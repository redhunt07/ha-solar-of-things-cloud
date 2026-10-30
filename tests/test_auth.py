"""Offline session-renewal regressions with a fake cloud and synthetic tokens."""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _pkg  # noqa: F401
from solar_of_things_cloud.api import (
    ApiError,
    AuthenticationError,
    SolarApi,
)
from solar_of_things_cloud.auth import CloudAuth


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)

    def get(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def renewed():
    return FakeResponse(
        {
            "code": 0,
            "data": {
                "accessToken": "new-access",
                "refreshToken": "rotated-refresh",
                "accessTokenWillExpiredAt": "2099-01-01T00:00:00Z",
                "refreshTokenWillExpiredAt": "2099-02-01T00:00:00Z",
            },
        }
    )


def telemetry():
    return FakeResponse(
        {
            "code": 0,
            "data": {
                "time": datetime.now(UTC).isoformat(),
                "fields": {"batteryVoltage": {"unit": "V", "value": 26.4}},
            },
        }
    )


class AuthTests(unittest.IsolatedAsyncioTestCase):
    def make_auth(self, session, **extra):
        self.saved = []

        async def save(data):
            self.saved.append(data)

        return CloudAuth(
            session,
            {"token": "old-access", "refresh_token": "refresh", **extra},
            save,
        )

    async def test_rotation_is_persisted(self) -> None:
        auth = self.make_auth(FakeSession([renewed()]))
        self.assertEqual(
            await auth.async_get_token(rejected="old-access"), "new-access"
        )
        self.assertEqual(self.saved[0]["refresh_token"], "rotated-refresh")

    async def test_concurrent_callers_share_one_renewal(self) -> None:
        session = FakeSession([renewed()])
        auth = self.make_auth(session)
        tokens = await asyncio.gather(
            auth.async_get_token(rejected="old-access"),
            auth.async_get_token(rejected="old-access"),
        )
        self.assertEqual(tokens, ["new-access", "new-access"])
        self.assertEqual(len(session.calls), 1)

    async def test_proactive_renewal_before_expiry(self) -> None:
        auth = self.make_auth(
            FakeSession([renewed()]), access_expires="2020-01-01T00:00:00Z"
        )
        self.assertEqual(await auth.async_get_token(), "new-access")

    async def test_no_renewal_while_valid(self) -> None:
        session = FakeSession([])
        auth = self.make_auth(session, access_expires="2099-01-01T00:00:00Z")
        self.assertEqual(await auth.async_get_token(), "old-access")
        self.assertEqual(session.calls, [])

    async def test_missing_refresh_token_requires_reauth(self) -> None:
        auth = self.make_auth(FakeSession([]), refresh_token="")
        with self.assertRaises(AuthenticationError):
            await auth.async_get_token(rejected="old-access")

    async def test_application_code_9_marks_session_expired(self) -> None:
        api = SolarApi(FakeSession([FakeResponse({"code": 9})]), "123")
        with self.assertRaises(AuthenticationError):
            await api.async_get_state()

    async def test_retry_is_bounded(self) -> None:
        session = FakeSession(
            [FakeResponse({"code": 9}), renewed(), FakeResponse({"code": 9})]
        )
        auth = self.make_auth(session)
        api = SolarApi(session, "123", auth)
        with self.assertRaises(AuthenticationError):
            await api.async_get_state()
        self.assertEqual(len(session.calls), 3)

    async def test_renewal_recovers_expired_session(self) -> None:
        session = FakeSession([FakeResponse({"code": 9}), renewed(), telemetry()])
        auth = self.make_auth(session)
        result = await SolarApi(session, "123", auth).async_get_state()
        self.assertEqual(result["values"], {"batteryVoltage": 26.4})
        self.assertEqual(len(session.calls), 3)

    async def test_network_failure_is_not_authentication(self) -> None:
        auth = self.make_auth(FakeSession([FakeResponse({}, status=503)]))
        with self.assertRaises(ApiError) as raised:
            await auth.async_get_token(rejected="old-access")
        self.assertNotIsInstance(raised.exception, AuthenticationError)
        self.assertFalse(self.saved)

    async def test_invalid_schema_is_not_saved(self) -> None:
        auth = self.make_auth(FakeSession([FakeResponse({"code": 0, "data": {}})]))
        with self.assertRaises(ApiError):
            await auth.async_get_token(rejected="old-access")
        self.assertFalse(self.saved)

    async def test_refresh_rejected_requires_reauth(self) -> None:
        auth = self.make_auth(FakeSession([FakeResponse({}, status=401)]))
        with self.assertRaises(AuthenticationError):
            await auth.async_get_token(rejected="old-access")


if __name__ == "__main__":
    unittest.main()

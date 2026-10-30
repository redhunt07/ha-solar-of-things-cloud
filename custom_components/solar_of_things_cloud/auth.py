"""Session renewal for the Solar of Things cloud API.

The vendor mobile app renews an expired session by posting the current access
token and the matching refresh token to a signed endpoint. The signature uses
the public web-portal application identity, whose secret is stored encrypted
in the portal build. This module reproduces that accepted request; it never
sends the account password and never calls a write endpoint.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .api import ApiError, AuthenticationError
from .const import (
    APP_ID,
    APP_SECRET_ENC,
    BASE_URL,
    REFRESH_MARGIN,
    REFRESH_PATH,
    REQUEST_TIMEOUT,
    TIME_ZONE,
)

SaveCallback = Callable[[dict[str, Any]], Awaitable[None]]


def _decrypt_secret() -> bytes:
    """Decrypt the public portal application secret with the APP_ID key."""
    digest = hashlib.md5(APP_ID.encode()).hexdigest().encode()
    decryptor = Cipher(algorithms.AES(digest[:16]), modes.CBC(digest[16:])).decryptor()
    raw = decryptor.update(base64.b64decode(APP_SECRET_ENC)) + decryptor.finalize()
    return raw.rstrip(b"\0")


def signed_headers(body: bytes, token: str) -> dict[str, str]:
    """Build the signed headers accepted by the renewal endpoint."""
    headers = {
        "IOT-Open-AppID": APP_ID,
        "IOT-Open-Body-Hash": hashlib.sha256(body).hexdigest(),
        "IOT-Open-Nonce": secrets.token_hex(16),
    }
    message = base64.b64encode(
        "&".join(f"{key}={headers[key]}" for key in sorted(headers)).encode()
    )
    signature = hashlib.md5(
        hmac.new(_decrypt_secret(), message, hashlib.sha256).digest()
    ).hexdigest()
    return {
        **headers,
        "IOT-Open-Sign": signature,
        "IOT-Token": token,
        "Content-Type": "application/json",
        "IOT-Time-Zone": TIME_ZONE,
    }


def parse_expiry(value: Any) -> float | None:
    """Return a POSIX timestamp for a vendor ISO date, or ``None``."""
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.timestamp() if stamp.tzinfo else None


class CloudAuth:
    """Owns the rotating credential pair and renews it when needed.

    The refresh token is rotated by the vendor: the new pair is persisted
    before any further request, so a restart cannot fall back to a revoked
    credential.
    """

    def __init__(
        self, session: ClientSession, data: dict[str, Any], save: SaveCallback
    ):
        self._session = session
        self._data = dict(data)
        self._save = save
        self._lock = asyncio.Lock()

    @property
    def data(self) -> dict[str, Any]:
        """Current credential data, safe to persist in the config entry."""
        return dict(self._data)

    def _refresh_due(self) -> bool:
        deadline = parse_expiry(self._data.get("access_expires"))
        if deadline is None:
            return False
        return datetime.now(UTC).timestamp() >= deadline - REFRESH_MARGIN

    async def async_get_token(self, rejected: str | None = None) -> str:
        """Return a usable access token, renewing it when required.

        ``rejected`` is the token the server just refused; concurrent callers
        share one renewal instead of racing.
        """
        async with self._lock:
            token = self._data.get("token")
            if not isinstance(token, str) or not token:
                raise AuthenticationError("Session renewal requires reauthentication")

            if rejected is not None and token != rejected:
                return token
            if rejected is None and not self._refresh_due():
                return token

            refresh_token = self._data.get("refresh_token")
            if not isinstance(refresh_token, str) or not refresh_token:
                raise AuthenticationError("Session renewal requires reauthentication")

            body = json.dumps(
                {"accessToken": token, "refreshToken": refresh_token},
                separators=(",", ":"),
            ).encode()

            async with self._session.post(
                BASE_URL + REFRESH_PATH,
                data=body,
                headers=signed_headers(body, token),
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise AuthenticationError("Refresh credential rejected")
                if response.status != 200:
                    raise ApiError("Session renewal temporarily unavailable")
                payload = await response.json()

            if not isinstance(payload, dict):
                raise ApiError("Invalid session renewal schema")
            if payload.get("code") == 9:
                raise AuthenticationError("Refresh credential expired")
            if payload.get("code") != 0:
                raise ApiError("Session renewal unsuccessful")

            data = payload.get("data")
            access_token = data.get("accessToken") if isinstance(data, dict) else None
            access_expires = (
                data.get("accessTokenWillExpiredAt") if isinstance(data, dict) else None
            )
            if (
                not isinstance(access_token, str)
                or not access_token
                or parse_expiry(access_expires) is None
            ):
                raise ApiError("Invalid session renewal schema")

            updated = {
                **self._data,
                "token": access_token,
                "refresh_token": data.get("refreshToken") or refresh_token,
                "access_expires": access_expires,
                "refresh_expires": data.get("refreshTokenWillExpiredAt")
                or self._data.get("refresh_expires"),
            }
            await self._save(updated)
            self._data = updated
            return access_token

"""Strictly read-only client and independently testable telemetry parser."""

from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Any, TypedDict

from aiohttp import ClientSession, ClientTimeout

from .const import (
    ACCEPT_LANGUAGE,
    BASE_URL,
    CLOCK_SKEW_TOLERANCE,
    MAX_TELEMETRY_AGE,
    REQUEST_TIMEOUT,
    SENSORS_BY_KEY,
    TELEMETRY_PATH,
    TIME_ZONE,
)


class Telemetry(TypedDict):
    """Validated telemetry sample."""

    time: datetime
    values: dict[str, float]


class ApiError(Exception):
    """Cloud returned an unusable response."""


class AuthenticationError(ApiError):
    """The session token is expired, revoked or invalid."""


def _parse_timestamp(value: Any) -> datetime:
    """Parse the vendor ISO timestamp, rejecting naive or malformed values."""
    if not isinstance(value, str):
        raise ApiError("Invalid telemetry timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise ApiError("Invalid telemetry timestamp") from err
    if stamp.tzinfo is None:
        raise ApiError("Invalid telemetry timestamp")
    return stamp


def _numeric_value(field: Any) -> float | None:
    """Return a finite numeric value, rejecting booleans and strings."""
    if not isinstance(field, dict) or field.get("isHidden") is True:
        return None
    value = field.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not isfinite(value):
        return None
    return float(value)


def parse_state(
    payload: Any, *, now: datetime | None = None, max_age: int = MAX_TELEMETRY_AGE
) -> Telemetry:
    """Validate a vendor payload and extract only the verified sensor keys.

    A malformed, stale or future-dated sample raises ``ApiError`` so it can
    never be turned into false zeros in Home Assistant.
    """
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise ApiError("Cloud returned an unsuccessful response")

    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("fields"), dict):
        raise ApiError("Invalid telemetry schema")

    stamp = _parse_timestamp(data.get("time"))
    reference = now or datetime.now(UTC)
    age = (reference - stamp).total_seconds()
    if age > max_age or age < -CLOCK_SKEW_TOLERANCE:
        raise ApiError("Telemetry is stale or timestamp is in the future")

    values: dict[str, float] = {}
    fields = data["fields"]
    for key, description in SENSORS_BY_KEY.items():
        field = fields.get(key)
        if not isinstance(field, dict) or field.get("unit") != description.unit:
            continue
        value = _numeric_value(field)
        if value is not None:
            values[key] = value

    return {"time": stamp, "values": values}


class SolarApi:
    """Minimal read-only client for the vendor telemetry endpoint."""

    def __init__(
        self,
        session: ClientSession,
        device_id: str,
        auth: Any | None = None,
        *,
        token: str | None = None,
    ) -> None:
        if not isinstance(device_id, str) or not device_id.isdigit():
            raise ValueError("Device ID must contain only digits")
        self._session = session
        self._device_id = device_id
        self._auth = auth
        self._token = token

    async def async_get_state(self) -> Telemetry:
        """Return one validated sample, renewing the session at most once."""
        token = await self._auth.async_get_token() if self._auth else self._token
        if not token:
            raise AuthenticationError("No session token available")
        try:
            return await self._async_get_state(token)
        except AuthenticationError:
            if self._auth is None:
                raise
            # At most one renewal and one retry, never an unbounded loop.
            token = await self._auth.async_get_token(rejected=token)
            return await self._async_get_state(token)

    async def _async_get_state(self, token: str) -> Telemetry:
        async with self._session.get(
            BASE_URL + TELEMETRY_PATH,
            params={"deviceId": self._device_id},
            headers={
                "IOT-Token": token,
                "Accept-Language": ACCEPT_LANGUAGE,
                "IOT-Time-Zone": TIME_ZONE,
            },
            allow_redirects=False,
            timeout=ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            if response.status in (401, 403):
                raise AuthenticationError("Renew the app session token")
            if response.status != 200:
                raise ApiError("Cloud HTTP request failed")
            payload = await response.json()

        if isinstance(payload, dict) and payload.get("code") == 9:
            raise AuthenticationError("Cloud session expired")
        return parse_state(payload)

"""Authentication for the Solar of Things cloud API.

Two mechanisms are supported, both against the same public portal identity:

- the rotating access/refresh token pair used by the vendor app;
- an account/password login, where the password is hashed locally with MD5
  (the format the vendor endpoint expects) and only the hash is stored.

Nothing here calls a write endpoint, and the account password is never kept
in clear text.
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
    LOGIN_PATH,
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
    """Build the signed headers accepted by the portal endpoints."""
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


def hash_password(password: str) -> str:
    """Return the password hash the vendor login endpoint expects.

    The endpoint compares an MD5 hex digest, not the clear-text password. Only
    this digest is stored in the config entry.
    """
    return hashlib.md5(password.encode()).hexdigest()


def parse_expiry(value: Any) -> float | None:
    """Return a POSIX timestamp for a vendor ISO date, or ``None``."""
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp.timestamp() if stamp.tzinfo else None


def _token_data(data: Any, *, account: str | None = None) -> dict[str, Any]:
    """Validate a login or renewal payload and normalize the credential pair."""
    access_token = data.get("accessToken") if isinstance(data, dict) else None
    access_expires = (
        data.get("accessTokenWillExpiredAt") if isinstance(data, dict) else None
    )
    if (
        not isinstance(access_token, str)
        or not access_token
        or parse_expiry(access_expires) is None
    ):
        raise ApiError("Invalid credential response schema")
    refresh_token = data.get("refreshToken") if isinstance(data, dict) else None
    return {
        "token": access_token,
        "refresh_token": refresh_token if isinstance(refresh_token, str) else None,
        "access_expires": access_expires,
        "refresh_expires": data.get("refreshTokenWillExpiredAt")
        if isinstance(data, dict)
        else None,
        "account": (data.get("account") if isinstance(data, dict) else None) or account,
    }


async def async_login(
    session: ClientSession, account: str, password_hash: str
) -> dict[str, Any]:
    """Log in with an account and its MD5 password digest.

    The vendor endpoint accepts the same portal signature used for renewal;
    the empty IOT-Token header is omitted.
    """
    body = json.dumps(
        {"account": account, "password": password_hash}, separators=(",", ":")
    ).encode()
    headers = signed_headers(body, "")
    headers.pop("IOT-Token", None)

    async with session.post(
        BASE_URL + LOGIN_PATH,
        data=body,
        headers=headers,
        timeout=ClientTimeout(total=REQUEST_TIMEOUT),
        allow_redirects=False,
    ) as response:
        if response.status in (401, 403):
            raise AuthenticationError("Account login rejected")
        if response.status != 200:
            raise ApiError("Account login temporarily unavailable")
        payload = await response.json()

    if not isinstance(payload, dict):
        raise ApiError("Invalid account login response")
    code = payload.get("code")
    if code in (7, 20101):
        raise AuthenticationError("Account or password rejected")
    if code != 0:
        raise ApiError("Account login unsuccessful")

    return _token_data(payload.get("data"), account=account)


class CloudAuth:
    """Owns the rotating credential pair and renews it when needed.

    When a stored account and password digest are available, an expired or
    revoked refresh token is recovered with a fresh login instead of asking
    the user for a new pair. Rotated credentials are persisted before any
    further request, so a restart cannot fall back to a revoked credential.
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

    def _can_login(self) -> bool:
        return bool(self._data.get("account") and self._data.get("password_hash"))

    async def async_get_token(self, rejected: str | None = None) -> str:
        """Return a usable access token, renewing or logging in when required.

        ``rejected`` is the token the server just refused; concurrent callers
        share one renewal instead of racing.
        """
        async with self._lock:
            token = self._data.get("token")
            has_token = isinstance(token, str) and bool(token)

            if has_token:
                if rejected is not None and token != rejected:
                    return token
                if rejected is None and not self._refresh_due():
                    return token

            if has_token and self._data.get("refresh_token"):
                try:
                    return await self._async_refresh(token)
                except AuthenticationError:
                    # Refresh revoked/expired: fall back to a fresh login when
                    # the account password digest is stored.
                    if not self._can_login():
                        raise

            if self._can_login():
                return await self._async_login()

            raise AuthenticationError("Session renewal requires reauthentication")

    async def _async_refresh(self, token: str) -> str:
        refresh_token = self._data["refresh_token"]
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

        refreshed = {
            key: value
            for key, value in _token_data(payload.get("data")).items()
            if value is not None
        }
        updated = {**self._data, **refreshed}
        if not updated.get("refresh_token"):
            updated["refresh_token"] = refresh_token
        await self._save(updated)
        self._data = updated
        return updated["token"]

    async def _async_login(self) -> str:
        updated = {
            **self._data,
            **await async_login(
                self._session, self._data["account"], self._data["password_hash"]
            ),
        }
        await self._save(updated)
        self._data = updated
        return updated["token"]

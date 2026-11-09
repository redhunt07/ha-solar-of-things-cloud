"""Config and reauthentication flows.

Two setup methods are offered: an account login (recommended, because it also
enables automatic recovery when the refresh token expires) or an existing
access/refresh token pair. The account password is hashed locally and only the
digest is stored.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ApiError, AuthenticationError, SolarApi
from .auth import CloudAuth, async_login, hash_password
from .const import DOMAIN

SECRET = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("account"): str,
        vol.Required("password"): SECRET,
    }
)

TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("token"): SECRET,
        vol.Optional("refresh_token", default=""): SECRET,
    }
)

REAUTH_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required("account"): str,
        vol.Required("password"): SECRET,
    }
)

REAUTH_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required("token"): SECRET,
        vol.Required("refresh_token"): SECRET,
    }
)


async def _validate_account(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Log in with the account and verify telemetry before creating the entry."""
    session = async_get_clientsession(hass)
    credentials = await async_login(
        session, data["account"], hash_password(data["password"])
    )
    await SolarApi(
        session, data["device_id"], token=credentials["token"]
    ).async_get_state()
    return {
        "device_id": data["device_id"],
        "account": credentials.get("account") or data["account"],
        "password_hash": hash_password(data["password"]),
        **credentials,
    }


async def _validate_tokens(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate an existing token pair against the cloud."""
    session = async_get_clientsession(hass)
    stored = dict(data)

    async def _save(updated: dict[str, Any]) -> None:
        stored.update(updated)

    auth = CloudAuth(session, stored, _save)
    await SolarApi(session, data["device_id"], auth).async_get_state()
    return stored


class SolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the read-only cloud setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user choose between an account login and existing tokens."""
        return self.async_show_menu(step_id="user", menu_options=["account", "token"])

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for the device ID, account and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                "device_id": str(user_input["device_id"]).strip(),
                "account": str(user_input["account"]).strip(),
                "password": user_input["password"],
            }
            try:
                validated = await _validate_account(self.hass, data)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ApiError, ClientError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(validated["device_id"])
                # Re-running setup for an existing device upgrades its stored
                # credentials (for example from tokens to the account method).
                self._abort_if_unique_id_configured(updates=validated)
                return self.async_create_entry(title="Solar of Things", data=validated)

        return self.async_show_form(
            step_id="account", data_schema=ACCOUNT_SCHEMA, errors=errors
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for the device ID and an existing session."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                "device_id": str(user_input["device_id"]).strip(),
                "token": user_input["token"].strip(),
                "refresh_token": user_input.get("refresh_token", "").strip(),
            }
            try:
                validated = await _validate_tokens(self.hass, data)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ApiError, ClientError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data["device_id"])
                self._abort_if_unique_id_configured(updates=validated)
                return self.async_create_entry(title="Solar of Things", data=validated)

        return self.async_show_form(
            step_id="token", data_schema=TOKEN_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication with the method used at setup."""
        entry = self._get_reauth_entry()
        if entry.data.get("account") and entry.data.get("password_hash"):
            return await self.async_step_reauth_account()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_account(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Replace the account password after a rejected login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self._get_reauth_entry()
            session = async_get_clientsession(self.hass)
            try:
                credentials = await async_login(
                    session,
                    str(user_input["account"]).strip(),
                    hash_password(user_input["password"]),
                )
                await SolarApi(
                    session, entry.data["device_id"], token=credentials["token"]
                ).async_get_state()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ApiError, ClientError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                updated = {
                    **entry.data,
                    "account": credentials.get("account")
                    or str(user_input["account"]).strip(),
                    "password_hash": hash_password(user_input["password"]),
                    **credentials,
                }
                return self.async_update_reload_and_abort(
                    entry, data_updates=updated, reason="reauth_successful"
                )

        entry = self._get_reauth_entry()
        schema = self.add_suggested_values_to_schema(
            REAUTH_ACCOUNT_SCHEMA, {"account": entry.data.get("account", "")}
        )
        return self.async_show_form(
            step_id="reauth_account", data_schema=schema, errors=errors
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Replace the credential pair with a fresh one from the app."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self._get_reauth_entry()
            data = {
                **entry.data,
                "token": user_input["token"].strip(),
                "refresh_token": user_input["refresh_token"].strip(),
                "access_expires": None,
            }
            try:
                session = async_get_clientsession(self.hass)
                stored = dict(data)

                async def _save(updated: dict[str, Any]) -> None:
                    stored.update(updated)

                auth = CloudAuth(session, stored, _save)
                await auth.async_get_token(rejected=data["token"])
                await SolarApi(session, data["device_id"], auth).async_get_state()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ApiError, ClientError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=stored, reason="reauth_successful"
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_TOKEN_SCHEMA, errors=errors
        )

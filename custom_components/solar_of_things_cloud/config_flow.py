"""Config and reauthentication flows.

Users supply an existing session token from their own Solar of Things app;
the account password is never requested or stored.
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
from .auth import CloudAuth
from .const import DOMAIN

SECRET = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("token"): SECRET,
        vol.Optional("refresh_token", default=""): SECRET,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required("token"): SECRET,
        vol.Required("refresh_token"): SECRET,
    }
)


async def _validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate credentials against the cloud and return the refreshed data."""
    session = async_get_clientsession(hass)
    stored = dict(data)

    async def _save(updated: dict[str, Any]) -> None:
        stored.update(updated)

    auth = CloudAuth(session, stored, _save)
    api = SolarApi(session, data["device_id"], auth)
    await api.async_get_state()
    return stored


class SolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the read-only cloud setup."""

    VERSION = 1

    async def async_step_user(
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
                validated = await _validate(self.hass, data)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ApiError, ClientError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data["device_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Solar of Things", data=validated)

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication when the session can no longer be renewed."""
        return await self.async_step_reauth_confirm()

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
                # Force a renewal so both halves of the pair are proven.
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
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )

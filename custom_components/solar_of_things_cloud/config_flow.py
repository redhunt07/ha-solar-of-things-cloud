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
from homeassistant.helpers import device_registry as dr
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


def vendor_credentials(hass: HomeAssistant) -> dict[str, str] | None:
    """Best-effort prefill from the official vendor integration, if present.

    Only a single unambiguous entry is used, and the token is revalidated
    before it is stored, so a stale vendor session cannot be imported blindly.
    """
    entries = hass.config_entries.async_entries("solar_of_things")
    registry = dr.async_get(hass)
    candidates: list[dict[str, str]] = []

    for entry in entries:
        token = entry.data.get("iot_token")
        if not token:
            continue
        device_id = entry.data.get("device_id")
        if not device_id:
            identifiers = {
                str(identifier[2])
                for device in registry.devices.values()
                if entry.entry_id in device.config_entries
                for identifier in device.identifiers
                if len(identifier) == 3
                and identifier[0] == "solar_of_things"
                and str(identifier[2]).isdigit()
            }
            if len(identifiers) != 1:
                continue
            device_id = identifiers.pop()
        candidates.append({"device_id": str(device_id), "token": token})

    return candidates[0] if len(candidates) == 1 else None


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

        schema = USER_SCHEMA
        if user_input is None:
            suggested = vendor_credentials(self.hass)
            if suggested:
                schema = self.add_suggested_values_to_schema(schema, suggested)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

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

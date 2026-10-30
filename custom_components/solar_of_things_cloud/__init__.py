"""Set up the read-only Solar of Things Cloud integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ApiError, AuthenticationError, SolarApi, Telemetry
from .auth import CloudAuth
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one inverter from a config entry."""
    session = async_get_clientsession(hass)

    async def _save_credentials(data: dict) -> None:
        hass.config_entries.async_update_entry(entry, data=data)

    auth = CloudAuth(session, dict(entry.data), _save_credentials)
    api = SolarApi(session, entry.data["device_id"], auth)

    async def _async_update() -> Telemetry:
        try:
            return await api.async_get_state()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Cloud session requires reauthentication"
            ) from err
        except (ApiError, ClientError, TimeoutError, ValueError) as err:
            # Never interpolate exception text: it may contain URLs or headers.
            raise UpdateFailed(
                "Cloud telemetry unavailable, expired session, or stale data"
            ) from err

    coordinator: DataUpdateCoordinator[Telemetry] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_update,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.info(
        "Cloud telemetry ready: source timestamp %s, %s measurements",
        coordinator.data["time"].isoformat(),
        len(coordinator.data["values"]),
    )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data = None
    return unloaded

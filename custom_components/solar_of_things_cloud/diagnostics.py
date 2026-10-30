"""Diagnostics support that never exposes session credentials."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import Telemetry
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for one config entry."""
    coordinator: Any = entry.runtime_data
    data: Telemetry | None = getattr(coordinator, "data", None)

    return {
        "entry": {
            "domain": DOMAIN,
            "device_id": entry.data.get("device_id"),
            "has_refresh_token": bool(entry.data.get("refresh_token")),
            "access_expires": entry.data.get("access_expires"),
            "refresh_expires": entry.data.get("refresh_expires"),
        },
        "coordinator": {
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if getattr(coordinator, "update_interval", None)
                else None
            ),
            "source_time": data["time"].isoformat() if data else None,
        },
        "measurements": data["values"] if data else {},
    }

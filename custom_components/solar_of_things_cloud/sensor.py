"""Read-only sensor platform: units come from the vendor, never rescaled."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api import Telemetry
from .const import DOMAIN, SENSORS, SensorDescription


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one entity per measurement currently present in the sample."""
    coordinator: DataUpdateCoordinator[Telemetry] = entry.runtime_data
    async_add_entities(
        SolarSensor(coordinator, entry, description)
        for description in SENSORS
        if description.key in coordinator.data["values"]
    )


class SolarSensor(CoordinatorEntity[DataUpdateCoordinator[Telemetry]], SensorEntity):
    """A single read-only telemetry measurement."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Telemetry],
        entry: ConfigEntry,
        description: SensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._attr_name = description.name
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = (
            SensorDeviceClass(description.device_class)
            if description.device_class
            else None
        )
        self._attr_state_class = SensorStateClass(description.state_class)
        self._attr_unique_id = f"{entry.data['device_id']}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["device_id"])},
            name="Inverter cloud sola lettura",
            manufacturer="Solar of Things",
            model="Cloud telemetry",
            configuration_url="https://solar.siseli.com/",
        )

    @property
    def available(self) -> bool:
        """Only expose values that are present in the current sample."""
        return (
            super().available
            and self._description.key in self.coordinator.data["values"]
        )

    @property
    def native_value(self) -> float | None:
        """Return the vendor value unchanged."""
        return self.coordinator.data["values"].get(self._description.key)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose when the cloud acquired the sample, not when it was fetched."""
        return {
            "source_time": self.coordinator.data["time"].isoformat(),
            "source": "vendor_cloud",
        }

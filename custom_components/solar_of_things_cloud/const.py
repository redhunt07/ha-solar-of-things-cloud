"""Constants for the Solar of Things Cloud integration.

The integration is deliberately read-only: it only calls the vendor telemetry
endpoint (plus the session renewal endpoint) and never changes inverter
settings.
"""

from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "solar_of_things_cloud"

# Fixed vendor origin. No caller-supplied URL, path or redirect is followed.
BASE_URL = "https://solar.siseli.com/apis"
TELEMETRY_PATH = "/deviceState/simple/state/latest/v1"
REFRESH_PATH = "/login/refresh/access/token"
LOGIN_PATH = "/login/account"

# Public web-portal application identity used to sign session renewal requests.
APP_ID = "rBrTRfAPXz"
# AES-CBC encrypted application secret (portal build), decrypted with a key
# derived from APP_ID. It is a public application credential, not a user secret.
APP_SECRET_ENC = "I4D0KRr2339z3pQ/at91V9BpFAOe54DaTafwSm6suIQ="

DEFAULT_SCAN_INTERVAL = 60
REQUEST_TIMEOUT = 25
MAX_TELEMETRY_AGE = 600
CLOCK_SKEW_TOLERANCE = 120
REFRESH_MARGIN = 300

TIME_ZONE = "Europe/Rome"
ACCEPT_LANGUAGE = "en"


@dataclass(frozen=True, kw_only=True)
class SensorDescription:
    """Description of one verified, read-only telemetry sensor."""

    key: str
    name: str
    unit: str
    device_class: str | None = None
    state_class: str = "measurement"


# A deliberately small, verified surface: no inferred battery power, SOC or
# energy values are invented. Units are exactly the ones decoded by the cloud.
SENSORS: tuple[SensorDescription, ...] = (
    SensorDescription(
        key="batteryVoltage", name="Battery voltage", unit="V", device_class="voltage"
    ),
    SensorDescription(
        key="batteryCapacity",
        name="Battery capacity (inverter estimate)",
        unit="%",
        device_class="battery",
    ),
    SensorDescription(
        key="batteryChargingCurrent",
        name="Battery charging current",
        unit="A",
        device_class="current",
    ),
    SensorDescription(
        key="batteryDischargeCurrent",
        name="Battery discharge current",
        unit="A",
        device_class="current",
    ),
    SensorDescription(
        key="acInputVoltage", name="Grid voltage", unit="V", device_class="voltage"
    ),
    SensorDescription(
        key="mainsFrequency", name="Grid frequency", unit="Hz", device_class="frequency"
    ),
    SensorDescription(
        key="mainsPower", name="Grid power", unit="kW", device_class="power"
    ),
    SensorDescription(
        key="outputVoltage", name="Output voltage", unit="V", device_class="voltage"
    ),
    SensorDescription(
        key="outputFrequency",
        name="Output frequency",
        unit="Hz",
        device_class="frequency",
    ),
    SensorDescription(
        key="outputActivePower", name="Load power", unit="kW", device_class="power"
    ),
    SensorDescription(key="outputLoadPercent", name="Load percentage", unit="%"),
    SensorDescription(
        key="generationPower",
        name="PV generation power",
        unit="kW",
        device_class="power",
    ),
    SensorDescription(
        key="pvVoltage", name="PV voltage", unit="V", device_class="voltage"
    ),
    SensorDescription(
        key="pvCurrent", name="PV current", unit="A", device_class="current"
    ),
    SensorDescription(key="pvPower", name="PV power", unit="kW", device_class="power"),
    # The vendor total is used as-is; resets/corrections are not claimed to be
    # monotonic, so the conservative TOTAL state class is used instead of
    # TOTAL_INCREASING.
    SensorDescription(
        key="pvGeneratedEnergyOfDay",
        name="PV energy today",
        unit="kWh",
        device_class="energy",
        state_class="total",
    ),
    SensorDescription(
        key="pvGeneratedEnergyOfTotal",
        name="PV energy total",
        unit="kWh",
        device_class="energy",
        state_class="total",
    ),
    SensorDescription(
        key="inverterTemperature",
        name="Inverter temperature",
        unit="°C",
        device_class="temperature",
    ),
)

SENSORS_BY_KEY: dict[str, SensorDescription] = {item.key: item for item in SENSORS}

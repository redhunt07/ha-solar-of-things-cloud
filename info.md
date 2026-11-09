![Solar of Things Cloud](https://raw.githubusercontent.com/redhunt07/ha-solar-of-things-cloud/main/custom_components/solar_of_things_cloud/brand/icon.png)

# Solar of Things Cloud for Home Assistant

Read-only cloud telemetry for Solar of Things (Siseli) inverters: battery, grid, PV, load and inverter temperature. Sign in with the app account and the session is recovered automatically when it expires.

- **18 read-only sensors**, units preserved.
- **Automatic session recovery** before expiry, with one bounded retry and rotated tokens persisted.
- **Account login** (password hashed locally, only the digest stored) or an existing session token.
- **Reauthentication flow** if the password changes or the session is revoked.
- **Data quality guards**: stale samples, wrong units and non-numeric values are rejected, never shown as zeros.
- **No writes** to the inverter.

## Installation

1. HACS → Integrations → search **Solar of Things Cloud**.
2. Install it and restart Home Assistant.
3. Settings → Devices & services → Add integration → **Solar of Things Cloud**.

Choose the account login and enter the numeric device ID, account and password: the integration obtains and renews the session itself. Alternatively, paste an existing access/refresh token pair. Credentials of other integrations are never read.

Requires Home Assistant 2026.10 or newer. No extra Python packages.

Optional Energy dashboard package: [`examples/sot_cloud_energy.yaml`](examples/sot_cloud_energy.yaml).

Full documentation: [README.md](README.md) · [Italiano](README.it.md). MIT licensed.

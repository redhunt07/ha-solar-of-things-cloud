# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-10-30

First public release, extracted from a live, verified installation.

### Added

- Read-only cloud telemetry for Solar of Things (Siseli) inverters: battery,
  grid, PV, load and inverter temperature (18 sensors, units preserved).
- Signed session renewal using the public web-portal identity, with proactive
  renewal 5 minutes before expiry, a single bounded retry and persistence of
  rotated credentials before further requests.
- Reauthentication flow for a fresh access/refresh token pair.
- Optional prefill of the device ID and access token from the official
  `solar_of_things` integration, always revalidated before being stored.
- Data quality guards: stale samples, future timestamps beyond the allowed
  clock skew, unexpected units, hidden fields and non-numeric values are
  rejected instead of being exposed as zeros.
- Redacted diagnostics support.
- English and Italian UI strings.
- Optional Energy dashboard package with estimated counters and day/month/year
  utility meters.
- Offline test suite (parser and session renewal) with a sanitized real
  telemetry fixture.
- CI workflows for linting, tests, `hassfest` and HACS validation.

### Verified

- Home Assistant 2026.10.4, live inverter, 18 entities with numeric states.
- Forced renewal inside Home Assistant: the session was renewed, the new
  expiry persisted and all sensors loaded again.
- 23 offline tests passing.

### Notes

- Polling is fixed at 60 seconds; vendor samples are typically about 5 minutes
  old.
- Energy counters are estimates, not fiscal meters. The PV total is the only
  vendor-provided energy counter.
- The integration is read-only and never changes inverter settings.

[1.0.0]: https://github.com/redhunt07/ha-solar-of-things-cloud/releases/tag/v1.0.0

# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-11-09

### Added

- Account login: the setup flow can now sign in with the app account and
  password, obtaining the session automatically. The password is hashed
  locally with MD5 (the digest the vendor endpoint expects) and only the
  digest is stored; the clear-text password is never persisted, logged or sent.
- Automatic recovery when the refresh token expires or is revoked: if an
  account/password digest is stored, the integration logs in again and saves
  the new credential pair instead of asking for a new token.
- Dedicated reauthentication step for the account method.

### Changed

- The setup flow now offers a choice between the account login and an existing
  session token. The token method is unchanged.
- HACS installation instructions now lead with a plain HACS search, as the
  integration is in the default store. The "custom repository" wording was
  removed.
- README, Italian README and `info.md` updated accordingly.

### Unchanged

- Read-only telemetry, sensor names, entity IDs, polling interval and the
  Energy dashboard example package.

## [1.0.2] — 2026-11-04

### Changed

- The setup form no longer reads credentials from the official Solar of Things
  integration: it only asks for the values the user enters. Removed the
  `vendor_credentials()` helper and the suggested-value prefill.
- README, Italian README and `info.md` updated to match.

## [1.0.1] — 2026-10-31

### Changed

- Added the `energy.solar_batteries` integration category for catalog discovery,
  resolving the category warning raised during HACS submission validation.
- No changes to telemetry, authentication or polling behavior.

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

[1.0.1]: https://github.com/redhunt07/ha-solar-of-things-cloud/releases/tag/v1.0.1

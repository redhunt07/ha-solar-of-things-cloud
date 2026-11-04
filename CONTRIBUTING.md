# Contributing

Thanks for taking the time to improve this integration. Useful contributions
include reproducible bug reports, hardware tests, documentation fixes and
focused pull requests.

## Before opening an issue

1. Check the [troubleshooting table](README.md#troubleshooting).
2. Confirm the integration version (HACS or `manifest.json`) and the Home
   Assistant version.
3. Reproduce with debug logging enabled and **remove tokens** from the log
   excerpt before posting. The integration does not log tokens, but copied
   app logs and diagnostics may contain them.

A good bug report includes:

- Home Assistant version and installation type;
- integration version and installation method (HACS or manual);
- inverter model and, if known, firmware version;
- what you expected, what happened and the steps to reproduce it;
- redacted logs and, when useful, the diagnostics download (already redacted).

## Development setup

```sh
git clone https://github.com/redhunt07/ha-solar-of-things-cloud.git
cd ha-solar-of-things-cloud

python3 -m unittest discover -s tests -t . -v
ruff check .
ruff format --check .
```

The offline suite does not need Home Assistant. It covers the telemetry parser
and the session renewal with a sanitized fixture and a fake cloud.

To test inside Home Assistant, copy `custom_components/solar_of_things_cloud`
into `/config/custom_components/`, restart, and check the log for setup errors.
Run **Developer tools → Check configuration** before restarting.

## Pull requests

- Keep changes focused; one topic per pull request.
- Add or update tests for parser and renewal behaviour.
- Run `ruff check .` and `ruff format --check .`.
- Do not include tokens, diagnostics files or `.storage` in commits.
- Describe what was tested and on which Home Assistant version.
- Never add a write endpoint without documenting why: the integration is
  intentionally read-only.

## Code layout

| File | Responsibility |
| :--- | :--- |
| `api.py` | Read-only client and telemetry parser |
| `auth.py` | Signed session renewal and credential rotation |
| `config_flow.py` | Setup and reauthentication |
| `sensor.py` | Read-only entities |
| `const.py` | Endpoints, constants and sensor descriptions |
| `diagnostics.py` | Redacted diagnostics |
| `__init__.py` | Config entry setup and coordinator |

## Translations

UI strings live in `custom_components/solar_of_things_cloud/translations/`.
English and Italian are maintained; additional languages are welcome. Entity
names are intentionally stable and not translated, so entity IDs do not change
when the Home Assistant language changes.

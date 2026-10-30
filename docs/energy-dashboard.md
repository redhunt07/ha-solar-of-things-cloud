# Energy dashboard setup (optional)

The integration exposes power and energy measurements; it does not create
cumulative counters by itself. The package in
[`examples/sot_cloud_energy.yaml`](../examples/sot_cloud_energy.yaml) builds
them from the read-only sensors.

## What the package creates

| Source | Purpose |
| :--- | :--- |
| `sensor.sot_rete_prelevata_energia` | Estimated grid import, integrated from `grid_power` |
| `sensor.sot_fotovoltaico_energia_totale` | Vendor PV total, used as-is |
| `sensor.sot_batteria_caricata_energia` | Estimated battery charge energy (`V × A`, DC side) |
| `sensor.sot_batteria_scaricata_energia` | Estimated battery discharge energy (`V × A`, DC side) |
| `sensor.sot_carichi_energia` | Estimated load energy supplied by the inverter |

Each counter also has daily, monthly and yearly utility meters.

## Install

1. Copy `examples/sot_cloud_energy.yaml` to `/config/packages/`.
2. Make sure packages are enabled in `configuration.yaml`:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

3. Restart Home Assistant and check **Developer tools → Check configuration**.
4. Open **Settings → Dashboards → Energy** and add:

   - **Grid consumption**: `sensor.sot_rete_prelevata_energia`, power
     `sensor.sot_rete_prelievo_potenza`.
   - **Solar production**: `sensor.sot_fotovoltaico_energia_totale`, power
     `sensor.sot_fotovoltaico_potenza`.
   - **Battery**: from `sensor.sot_batteria_scaricata_energia`, to
     `sensor.sot_batteria_caricata_energia`, power
     `sensor.sot_batteria_potenza_netta`.
   - **Device consumption**: `sensor.sot_carichi_energia`.

5. Wait for normal recorder/statistics cycles before expecting populated
   graphs. New counters start from zero and do not backfill history.

## Accuracy notes

- Cloud samples arrive roughly every 5 minutes; integration is an estimate,
  not a fiscal meter.
- Battery power is computed on the DC side and does not account for inverter
  efficiency.
- Grid power reflects the inverter input, not necessarily the whole house.
- The PV total is the only counter provided by the vendor; resets and
  corrections are not assumed to be monotonic, so it is not declared
  `total_increasing`.
- If an entity is unavailable, the integral does not treat it as zero.

Entity IDs in the package match a default installation. If you renamed
entities, update the package accordingly.

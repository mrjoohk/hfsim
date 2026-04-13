# Flight + Sensor + Atmosphere Implementation Analysis

## Goal
- Prioritize flight, sensor, and atmosphere verification before threat/radar and full-environment validation.
- Add deterministic validation logging and an offline visualization path that does not block core simulation throughput.

## Key Decisions
- Keep `ownship 6-DoF` as the acceptance anchor and make atmosphere influence explicit in IF-02.
- Keep the sensor model lightweight and state-derived rather than beam-level or image-based.
- Keep `pyvista` optional and offline-only so that validation/analysis tooling does not become a hard runtime dependency.

## Implementation Mapping
- `IF-02`
  - Added deterministic atmosphere adjustment helper.
  - Applied density, wind, and turbulence to ownship propagation and sensor quality.
- `IF-03`
  - Expanded branch rollout state payload to carry sensor and atmosphere values needed for downstream logging/visualization.
- Logging
  - Added deterministic JSONL and CSV export helpers.
  - Added branch-result flattening for branch-separated validation logs.
- Visualization
  - Added offline `pyvista` viewer helper with dependency injection for testing.

## Validation Focus
- Ownship stability, deterministic replay, throttle/pitch/roll sanity remain MUST checks.
- Added atmosphere sensitivity and sensor continuity checks.
- Added branch logging separation and viewer smoke coverage.

## Deferred
- Threat + radar validation deepening.
- Full-environment long-horizon acceptance.
- Real `pyvista` package installation/integration in runtime environment.

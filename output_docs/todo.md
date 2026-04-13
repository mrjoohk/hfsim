# TODO

## Deferred After MVP Runtime Branching

- Define `evidence_pack` schema after MVP acceptance metrics are finalized.
- Add JSBSim or other open-model comparison suite for secondary 6-DoF validation.
- Expand aerodynamic calibration workflow and calibration case library.
- Upgrade radar/sensor models from continuity placeholders to richer mission models.
- Upgrade atmosphere/weather model beyond continuity-level state propagation.
- Add threat + radar validation harness after flight + sensor + atmosphere acceptance stabilizes.
- Add full-environment long-horizon acceptance for checkpoint completeness and cross-subsystem continuity.
- Add real `pyvista` dependency/install path and richer offline viewer overlays for threat/radar analysis.
- Add real `ray` dependency/install path and actor-pool execution harness on top of `hf_sim.ray_runtime`.
- Add benchmark and profiling automation for time-acceleration regression tracking.
- Persist run manifests and branch rollout artifacts into structured evidence outputs.
- Revisit observation schema once branched radar/sensor channels become learner inputs.

# IF Decomposition

## IF-01: Scenario and Resource Orchestration

Input:  execution_request (structured config, dimensionless + SI mixed schema)
Output: execution_bundle (structured scenario + rollout plan object)

[sequential]

- UF-01-01: parse_execution_config
  Input: execution_request -> Output: normalized_request (structured config)
  Note: Validate and normalize experiment, curriculum, and benchmark options.
- UF-01-02: inspect_hardware_profile [depends on UF-01-01]
  Input: normalized_request -> Output: hardware_budget (resource profile)
  Note: Detect CPU, RAM, GPU, and derive safe memory ceilings.
- UF-01-03: synthesize_scenario [depends on UF-01-01]
  Input: normalized_request -> Output: scenario_instance (scenario object)
  Note: Generate seeded learnability-first scenario with curriculum policy.
- UF-01-04: size_rollout_batch [depends on UF-01-02]
  Input: hardware_budget -> Output: rollout_plan (batch/resource plan)
  Note: Compute hardware-adaptive rollout parallelism for the active motion-model stack.
- UF-01-05: assemble_execution_bundle [depends on UF-01-03]
  Input: scenario_instance -> Output: partial_bundle (execution object)
  Note: Package scenario metadata, seed, and agent count into execution format.
- UF-01-06: finalize_execution_bundle [depends on UF-01-04]
  Input: partial_bundle -> Output: execution_bundle (final execution object)
  Note: Merge rollout plan and scenario package into simulator-ready bundle.

---

## IF-02: Flight and Threat Dynamics Propagation

Input:  dynamics_step_request (structured state + control bundle)
Output: dynamics_step_result (structured multi-entity state bundle)

[sequential]

- UF-02-01: decode_state_bundle
  Input: dynamics_step_request -> Output: entity_states (entity state set)
  Note: Split ownship, threat, target, and environment states into typed substructures.
- UF-02-02: propagate_ownship_6dof [depends on UF-02-01]
  Input: entity_states -> Output: ownship_state_next (6-DoF state)
  Note: Advance rigid-body ownship dynamics with aerodynamic parameters.
- UF-02-03: propagate_threat_kinematics [depends on UF-02-01]
  Input: entity_states -> Output: threat_state_next (threat state set)
  Note: Advance active threat and adversary kinematic models.
- UF-02-04: propagate_target_environment [depends on UF-02-01]
  Input: entity_states -> Output: environment_state_next (environment state set)
  Note: Advance target, terrain-linked environment, and scenario transition state.
- UF-02-05: apply_aero_calibration [depends on UF-02-02]
  Input: ownship_state_next -> Output: calibrated_ownship_state (6-DoF state)
  Note: Apply configured aerodynamic coefficient model and calibration-ready overrides.
- UF-02-06: compose_step_result [depends on UF-02-03]
  Input: calibrated_ownship_state -> Output: dynamics_step_result (state bundle)
  Note: Merge ownship, threat, and environment updates into the next-step output.

---

## IF-03: Snapshot Branch Rollout Service

Input:  snapshot_rollout_request (snapshot payload + control request)
Output: snapshot_rollout_result (snapshot payload and branch trajectory object)

[sequential]

- UF-03-01: capture_snapshot_state
  Input: snapshot_rollout_request -> Output: snapshot_payload (serialized snapshot)
  Note: Materialize immutable snapshot from simulator-visible and hidden state.
- UF-03-02: restore_snapshot_state [depends on UF-03-01]
  Input: snapshot_payload -> Output: restored_runtime_state (runtime state)
  Note: Reconstruct deterministic runtime state from snapshot bytes.
- UF-03-03: inject_control_sequence [depends on UF-03-02]
  Input: restored_runtime_state -> Output: rollout_runtime_state (runtime state + controls)
  Note: Attach new control sequence for replay or counterfactual rollout.
- UF-03-04: execute_branch_rollout [depends on UF-03-03]
  Input: rollout_runtime_state -> Output: branch_trajectory (trajectory object)
  Note: Run fixed-horizon deterministic branch rollout from the restored state.
- UF-03-05: verify_replay_consistency [depends on UF-03-04]
  Input: branch_trajectory -> Output: consistency_flags (validation flags)
  Note: Check deterministic replay and event-log consistency constraints.
- UF-03-06: package_snapshot_result [depends on UF-03-05]
  Input: consistency_flags -> Output: snapshot_rollout_result (result bundle)
  Note: Return snapshot payload, branch trajectory, and verification metadata.

---

## IF-04: Structured Observation Interface

Input:  observation_request (structured simulator state object)
Output: observation_batch (structured observation object)

[sequential]

- UF-04-01: extract_vehicle_features
  Input: observation_request -> Output: vehicle_features (float feature vector)
  Note: Extract ownship and multi-agent state features for learning.
- UF-04-02: extract_terrain_features [depends on UF-04-01]
  Input: observation_request -> Output: terrain_features (float feature vector)
  Note: Build relative terrain and geometry features from environment state.
- UF-04-03: extract_threat_features [depends on UF-04-01]
  Input: observation_request -> Output: threat_features (float feature vector)
  Note: Build threat-relative features and masks from adversary state.
- UF-04-04: normalize_observation_features [depends on UF-04-02]
  Input: vehicle_features -> Output: normalized_features (normalized vector set)
  Note: Normalize and clip feature groups into learner-safe numeric ranges.
- UF-04-05: build_observation_masks [depends on UF-04-03]
  Input: threat_features -> Output: observation_masks (binary masks)
  Note: Generate validity masks for missing or gated observation channels.
- UF-04-06: assemble_observation_batch [depends on UF-04-05]
  Input: normalized_features -> Output: observation_batch (observation object)
  Note: Merge normalized features and masks into backward-compatible batch schema.

---

## IF-05: Evaluation, Benchmark, and Reproducibility Reporting

Input:  evaluation_request (metrics + run metadata bundle)
Output: evaluation_report_bundle (ranked metrics + acceleration report + manifest)

[sequential]

- UF-05-01: collect_run_metadata
  Input: evaluation_request -> Output: run_metadata (manifest fields)
  Note: Gather config, seed, hardware, and revision information for reproducibility.
- UF-05-02: compute_benchmark_metrics [depends on UF-05-01]
  Input: evaluation_request -> Output: benchmark_metrics (performance metrics)
  Note: Compute time acceleration and benchmark outcome metrics.
- UF-05-03: rank_learning_metrics [depends on UF-05-02]
  Input: benchmark_metrics -> Output: ranked_learning_metrics (ranked metrics)
  Note: Order metrics by prediction error, latent consistency, then policy convergence.
- UF-05-04: audit_scope_exclusions [depends on UF-05-01]
  Input: run_metadata -> Output: scope_audit (scope audit report)
  Note: Detect excluded non-MVP features in the phase-1 plan or run config.
- UF-05-05: build_reproducibility_manifest [depends on UF-05-03]
  Input: run_metadata -> Output: run_manifest (manifest object)
  Note: Emit reproducibility manifest in stable machine-readable form.
- UF-05-06: compose_evaluation_report [depends on UF-05-04]
  Input: ranked_learning_metrics -> Output: evaluation_report_bundle (report bundle)
  Note: Merge metrics, benchmark, scope audit, and manifest into final evidence bundle.

## UF Candidate Summary

| UF-ID | Parent IF | Verb-Noun Name | Input Type | Output Type |
|-------|-----------|---------------|------------|-------------|
| UF-01-01 | IF-01 | parse_execution_config | structured config | normalized config |
| UF-01-02 | IF-01 | inspect_hardware_profile | normalized config | resource profile |
| UF-01-03 | IF-01 | synthesize_scenario | normalized config | scenario object |
| UF-01-04 | IF-01 | size_rollout_batch | resource profile | rollout plan |
| UF-01-05 | IF-01 | assemble_execution_bundle | scenario object | execution object |
| UF-01-06 | IF-01 | finalize_execution_bundle | execution object | final execution object |
| UF-02-01 | IF-02 | decode_state_bundle | step request | entity state set |
| UF-02-02 | IF-02 | propagate_ownship_6dof | entity state set | 6-DoF state |
| UF-02-03 | IF-02 | propagate_threat_kinematics | entity state set | threat state set |
| UF-02-04 | IF-02 | propagate_target_environment | entity state set | environment state set |
| UF-02-05 | IF-02 | apply_aero_calibration | 6-DoF state | calibrated 6-DoF state |
| UF-02-06 | IF-02 | compose_step_result | calibrated state | state bundle |
| UF-03-01 | IF-03 | capture_snapshot_state | rollout request | serialized snapshot |
| UF-03-02 | IF-03 | restore_snapshot_state | serialized snapshot | runtime state |
| UF-03-03 | IF-03 | inject_control_sequence | runtime state | runtime state + controls |
| UF-03-04 | IF-03 | execute_branch_rollout | runtime state + controls | trajectory object |
| UF-03-05 | IF-03 | verify_replay_consistency | trajectory object | validation flags |
| UF-03-06 | IF-03 | package_snapshot_result | validation flags | result bundle |
| UF-04-01 | IF-04 | extract_vehicle_features | simulator state | float feature vector |
| UF-04-02 | IF-04 | extract_terrain_features | simulator state | float feature vector |
| UF-04-03 | IF-04 | extract_threat_features | simulator state | float feature vector |
| UF-04-04 | IF-04 | normalize_observation_features | feature vector set | normalized vector set |
| UF-04-05 | IF-04 | build_observation_masks | threat features | binary masks |
| UF-04-06 | IF-04 | assemble_observation_batch | normalized vector set | observation object |
| UF-05-01 | IF-05 | collect_run_metadata | eval request | manifest fields |
| UF-05-02 | IF-05 | compute_benchmark_metrics | eval request | performance metrics |
| UF-05-03 | IF-05 | rank_learning_metrics | performance metrics | ranked metrics |
| UF-05-04 | IF-05 | audit_scope_exclusions | manifest fields | scope audit report |
| UF-05-05 | IF-05 | build_reproducibility_manifest | manifest fields | manifest object |
| UF-05-06 | IF-05 | compose_evaluation_report | ranked metrics | report bundle |

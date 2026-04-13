# Verification Granularity Analysis
Date: 2026-04-08 13:15

## Scope

- Review whether every UF should have an independent functional test
- Determine which items are better validated at UF level versus IF-chain level
- Propose a verification-plan rewrite direction for `uf.md`

## Core Conclusion

Yes, the current verification plan should be restructured by **testable granularity**, not by a blanket rule of "every UF gets its own full functional test file."

The right approach is:
- keep **UF-level tests** for functions whose behavior is locally decidable and whose contract can be checked without the full chain
- use **IF-level chain/integration tests** for functions whose correctness depends primarily on upstream/downstream context, merged state, or cross-UF orchestration

## Why This Is the Better Model

1. Some UFs are naturally unit-testable.
   - Example:
     - `parse_execution_config`
     - `decode_state_bundle`
     - `restore_snapshot_state`
     - `compute_benchmark_metrics`
   - These have clear local inputs, outputs, and edge cases.
   - Their main correctness signal is local contract satisfaction.

2. Some UFs are only partially meaningful in isolation.
   - Example:
     - `assemble_execution_bundle`
     - `compose_step_result`
     - `package_snapshot_result`
     - `assemble_observation_batch`
     - `compose_evaluation_report`
   - These are aggregation/composition steps.
   - They can still have small guard-rail tests, but their real behavioral value appears only when fed valid chain outputs.

3. Some checks are fundamentally IF-level, not UF-level.
   - Example:
     - overall `60x` requirement for the active motion-model stack
     - deterministic snapshot capture -> restore -> control reinjection -> branch rollout behavior
     - observation schema backward compatibility through the full feature pipeline
     - evaluation priority ordering across benchmark + learning metrics + scope audit + manifest
   - These emerge from multiple UFs working together.

## Recommended Classification

### Category A: UF-local functional tests required

These should have direct unit tests with happy-path + edge-case coverage:

- IF-01
  - `UF-01-01 parse_execution_config`
  - `UF-01-02 inspect_hardware_profile`
  - `UF-01-03 synthesize_scenario`
  - `UF-01-04 size_rollout_batch`
- IF-02
  - `UF-02-01 decode_state_bundle`
  - `UF-02-02 propagate_ownship_6dof`
  - `UF-02-03 propagate_threat_kinematics`
  - `UF-02-04 propagate_target_environment`
  - `UF-02-05 apply_aero_calibration`
- IF-03
  - `UF-03-01 capture_snapshot_state`
  - `UF-03-02 restore_snapshot_state`
  - `UF-03-03 inject_control_sequence`
  - `UF-03-04 execute_branch_rollout`
  - `UF-03-05 verify_replay_consistency`
- IF-04
  - `UF-04-01 extract_vehicle_features`
  - `UF-04-02 extract_terrain_features`
  - `UF-04-03 extract_threat_features`
  - `UF-04-04 normalize_observation_features`
  - `UF-04-05 build_observation_masks`
- IF-05
  - `UF-05-01 collect_run_metadata`
  - `UF-05-02 compute_benchmark_metrics`
  - `UF-05-03 rank_learning_metrics`
  - `UF-05-04 audit_scope_exclusions`
  - `UF-05-05 build_reproducibility_manifest`

### Category B: UF guard-rail tests + IF-level functional validation

These should keep lightweight unit checks for validation/error handling, but their main functional test should be chain/integration based:

- `UF-01-05 assemble_execution_bundle`
- `UF-01-06 finalize_execution_bundle`
- `UF-02-06 compose_step_result`
- `UF-03-06 package_snapshot_result`
- `UF-04-06 assemble_observation_batch`
- `UF-05-06 compose_evaluation_report`

### Category C: IF-level acceptance only

These are not properties of a single UF and should be owned explicitly by IF tests:

- `IF-01`
  - active motion-model stack planning supports `>= 60x` estimated acceleration
  - deterministic seed is preserved end-to-end
- `IF-02`
  - full motion-model stack remains finite/stable through chained propagation
- `IF-03`
  - restore + control reinjection + branch rollout remain deterministic
- `IF-04`
  - final observation schema is stable and backward-compatible
- `IF-05`
  - metric priority order is `prediction error > latent rollout consistency > policy convergence`

## Implication for `uf.md`

`uf.md` should stop implying that every UF needs a fully separate end-to-end functional test file.

Instead, each UF block should declare:
- `Unit Verification`: local contract tests or guard-rail tests
- `Chain Verification`: parent IF test when the UF's behavioral meaning depends on composition

This will make the document match both:
- the actual implementation structure
- the real engineering meaning of the tests

## Recommended Rewrite Pattern

For composition-heavy UFs, the verification section should look like:

- Verification Plan:
    Unit:
      - validate missing dependency raises expected error
      - validate output schema assembly on minimal valid context
    Chain:
      - `tests/integration/test_ifXX_*.py::test_ifXX_*_acceptance`
    Coverage:
      - unit branch coverage on guards
      - functional acceptance owned by parent IF

## Judgment Rationale

- Forcing per-UF "full functional tests" on composition nodes creates fake precision and document drift.
- A verification plan is useful only when it reflects where correctness can actually be observed.
- The current implementation already hints at the right structure: most meaningful behavioral tests are grouped at IF level, while local guards are checked in unit tests.
- Therefore the clean fix is not merely renaming files; it is redefining verification ownership by granularity.

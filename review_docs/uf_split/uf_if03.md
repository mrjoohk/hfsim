# Unit Function Blocks

- UF-ID: UF-03-01
- Parent IF: IF-03
- Goal: capture immutable snapshot from runtime state
- I/O Contract:
    Input:  snapshot_rollout_request: SnapshotRolloutRequest, snapshot request + control metadata, valid schema
    Output: snapshot_payload: SnapshotPayload, serialized bytes + metadata fields, byte_length[1,10^9]
- Algorithm Summary:
    Snapshot capture: serialize visible state, hidden state, RNG state, and continuation metadata into immutable snapshot payload.
- Edge Cases:
    - runtime state handle is missing: raise `ValueError("runtime state required")`
    - serialized payload exceeds configured limit: raise `MemoryError`
    - non-serializable field is encountered: raise `TypeError` with field name
- Verification Plan:
    Unit:        tests/unit/test_capture_snapshot_state.py::test_serializes_runtime_state
                 tests/unit/test_capture_snapshot_state.py::test_missing_runtime_state_raises
                 tests/unit/test_capture_snapshot_state.py::test_oversized_payload_raises
    Integration: tests/integration/test_if03_snapshot.py::test_capture_snapshot_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-02
- Parent IF: IF-03
- Goal: restore deterministic runtime state from snapshot
- I/O Contract:
    Input:  snapshot_payload: SnapshotPayload, serialized bytes + metadata fields, byte_length[1,10^9]
    Output: restored_runtime_state: RestoredRuntimeState, mutable simulator runtime state, valid schema
- Algorithm Summary:
    Snapshot restore: deserialize snapshot payload, reconstruct hidden state, and rebind deterministic RNG and continuation context.
- Edge Cases:
    - snapshot checksum mismatch: raise `ValueError("corrupt snapshot")`
    - payload version is unsupported: raise `RuntimeError("snapshot version unsupported")`
    - deserialized state misses required RNG field: raise `ValueError("rng state missing")`
- Verification Plan:
    Unit:        tests/unit/test_restore_snapshot_state.py::test_restores_valid_snapshot
                 tests/unit/test_restore_snapshot_state.py::test_checksum_mismatch_raises
                 tests/unit/test_restore_snapshot_state.py::test_missing_rng_state_raises
    Integration: tests/integration/test_if03_snapshot.py::test_restore_snapshot_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-03
- Parent IF: IF-03
- Goal: inject control sequence into restored runtime
- I/O Contract:
    Input:  restored_runtime_state: RestoredRuntimeState, mutable simulator runtime state, valid schema
    Output: rollout_runtime_state: RolloutRuntimeState, runtime state + control sequence, horizon[1,10^6], control_range[-1,1]
- Algorithm Summary:
    Control attachment: validate control horizon and bind replay or counterfactual control sequence to restored runtime state.
- Edge Cases:
    - control sequence is empty: raise `ValueError("control sequence cannot be empty")`
    - control sequence contains NaN/Inf: raise `ValueError("non-finite control detected")`
    - horizon exceeds configured maximum: raise `ValueError` with requested horizon
- Verification Plan:
    Unit:        tests/unit/test_inject_control_sequence.py::test_attaches_valid_control_sequence
                 tests/unit/test_inject_control_sequence.py::test_empty_sequence_raises
                 tests/unit/test_inject_control_sequence.py::test_nonfinite_control_raises
    Integration: tests/integration/test_if03_snapshot.py::test_control_injection_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-04
- Parent IF: IF-03
- Goal: execute deterministic branch rollout
- I/O Contract:
    Input:  rollout_runtime_state: RolloutRuntimeState, runtime state + control sequence, horizon[1,10^6], control_range[-1,1]
    Output: branch_trajectory: BranchTrajectory, float64 trajectory tensors + event logs, shape=(H,...) finite range
- Algorithm Summary:
    Fixed-horizon rollout: iteratively step restored runtime with injected controls and record trajectory and event outputs.
- Edge Cases:
    - runtime state becomes non-finite mid-rollout: abort and raise `RuntimeError("branch rollout diverged")`
    - event log buffer exceeds configured capacity: grow within limit or raise `MemoryError`
    - rollout horizon is one step: return single-step trajectory of correct schema
- Verification Plan:
    Unit:        tests/unit/test_execute_branch_rollout.py::test_rolls_out_fixed_horizon
                 tests/unit/test_execute_branch_rollout.py::test_divergent_runtime_raises
                 tests/unit/test_execute_branch_rollout.py::test_single_step_horizon_is_supported
    Integration: tests/integration/test_if03_snapshot.py::test_branch_rollout_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-05
- Parent IF: IF-03
- Goal: verify replay consistency for branch trajectory
- I/O Contract:
    Input:  branch_trajectory: BranchTrajectory, float64 trajectory tensors + event logs, shape=(H,...) finite range
    Output: consistency_flags: ConsistencyFlags, boolean + scalar error metrics, deterministic range {0,1} and error>=0
- Algorithm Summary:
    Replay consistency check: compare repeated rollout outputs against deterministic tolerance and emit pass/fail flags with error metrics.
- Edge Cases:
    - reference trajectory is missing: raise `ValueError("reference trajectory required")`
    - event log lengths differ: set deterministic flag false and record mismatch count
    - tolerance config is negative: raise `ValueError("tolerance must be non-negative")`
- Verification Plan:
    Unit:        tests/unit/test_verify_replay_consistency.py::test_flags_identical_rollouts_as_consistent
                 tests/unit/test_verify_replay_consistency.py::test_missing_reference_raises
                 tests/unit/test_verify_replay_consistency.py::test_event_log_mismatch_is_reported
    Integration: tests/integration/test_if03_snapshot.py::test_replay_consistency_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-06
- Parent IF: IF-03
- Goal: package snapshot rollout result bundle
- I/O Contract:
    Input:  consistency_flags: ConsistencyFlags, boolean + scalar error metrics, deterministic range {0,1} and error>=0
    Output: snapshot_rollout_result: SnapshotRolloutResult, snapshot payload + trajectory + verification metadata, valid schema
- Algorithm Summary:
    Result packaging: combine snapshot payload, branch trajectory, and replay-consistency metadata into final service response.
- Edge Cases:
    - branch trajectory dependency is missing: raise `RuntimeError("branch_trajectory missing")`
    - snapshot payload dependency is missing: raise `RuntimeError("snapshot_payload missing")`
    - result serialization exceeds configured limit: raise `MemoryError`
- Verification Plan:
    Unit:        tests/unit/test_package_snapshot_result.py::test_packages_snapshot_rollout_result
                 tests/unit/test_package_snapshot_result.py::test_missing_branch_trajectory_raises
                 tests/unit/test_package_snapshot_result.py::test_missing_snapshot_payload_raises
    Integration: tests/integration/test_if03_snapshot.py::test_package_snapshot_result_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

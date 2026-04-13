# Unit Function Blocks

- UF-ID: UF-02-01
- Parent IF: IF-02
- Goal: decode step request into typed entity states
- I/O Contract:
    Input:  dynamics_step_request: DynamicsStepRequest, SI state + normalized control bundle, dt_internal(0.0005,0.02], agent_count[1,4]
    Output: entity_states: EntityStateSet, typed ownship/threat/target/environment states, finite numeric range
- Algorithm Summary:
    State decoding: unpack step request into typed entity-state views and validate unit and range consistency before propagation.
- Edge Cases:
    - dynamics_step_request is None: raise `ValueError("dynamics_step_request cannot be None")`
    - dt_internal is outside valid range: raise `ValueError` with supplied dt
    - any state tensor contains NaN/Inf: raise `ValueError("non-finite state detected")`
- Verification Plan:
    Unit:        tests/unit/test_decode_state_bundle.py::test_decodes_valid_step_request
                 tests/unit/test_decode_state_bundle.py::test_invalid_dt_raises
                 tests/unit/test_decode_state_bundle.py::test_nonfinite_state_raises
    Integration: tests/integration/test_if02_dynamics.py::test_decode_state_bundle_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-02
- Parent IF: IF-02
- Goal: propagate ownship 6-DoF state
- I/O Contract:
    Input:  entity_states: EntityStateSet, typed ownship/threat/target/environment states, finite numeric range
    Output: ownship_propagation_context: OwnshipPropagationContext, ownship next-state + shared entity references, valid schema
- Algorithm Summary:
    6-DoF rigid-body integration: compute force and moment derivatives from control and aero parameters, then advance translational and angular state.
- Edge Cases:
    - aerodynamic parameter table is missing: raise `ValueError("aero parameters required")`
    - quaternion norm collapses below tolerance: renormalize if >1e-9 else raise `RuntimeError`
    - control input exceeds [-1,1]: clip to range and log warning
- Verification Plan:
    Unit:        tests/unit/test_propagate_ownship_6dof.py::test_propagates_finite_state
                 tests/unit/test_propagate_ownship_6dof.py::test_missing_aero_params_raises
                 tests/unit/test_propagate_ownship_6dof.py::test_out_of_range_control_is_clipped
    Integration: tests/integration/test_if02_dynamics.py::test_ownship_propagation_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-03
- Parent IF: IF-02
- Goal: propagate threat and adversary kinematics
- I/O Contract:
    Input:  ownship_propagation_context: OwnshipPropagationContext, ownship next-state + shared entity references, valid schema
    Output: threat_propagation_context: ThreatPropagationContext, ownship + threat next-state references, valid schema
- Algorithm Summary:
    Threat propagation: advance active adversary and threat kinematic states using configured motion and engagement models.
- Edge Cases:
    - no active threats in entity_states: return empty `ThreatStateSet` of correct shape
    - threat speed is negative from prior state: clamp to zero and log warning
    - threat model id is unsupported: raise `NotImplementedError`
- Verification Plan:
    Unit:        tests/unit/test_propagate_threat_kinematics.py::test_propagates_active_threats
                 tests/unit/test_propagate_threat_kinematics.py::test_empty_threat_set_returns_empty
                 tests/unit/test_propagate_threat_kinematics.py::test_unknown_model_raises
    Integration: tests/integration/test_if02_dynamics.py::test_threat_propagation_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-04
- Parent IF: IF-02
- Goal: propagate target and environment state
- I/O Contract:
    Input:  threat_propagation_context: ThreatPropagationContext, ownship + threat next-state references, valid schema
    Output: environment_propagation_context: EnvironmentPropagationContext, ownship + threat + environment references, valid schema
- Algorithm Summary:
    Environment transition: advance targets, environment flags, and scenario-local transition variables required for the next step.
- Edge Cases:
    - target list is empty: return valid empty target set and preserve environment state
    - terrain grid reference is missing: raise `ValueError("terrain reference required")`
    - environment flag vector shape mismatch: raise `ValueError` with expected shape
- Verification Plan:
    Unit:        tests/unit/test_propagate_target_environment.py::test_propagates_environment_state
                 tests/unit/test_propagate_target_environment.py::test_empty_target_set_is_supported
                 tests/unit/test_propagate_target_environment.py::test_missing_terrain_reference_raises
    Integration: tests/integration/test_if02_dynamics.py::test_environment_propagation_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-05
- Parent IF: IF-02
- Goal: apply aerodynamic calibration overrides
- I/O Contract:
    Input:  environment_propagation_context: EnvironmentPropagationContext, ownship + threat + environment references, valid schema
    Output: aero_calibration_context: AeroCalibrationContext, calibrated ownship + merged dependency references, valid schema
- Algorithm Summary:
    Calibration overlay: evaluate configured coefficient overrides or reference-seeded corrections and apply them to the propagated ownship state.
- Edge Cases:
    - calibration config is absent: return pass-through calibrated state and log info
    - open-model seed contains missing coefficient keys: skip missing keys and log warning
    - calibrated state becomes non-finite: raise `RuntimeError("calibration divergence")`
- Verification Plan:
    Unit:        tests/unit/test_apply_aero_calibration.py::test_applies_configured_overrides
                 tests/unit/test_apply_aero_calibration.py::test_missing_calibration_config_is_passthrough
                 tests/unit/test_apply_aero_calibration.py::test_nonfinite_calibrated_state_raises
    Integration: tests/integration/test_if02_dynamics.py::test_aero_calibration_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-06
- Parent IF: IF-02
- Goal: compose next-step dynamics result bundle
- I/O Contract:
    Input:  aero_calibration_context: AeroCalibrationContext, calibrated ownship + merged dependency references, valid schema
    Output: dynamics_step_result: DynamicsStepResult, structured multi-entity state bundle, SI units + discrete flags, finite range
- Algorithm Summary:
    State composition: merge calibrated ownship state with threat and environment dependency outputs into a unified next-step bundle.
- Edge Cases:
    - dependent threat state is missing: raise `RuntimeError("threat_state_next missing")`
    - dependent environment state is missing: raise `RuntimeError("environment_state_next missing")`
    - merged bundle contains inconsistent batch dimensions: raise `ValueError("batch dimension mismatch")`
- Verification Plan:
    Unit:        tests/unit/test_compose_step_result.py::test_composes_valid_result_bundle
                 tests/unit/test_compose_step_result.py::test_missing_threat_state_raises
                 tests/unit/test_compose_step_result.py::test_batch_dimension_mismatch_raises
    Integration: tests/integration/test_if02_dynamics.py::test_compose_step_result_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

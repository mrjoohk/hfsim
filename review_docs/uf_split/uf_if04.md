# Unit Function Blocks

- UF-ID: UF-04-01
- Parent IF: IF-04
- Goal: extract vehicle state features
- I/O Contract:
    Input:  observation_request: ObservationRequest, structured simulator state + terrain/threat references, valid schema
    Output: vehicle_feature_context: VehicleFeatureContext, vehicle feature tensors + observation refs, valid schema
- Algorithm Summary:
    Vehicle feature extraction: read ownship and teammate state fields and project them into learner-facing feature vectors.
- Edge Cases:
    - observation_request is None: raise `ValueError("observation_request cannot be None")`
    - required vehicle state field is missing: raise `KeyError` with field name
    - input state contains NaN/Inf: replace with configured default and set mask bit
- Verification Plan:
    Unit:        tests/unit/test_extract_vehicle_features.py::test_extracts_vehicle_features
                 tests/unit/test_extract_vehicle_features.py::test_missing_field_raises
                 tests/unit/test_extract_vehicle_features.py::test_nonfinite_state_sets_mask
    Integration: tests/integration/test_if04_observation.py::test_vehicle_feature_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-02
- Parent IF: IF-04
- Goal: extract terrain-relative features
- I/O Contract:
    Input:  vehicle_feature_context: VehicleFeatureContext, vehicle feature tensors + observation refs, valid schema
    Output: terrain_feature_context: TerrainFeatureContext, vehicle + terrain feature tensors, valid schema
- Algorithm Summary:
    Terrain featurization: sample terrain and geometry context relative to each agent and encode it into fixed-width feature vectors.
- Edge Cases:
    - terrain source is absent: raise `ValueError("terrain source required")`
    - sampled terrain value is outside configured range: clip and log warning
    - agent position is outside terrain bounds: return boundary-safe default feature vector
- Verification Plan:
    Unit:        tests/unit/test_extract_terrain_features.py::test_extracts_terrain_features
                 tests/unit/test_extract_terrain_features.py::test_missing_terrain_source_raises
                 tests/unit/test_extract_terrain_features.py::test_out_of_bounds_position_returns_default
    Integration: tests/integration/test_if04_observation.py::test_terrain_feature_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-03
- Parent IF: IF-04
- Goal: extract threat-relative features
- I/O Contract:
    Input:  terrain_feature_context: TerrainFeatureContext, vehicle + terrain feature tensors, valid schema
    Output: threat_feature_context: ThreatFeatureContext, vehicle + terrain + threat feature tensors, valid schema
- Algorithm Summary:
    Threat featurization: encode nearby threat state, geometry, and availability into fixed-width threat feature vectors.
- Edge Cases:
    - no visible threats are present: return zero-valued feature vector with presence flag 0
    - threat reference shape mismatch: raise `ValueError("threat shape mismatch")`
    - threat count exceeds configured cap: keep top-k by configured priority and log warning
- Verification Plan:
    Unit:        tests/unit/test_extract_threat_features.py::test_extracts_visible_threats
                 tests/unit/test_extract_threat_features.py::test_no_visible_threats_returns_zero_vector
                 tests/unit/test_extract_threat_features.py::test_shape_mismatch_raises
    Integration: tests/integration/test_if04_observation.py::test_threat_feature_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-04
- Parent IF: IF-04
- Goal: normalize observation feature groups
- I/O Contract:
    Input:  threat_feature_context: ThreatFeatureContext, vehicle + terrain + threat feature tensors, valid schema
    Output: normalized_features: ObservationFeatureSet, float32 tensors shape=(B,A,F*), normalized range [-1,1] or [0,1]
- Algorithm Summary:
    Feature normalization: apply configured scaling, clipping, and concatenation rules to produce learner-safe observation features.
- Edge Cases:
    - scale configuration is missing: raise `ValueError("normalization config required")`
    - any feature magnitude exceeds clip bound: clip to configured bound and record metric
    - concatenated feature width differs from schema: raise `ValueError("feature width mismatch")`
- Verification Plan:
    Unit:        tests/unit/test_normalize_observation_features.py::test_normalizes_feature_ranges
                 tests/unit/test_normalize_observation_features.py::test_missing_scale_config_raises
                 tests/unit/test_normalize_observation_features.py::test_feature_width_mismatch_raises
    Integration: tests/integration/test_if04_observation.py::test_normalization_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-05
- Parent IF: IF-04
- Goal: build observation validity masks
- I/O Contract:
    Input:  normalized_features: ObservationFeatureSet, float32 tensors shape=(B,A,F*), normalized range [-1,1] or [0,1]
    Output: observation_assembly_context: ObservationAssemblyContext, normalized features + mask tensors, valid schema
- Algorithm Summary:
    Mask generation: derive channel-validity and availability masks from feature presence, gating, and fallback usage.
- Edge Cases:
    - normalized_features tensor is empty: return valid zero-mask context of expected shape
    - mask width config mismatches feature schema: raise `ValueError("mask width mismatch")`
    - mask contains non-binary value after computation: cast to {0,1} and log warning
- Verification Plan:
    Unit:        tests/unit/test_build_observation_masks.py::test_builds_binary_masks
                 tests/unit/test_build_observation_masks.py::test_empty_threat_features_returns_zero_masks
                 tests/unit/test_build_observation_masks.py::test_mask_width_mismatch_raises
    Integration: tests/integration/test_if04_observation.py::test_mask_generation_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-06
- Parent IF: IF-04
- Goal: assemble backward-compatible observation batch
- I/O Contract:
    Input:  observation_assembly_context: ObservationAssemblyContext, normalized features + mask tensors, valid schema
    Output: observation_batch: ObservationBatch, feature tensors + masks + extension hooks, valid schema
- Algorithm Summary:
    Observation assembly: package normalized features with masks and optional extension slots into the stable observation API.
- Edge Cases:
    - mask dependency is missing: raise `RuntimeError("observation_masks missing")`
    - extension hook key conflicts with reserved field: raise `ValueError("reserved extension key")`
    - output schema version is unsupported by config: raise `RuntimeError("unsupported observation schema version")`
- Verification Plan:
    Unit:        tests/unit/test_assemble_observation_batch.py::test_assembles_observation_batch
                 tests/unit/test_assemble_observation_batch.py::test_missing_mask_dependency_raises
                 tests/unit/test_assemble_observation_batch.py::test_reserved_extension_key_raises
    Integration: tests/integration/test_if04_observation.py::test_observation_assembly_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

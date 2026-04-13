# Unit Function Blocks

This document uses verification ownership rather than assuming every UF must have a standalone full functional test.

- `Unit Verification`: local contract, edge-case, and guard-rail checks
- `Chain Verification`: parent IF integration or acceptance check
- `Ownership`: where the main behavioral correctness is observed

## IF-01

- UF-ID: UF-01-01
- Parent IF: IF-01
- Goal: parse execution request into normalized config
- I/O Contract:
    Input: `ExecutionRequest`
    Output: `NormalizedExecutionRequest`
- Algorithm Summary:
    Validate required fields, normalize ranges, and canonicalize execution options.
- Edge Cases:
    - `execution_request is None`
    - missing scenario or run id
    - out-of-range `agent_count` or `curriculum_level`
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if01_orchestration.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if01_orchestration.py::test_if01_execution_bundle_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-02
- Parent IF: IF-01
- Goal: inspect local hardware and derive resource budget
- I/O Contract:
    Input: `NormalizedExecutionRequest`
    Output: `HardwareInspectionContext`
- Algorithm Summary:
    Inspect CPU, RAM, and GPU profile and derive safe execution budgets.
- Edge Cases:
    - GPU unavailable
    - invalid memory report
    - unsupported accelerator type
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if01_orchestration.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if01_orchestration.py::test_if01_execution_bundle_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-03
- Parent IF: IF-01
- Goal: synthesize seeded training scenario
- I/O Contract:
    Input: `HardwareInspectionContext`
    Output: `ScenarioPlanningContext`
- Algorithm Summary:
    Generate deterministic learnability-first scenario from seed and curriculum controls.
- Edge Cases:
    - invalid seed
    - missing curriculum policy
    - rare-case request in baseline mode
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if01_orchestration.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if01_orchestration.py::test_if01_execution_bundle_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-04
- Parent IF: IF-01
- Goal: size rollout batch for available resources
- I/O Contract:
    Input: `ScenarioPlanningContext`
    Output: `RolloutSizingContext`
- Algorithm Summary:
    Estimate rollout footprint for the active motion-model stack and choose safe parallelism.
- Edge Cases:
    - single rollout exceeds budget
    - CPU-only fallback
    - invalid sizing estimate
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if01_orchestration.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if01_orchestration.py::test_if01_execution_bundle_acceptance`
    Ownership:
      - UF-local sizing verification plus IF-01 `>= 60x` acceptance
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-05
- Parent IF: IF-01
- Goal: assemble partial execution bundle from scenario
- I/O Contract:
    Input: `RolloutSizingContext`
    Output: `PartialExecutionBundle`
- Algorithm Summary:
    Package scenario metadata, benchmark mode, seed, and rollout shell into partial execution state.
- Edge Cases:
    - missing scenario id
    - agent-count mismatch
    - serialization overflow
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if01_orchestration.py`
    Chain Verification:
      - `tests/integration/test_if01_orchestration.py::test_if01_execution_bundle_acceptance`
    Ownership:
      - parent IF chain functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-06
- Parent IF: IF-01
- Goal: finalize simulator-ready execution bundle
- I/O Contract:
    Input: `PartialExecutionBundle`
    Output: `ExecutionBundle`
- Algorithm Summary:
    Merge partial execution bundle and rollout plan into deterministic simulator-ready payload.
- Edge Cases:
    - rollout plan missing
    - checksum mismatch
    - budget overflow
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if01_orchestration.py`
    Chain Verification:
      - `tests/integration/test_if01_orchestration.py::test_if01_execution_bundle_acceptance`
    Ownership:
      - parent IF chain functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

## IF-02

- UF-ID: UF-02-01
- Parent IF: IF-02
- Goal: decode step request into typed entity states
- I/O Contract:
    Input: `DynamicsStepRequest`
    Output: `EntityStateSet`
- Algorithm Summary:
    Validate step request and unpack typed ownship, threat, target, and environment state.
- Edge Cases:
    - request is None
    - invalid `dt_internal`
    - non-finite state values
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-02
- Parent IF: IF-02
- Goal: propagate ownship 6-DoF state
- I/O Contract:
    Input: `EntityStateSet`
    Output: `OwnshipPropagationContext`
- Algorithm Summary:
    Advance simplified 6-DoF ownship state from control input and aerodynamic parameters.
- Edge Cases:
    - missing aero parameters
    - quaternion collapse
    - out-of-range control
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local dynamics verification plus IF-02 stability acceptance
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-03
- Parent IF: IF-02
- Goal: propagate threat and adversary kinematics
- I/O Contract:
    Input: `OwnshipPropagationContext`
    Output: `ThreatPropagationContext`
- Algorithm Summary:
    Advance active threat kinematics with configured motion model.
- Edge Cases:
    - no active threats
    - negative speed state
    - unsupported threat model
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-04
- Parent IF: IF-02
- Goal: propagate target and environment state
- I/O Contract:
    Input: `ThreatPropagationContext`
    Output: `EnvironmentPropagationContext`
- Algorithm Summary:
    Advance targets and scenario-local environment transition state.
- Edge Cases:
    - empty target list
    - missing terrain reference
    - environment-shape mismatch
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-05
- Parent IF: IF-02
- Goal: apply aerodynamic calibration overrides
- I/O Contract:
    Input: `EnvironmentPropagationContext`
    Output: `AeroCalibrationContext`
- Algorithm Summary:
    Apply calibration overlay or reference-seeded coefficient adjustment.
- Edge Cases:
    - missing calibration config
    - incomplete open-model seed
    - non-finite calibrated state
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local calibration verification plus IF-02 stability acceptance
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-02-06
- Parent IF: IF-02
- Goal: compose next-step dynamics result bundle
- I/O Contract:
    Input: `AeroCalibrationContext`
    Output: `DynamicsStepResult`
- Algorithm Summary:
    Merge calibrated ownship, threat, target, and environment outputs into next-step result bundle.
- Edge Cases:
    - missing threat dependency
    - missing environment dependency
    - batch-dimension mismatch
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if02_dynamics.py`
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - parent IF chain functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

## IF-03

- UF-ID: UF-03-01
- Parent IF: IF-03
- Goal: capture immutable snapshot from runtime state
- I/O Contract:
    Input: `SnapshotRolloutRequest`
    Output: `SnapshotPayload`
- Algorithm Summary:
    Serialize visible state, hidden state, RNG state, and continuation metadata into immutable payload.
- Edge Cases:
    - missing runtime state
    - oversized payload
    - non-serializable field
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if03_snapshot.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if03_snapshot.py::test_if03_snapshot_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-02
- Parent IF: IF-03
- Goal: restore deterministic runtime state from snapshot
- I/O Contract:
    Input: `SnapshotPayload`
    Output: `RestoredRuntimeState`
- Algorithm Summary:
    Validate snapshot payload and reconstruct deterministic runtime state.
- Edge Cases:
    - checksum mismatch
    - unsupported version
    - missing RNG state
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if03_snapshot.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if03_snapshot.py::test_if03_snapshot_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-03
- Parent IF: IF-03
- Goal: inject control sequence into restored runtime
- I/O Contract:
    Input: `RestoredRuntimeState`
    Output: `RolloutRuntimeState`
- Algorithm Summary:
    Attach validated control sequence and fixed horizon to restored runtime.
- Edge Cases:
    - empty control sequence
    - non-finite control
    - invalid horizon
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if03_snapshot.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if03_snapshot.py::test_if03_snapshot_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-04
- Parent IF: IF-03
- Goal: execute deterministic branch rollout
- I/O Contract:
    Input: `RolloutRuntimeState`
    Output: `BranchTrajectory`
- Algorithm Summary:
    Run fixed-horizon deterministic branch rollout from restored runtime state.
- Edge Cases:
    - non-finite runtime during rollout
    - event-log overflow
    - single-step horizon
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if03_snapshot.py`
      - local contract ownership: medium
    Chain Verification:
      - `tests/integration/test_if03_snapshot.py::test_if03_snapshot_acceptance`
    Ownership:
      - mixed UF-local verification and IF-03 deterministic acceptance
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-05
- Parent IF: IF-03
- Goal: verify replay consistency for branch trajectory
- I/O Contract:
    Input: `BranchTrajectory`
    Output: `ConsistencyFlags`
- Algorithm Summary:
    Compare replay result against reference within deterministic tolerance.
- Edge Cases:
    - missing reference trajectory
    - event-log length mismatch
    - negative tolerance
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if03_snapshot.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if03_snapshot.py::test_if03_snapshot_acceptance`
    Ownership:
      - mixed UF-local verification and IF-03 deterministic acceptance
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-03-06
- Parent IF: IF-03
- Goal: package snapshot rollout result bundle
- I/O Contract:
    Input: `ConsistencyFlags`
    Output: `SnapshotRolloutResult`
- Algorithm Summary:
    Package snapshot payload, branch trajectory, and replay-consistency metadata.
- Edge Cases:
    - missing branch trajectory
    - missing snapshot payload
    - result-size overflow
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if03_snapshot.py`
    Chain Verification:
      - `tests/integration/test_if03_snapshot.py::test_if03_snapshot_acceptance`
    Ownership:
      - parent IF chain functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

## IF-04

- UF-ID: UF-04-01
- Parent IF: IF-04
- Goal: extract vehicle state features
- I/O Contract:
    Input: `ObservationRequest`
    Output: `VehicleFeatureContext`
- Algorithm Summary:
    Project ownship and teammate state into learner-facing vehicle features.
- Edge Cases:
    - request is None
    - missing required vehicle field
    - non-finite input state
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-02
- Parent IF: IF-04
- Goal: extract terrain-relative features
- I/O Contract:
    Input: `VehicleFeatureContext`
    Output: `TerrainFeatureContext`
- Algorithm Summary:
    Encode relative terrain and geometry context into fixed-width terrain features.
- Edge Cases:
    - missing terrain source
    - sampled terrain out of range
    - out-of-bounds position
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-03
- Parent IF: IF-04
- Goal: extract threat-relative features
- I/O Contract:
    Input: `TerrainFeatureContext`
    Output: `ThreatFeatureContext`
- Algorithm Summary:
    Encode nearby threat geometry and availability into fixed-width threat features.
- Edge Cases:
    - no visible threats
    - threat-shape mismatch
    - threat count exceeds cap
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-04
- Parent IF: IF-04
- Goal: normalize observation feature groups
- I/O Contract:
    Input: `ThreatFeatureContext`
    Output: `ObservationFeatureSet`
- Algorithm Summary:
    Scale, clip, and concatenate feature groups into learner-safe normalized features.
- Edge Cases:
    - missing normalization context
    - clip-bound exceedance
    - feature-width mismatch
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-05
- Parent IF: IF-04
- Goal: build observation validity masks
- I/O Contract:
    Input: `ObservationFeatureSet`
    Output: `ObservationAssemblyContext`
- Algorithm Summary:
    Derive availability and validity masks from normalized feature content.
- Edge Cases:
    - empty normalized features
    - mask-width mismatch
    - non-binary mask result
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-04-06
- Parent IF: IF-04
- Goal: assemble backward-compatible observation batch
- I/O Contract:
    Input: `ObservationAssemblyContext`
    Output: `ObservationBatch`
- Algorithm Summary:
    Package normalized features, masks, and extension hooks into stable observation schema.
- Edge Cases:
    - missing mask dependency
    - reserved extension key
    - unsupported schema version
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if04_observation.py`
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - parent IF chain functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

## IF-05

- UF-ID: UF-05-01
- Parent IF: IF-05
- Goal: collect reproducibility metadata
- I/O Contract:
    Input: `EvaluationRequest`
    Output: `EvaluationMetadataContext`
- Algorithm Summary:
    Extract reproducibility-critical metadata into manifest-ready normalized form.
- Edge Cases:
    - missing revision
    - missing hardware profile
    - duplicate seed names
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-02
- Parent IF: IF-05
- Goal: compute benchmark and acceleration metrics
- I/O Contract:
    Input: `EvaluationMetadataContext`
    Output: `BenchmarkMetricsContext`
- Algorithm Summary:
    Compute benchmark counters including time-acceleration metric.
- Edge Cases:
    - zero wall-clock time
    - negative sim time
    - missing benchmark counter
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local functional verification plus IF-05 reporting acceptance
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-03
- Parent IF: IF-05
- Goal: rank learning metrics by validation priority
- I/O Contract:
    Input: `BenchmarkMetricsContext`
    Output: `RankingContext`
- Algorithm Summary:
    Rank learning metrics as prediction error, latent consistency, then policy convergence.
- Edge Cases:
    - missing prediction metrics
    - unknown metric group
    - duplicate priority key
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local functional verification plus IF-05 ordering acceptance
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-04
- Parent IF: IF-05
- Goal: audit phase-one scope exclusions
- I/O Contract:
    Input: `RankingContext`
    Output: `ScopeAuditContext`
- Algorithm Summary:
    Compare declared features against phase-one exclusions and emit findings.
- Edge Cases:
    - missing feature plan
    - duplicate excluded feature
    - unknown feature token
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-05
- Parent IF: IF-05
- Goal: build reproducibility manifest
- I/O Contract:
    Input: `ScopeAuditContext`
    Output: `ReportAssemblyContext`
- Algorithm Summary:
    Build stable reproducibility manifest from normalized metadata.
- Edge Cases:
    - unwritable serialization target
    - empty required field
    - unsupported manifest schema
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
      - local contract ownership: high
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local functional verification plus IF-05 reporting acceptance
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-06
- Parent IF: IF-05
- Goal: compose final evaluation report bundle
- I/O Contract:
    Input: `ReportAssemblyContext`
    Output: `EvaluationReportBundle`
- Algorithm Summary:
    Compose ranked metrics, benchmark, scope audit, and manifest into final report bundle.
- Edge Cases:
    - missing benchmark metrics
    - missing scope audit
    - artifact-size overflow
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if05_reporting.py`
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - parent IF chain functional verification
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

## I/O Chain Continuity Check

- IF-01: `ExecutionRequest -> NormalizedExecutionRequest -> HardwareInspectionContext -> ScenarioPlanningContext -> RolloutSizingContext -> PartialExecutionBundle -> ExecutionBundle`
- IF-02: `DynamicsStepRequest -> EntityStateSet -> OwnshipPropagationContext -> ThreatPropagationContext -> EnvironmentPropagationContext -> AeroCalibrationContext -> DynamicsStepResult`
- IF-03: `SnapshotRolloutRequest -> SnapshotPayload -> RestoredRuntimeState -> RolloutRuntimeState -> BranchTrajectory -> ConsistencyFlags -> SnapshotRolloutResult`
- IF-04: `ObservationRequest -> VehicleFeatureContext -> TerrainFeatureContext -> ThreatFeatureContext -> ObservationFeatureSet -> ObservationAssemblyContext -> ObservationBatch`
- IF-05: `EvaluationRequest -> EvaluationMetadataContext -> BenchmarkMetricsContext -> RankingContext -> ScopeAuditContext -> ReportAssemblyContext -> EvaluationReportBundle`

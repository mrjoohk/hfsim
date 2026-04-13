# Unit Function Blocks

- UF-ID: UF-01-01
- Parent IF: IF-01
- Goal: parse execution request into normalized config
- I/O Contract:
    Input:  execution_request: ExecutionRequest, dimensionless + SI mixed fields, valid experiment schema
    Output: normalized_request: NormalizedExecutionRequest, dimensionless + SI normalized fields, valid schema
- Algorithm Summary:
    Schema normalization: validate required keys, fill defaults, normalize units and enum values into canonical execution config.
- Edge Cases:
    - execution_request is None: raise `ValueError("execution_request cannot be None")`
    - missing required benchmark/scenario field: raise `ValueError` with missing key name
    - out-of-range agent_count or curriculum_level: clip to configured bounds and log warning
- Verification Plan:
    Unit:        tests/unit/test_parse_execution_config.py::test_normalizes_valid_request
                 tests/unit/test_parse_execution_config.py::test_none_request_raises
                 tests/unit/test_parse_execution_config.py::test_out_of_range_values_are_clipped
    Integration: tests/integration/test_if01_orchestration.py::test_parse_execution_config_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-02
- Parent IF: IF-01
- Goal: inspect local hardware and derive resource budget
- I/O Contract:
    Input:  normalized_request: NormalizedExecutionRequest, dimensionless + SI normalized fields, valid schema
    Output: hardware_inspection_context: HardwareInspectionContext, normalized config + hardware budget fields, valid schema
- Algorithm Summary:
    Hardware inspection: query CPU/RAM/GPU capacities and compute safe execution ceilings using configured memory utilization caps.
- Edge Cases:
    - GPU query fails: return CPU-only budget with `gpu_enabled=false`
    - reported RAM or VRAM is zero: raise `RuntimeError("invalid hardware profile")`
    - unsupported accelerator type: ignore device and log warning
- Verification Plan:
    Unit:        tests/unit/test_inspect_hardware_profile.py::test_builds_gpu_budget
                 tests/unit/test_inspect_hardware_profile.py::test_gpu_query_failure_falls_back_to_cpu
                 tests/unit/test_inspect_hardware_profile.py::test_zero_memory_raises
    Integration: tests/integration/test_if01_orchestration.py::test_hardware_budget_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-03
- Parent IF: IF-01
- Goal: synthesize seeded training scenario
- I/O Contract:
    Input:  hardware_inspection_context: HardwareInspectionContext, normalized config + hardware budget fields, valid schema
    Output: scenario_planning_context: ScenarioPlanningContext, scenario fields + hardware hints, valid schema
- Algorithm Summary:
    Seeded scenario synthesis: apply curriculum policy, difficulty controls, and deterministic randomization to build a learnability-first scenario.
- Edge Cases:
    - seed is outside valid range: replace with bounded deterministic seed and log warning
    - curriculum policy is missing: use baseline difficulty policy
    - rare_case_injection requested at baseline mode: disable rare cases and log info
- Verification Plan:
    Unit:        tests/unit/test_synthesize_scenario.py::test_same_seed_generates_same_scenario
                 tests/unit/test_synthesize_scenario.py::test_missing_policy_uses_baseline
                 tests/unit/test_synthesize_scenario.py::test_baseline_disables_rare_cases
    Integration: tests/integration/test_if01_orchestration.py::test_scenario_synthesis_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-04
- Parent IF: IF-01
- Goal: size rollout batch for available resources
- I/O Contract:
    Input:  scenario_planning_context: ScenarioPlanningContext, scenario fields + hardware hints, valid schema
    Output: rollout_sizing_context: RolloutSizingContext, scenario metadata + rollout plan fields, valid schema
- Algorithm Summary:
    Resource sizing: estimate per-rollout memory and compute cost for the active motion-model stack and choose a safe parallel batch size.
- Edge Cases:
    - estimated rollout footprint exceeds budget for one rollout: raise `MemoryError`
    - GPU budget unavailable: compute CPU-only rollout plan
    - negative or NaN estimate term: raise `ValueError("invalid sizing estimate")`
- Verification Plan:
    Unit:        tests/unit/test_size_rollout_batch.py::test_sizes_within_budget
                 tests/unit/test_size_rollout_batch.py::test_cpu_only_plan_is_supported
                 tests/unit/test_size_rollout_batch.py::test_oversized_single_rollout_raises
    Integration: tests/integration/test_if01_orchestration.py::test_rollout_sizing_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-05
- Parent IF: IF-01
- Goal: assemble partial execution bundle from scenario
- I/O Contract:
    Input:  rollout_sizing_context: RolloutSizingContext, scenario metadata + rollout plan fields, valid schema
    Output: partial_bundle: PartialExecutionBundle, structured scenario package, valid schema
- Algorithm Summary:
    Bundle assembly: package scenario state, metadata, benchmark flags, and agent configuration into an execution bundle shell.
- Edge Cases:
    - scenario metadata is missing required id: raise `ValueError("scenario_id required")`
    - agent_count mismatches scenario layout: raise `ValueError` with expected vs actual count
    - scenario payload exceeds configured serialization limit: raise `MemoryError`
- Verification Plan:
    Unit:        tests/unit/test_assemble_execution_bundle.py::test_packages_valid_scenario
                 tests/unit/test_assemble_execution_bundle.py::test_missing_scenario_id_raises
                 tests/unit/test_assemble_execution_bundle.py::test_agent_count_mismatch_raises
    Integration: tests/integration/test_if01_orchestration.py::test_partial_bundle_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-01-06
- Parent IF: IF-01
- Goal: finalize simulator-ready execution bundle
- I/O Contract:
    Input:  partial_bundle: PartialExecutionBundle, structured scenario package, valid schema
    Output: execution_bundle: ExecutionBundle, structured scenario + rollout plan object, valid schema
- Algorithm Summary:
    Final bundle merge: join partial execution package with rollout plan and emit deterministic simulator-ready execution bundle.
- Edge Cases:
    - rollout plan is absent from dependency context: raise `RuntimeError("rollout_plan missing")`
    - partial bundle checksum mismatch: raise `ValueError("bundle integrity failure")`
    - merged memory budget exceeds hardware cap: raise `MemoryError`
- Verification Plan:
    Unit:        tests/unit/test_finalize_execution_bundle.py::test_merges_partial_bundle_and_plan
                 tests/unit/test_finalize_execution_bundle.py::test_missing_rollout_plan_raises
                 tests/unit/test_finalize_execution_bundle.py::test_budget_overflow_raises
    Integration: tests/integration/test_if01_orchestration.py::test_finalize_execution_bundle_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

# Requirements

## Functional Requirements

### 6-DoF Vehicle Dynamics Core
- ID: REQ-001
- Title: Implement simplified 6-DoF rigid-body flight dynamics
- Context: 월드모델이 고속 기동과 자세 변화를 포함한 비행 동역학을 학습하려면 내부 시뮬레이터가 6-DoF 상태 전이를 일관되게 생성해야 한다.
- Inputs:
    control_input: float vector, normalized command, range [-1.0, 1.0] per channel
    dt_internal: float, second, range (0.0005, 0.02]
    vehicle_params: structured config, dimensionless + SI mixed units, predefined schema range
- Outputs:
    vehicle_state: float vector, SI units, finite state range defined by config
    state_derivatives: float vector, SI units per second, finite range
- Constraints:
    Must use 6-DoF state propagation.
    Must remain numerically stable for at least 600 simulated seconds without NaN/Inf.
    Must support parameterized aerodynamic coefficient configuration.
- Acceptance Criteria:
    Given a valid vehicle parameter set and a constant control sequence for 600 simulated seconds,
    When the dynamics core is stepped with `dt_internal <= 0.02 s`,
    Then `100%` of states and derivatives shall remain finite with `0` NaN/Inf occurrences.
    Given identical initial state, seed, and control sequence,
    When the same rollout is executed twice,
    Then the maximum absolute difference between corresponding state elements shall be `<= 1e-6`.
- Tests:
    Unit:        tests/unit/test_dynamics_6dof.py
    Integration: tests/integration/test_dynamics_6dof_integration.py
    E2E:         tests/e2e/test_dynamics_6dof_e2e.py
- Evidence:
    reports/dynamics_6dof/
    evidence_pack/dynamics_6dof/

### Snapshot Restore and Control Reinjection
- ID: REQ-002
- Title: Support arbitrary-time snapshot capture, restore, and branch rollout
- Context: 월드모델 학습과 counterfactual 비교를 위해 임의 시점 상태를 저장하고, 이후 다른 조종 입력을 다시 주입해 미래 궤적을 분기할 수 있어야 한다.
- Inputs:
    snapshot_request_time: int, simulation step index, range [0, 10^9]
    control_sequence: float tensor, normalized command, range [-1.0, 1.0]
    snapshot_payload: serialized state object, bytes, non-empty valid schema
- Outputs:
    snapshot_payload: serialized state object, bytes, non-empty valid schema
    branch_rollout: structured trajectory, SI units + discrete flags, horizon [1, 10^6] steps
- Constraints:
    Snapshot must contain control-relevant hidden state, RNG state, and environment continuation state.
    Restore and branch rollout must be deterministic.
    Snapshot save/restore overhead must not reduce benchmark time acceleration below `60x` on the reference scenario.
- Acceptance Criteria:
    Given a saved snapshot at time `t_k`, a fixed seed, and a control sequence of horizon `H = 256`,
    When the simulator restores the snapshot and rolls out the sequence twice,
    Then the two trajectories shall match with maximum absolute state error `<= 1e-6` and identical discrete event logs.
    Given a saved snapshot at time `t_k` and two different control sequences,
    When branch rollout is executed from the same snapshot for `H = 128`,
    Then the simulator shall produce `2` distinct trajectory objects without mutating the original snapshot.
- Tests:
    Unit:        tests/unit/test_snapshot_branching.py
    Integration: tests/integration/test_snapshot_branching_integration.py
    E2E:         tests/e2e/test_snapshot_branching_e2e.py
- Evidence:
    reports/snapshot_branching/
    evidence_pack/snapshot_branching/

### Hardware-Adaptive Rollout Scheduling
- ID: REQ-003
- Title: Auto-size rollout parallelism based on available machine resources
- Context: 병렬 rollout 수와 env step throughput은 PC 사양에 따라 달라지므로, 단일 고정값이 아니라 하드웨어 상태에 맞는 안전한 병렬도를 자동 산정해야 한다.
- Inputs:
    hardware_profile: structured system info, CPU cores / RAM / GPU VRAM, machine-local range
    scenario_profile: structured config, agents / horizon / observation schema, predefined valid range
- Outputs:
    rollout_plan: structured config, integer counts and memory budget, valid finite range
    resource_report: structured log, percentage and absolute units, valid schema
- Constraints:
    Auto-sizing must complete within `30 s`.
    Planned RAM usage must be `<= 85%` of available RAM.
    Planned VRAM usage, when GPU is enabled, must be `<= 90%` of available VRAM.
    Auto-sizing must account for the full active motion-model stack of the benchmark scenario.
- Acceptance Criteria:
    Given a valid hardware profile and scenario profile,
    When rollout auto-sizing is executed,
    Then the system shall emit a valid rollout plan and resource report within `30 s`.
    Given a generated rollout plan,
    When the simulator initializes the environment batch,
    Then initialization shall complete with `0` out-of-memory failures on the target machine.
- Tests:
    Unit:        tests/unit/test_rollout_autosize.py
    Integration: tests/integration/test_rollout_autosize_integration.py
    E2E:         tests/e2e/test_rollout_autosize_e2e.py
- Evidence:
    reports/rollout_autosize/
    evidence_pack/rollout_autosize/

### Time Acceleration Benchmark
- ID: REQ-004
- Title: Achieve minimum 60x simulation time acceleration on the reference scenario
- Context: 학습 가능성을 빠르게 검증하려면 단일 머신에서도 충분한 시뮬레이션 시간 배속이 확보되어야 한다.
- Inputs:
    benchmark_scenario: structured config, 4 agents and structured observations, predefined valid range
    benchmark_duration: float, simulated second, range [60, 3600]
- Outputs:
    acceleration_report: structured metrics, x-real-time ratio, range [0, +inf)
- Constraints:
    Reference benchmark shall use 4 agents.
    Observation mode shall be state vector + terrain/threat features only.
    Benchmark shall include all active motion models required by the reference scenario, including 6-DoF ownship dynamics, threat kinematics, target/environment transitions, and snapshot/state-management overhead.
    Logging level shall not exceed configured benchmark mode.
- Acceptance Criteria:
    Given the reference benchmark scenario and benchmark mode configuration,
    When the simulator runs for at least `600` simulated seconds,
    Then the measured simulation-time-to-wall-clock ratio for the full active motion-model stack shall be `>= 60.0`.
- Tests:
    Unit:        tests/unit/test_time_acceleration_metrics.py
    Integration: tests/integration/test_time_acceleration_integration.py
    E2E:         tests/e2e/test_time_acceleration_e2e.py
- Evidence:
    reports/time_acceleration/
    evidence_pack/time_acceleration/

### Structured Observation Interface
- ID: REQ-005
- Title: Provide structured observations with terrain and threat features
- Context: 초기 월드모델 검증에서는 상태벡터 기반 관측이 가장 효율적이므로, 기본 관측은 구조화 feature로 제공되어야 한다.
- Inputs:
    sim_state: structured state object, SI units + flags, valid schema
    terrain_map: structured feature source, normalized or SI units, valid schema
    threat_state: structured feature source, SI units + categorical flags, valid schema
- Outputs:
    observation_vector: float vector, normalized feature units, finite range
    observation_mask: binary vector, {0,1}, valid length range
- Constraints:
    Observation must include vehicle state, relative terrain features, and threat features.
    Observation output must be extensible to future image/virtual sensor channels without breaking the base API.
- Acceptance Criteria:
    Given a valid simulator state for `4` agents,
    When observations are generated,
    Then `100%` of returned observation vectors shall contain only finite numeric values and valid masks.
    Given the base structured observation API,
    When an image or virtual sensor channel is added in a backward-compatible extension,
    Then existing structured observation consumers shall require `0` mandatory field changes.
- Tests:
    Unit:        tests/unit/test_structured_observation.py
    Integration: tests/integration/test_structured_observation_integration.py
    E2E:         tests/e2e/test_structured_observation_e2e.py
- Evidence:
    reports/structured_observation/
    evidence_pack/structured_observation/

### Learnability-First Scenario Generation
- ID: REQ-006
- Title: Generate curriculum-oriented scenarios for world-model learning validation
- Context: 이번 단계의 목적은 현실성 최대화가 아니라 월드모델 학습 성공 검증이므로, 시나리오 생성은 learnability-first 원칙을 따라야 한다.
- Inputs:
    scenario_seed: int, dimensionless, range [0, 2^31-1]
    curriculum_level: int, dimensionless, range [0, 10]
    scenario_policy: structured config, categorical + numeric fields, valid schema
- Outputs:
    scenario_instance: structured scenario object, valid schema
    scenario_metadata: structured log, curriculum and difficulty metrics, valid schema
- Constraints:
    Scenario generator must support reproducible seeded generation.
    Difficulty must be controllable by curriculum level.
    Rare/extreme cases must be injectable but disabled by default at baseline level.
- Acceptance Criteria:
    Given the same seed, curriculum level, and policy configuration,
    When scenario generation is executed twice,
    Then the resulting scenario instance hashes shall be identical in `100%` of matched fields.
    Given curriculum levels `0` and `5`,
    When `100` scenarios are generated for each level,
    Then the average configured threat/event difficulty score at level `5` shall be at least `20%` higher than at level `0`.
- Tests:
    Unit:        tests/unit/test_scenario_curriculum.py
    Integration: tests/integration/test_scenario_curriculum_integration.py
    E2E:         tests/e2e/test_scenario_curriculum_e2e.py
- Evidence:
    reports/scenario_curriculum/
    evidence_pack/scenario_curriculum/

### Four-Agent Mission Baseline
- ID: REQ-007
- Title: Support 4-agent baseline missions with shared-environment execution
- Context: 초기 멀티에이전트 학습 검증은 4기 편대를 기본 단위로 수행해야 한다.
- Inputs:
    agent_count: int, count, range [1, 4]
    shared_env_config: structured config, valid schema
- Outputs:
    multi_agent_state: structured batch state, SI units + flags, valid schema
    episode_status: structured metrics and flags, valid schema
- Constraints:
    The simulator must support 1, 2, and 4 agents in one codebase.
    Four-agent execution is the default benchmark and validation mode.
- Acceptance Criteria:
    Given `agent_count = 4` and a valid shared environment configuration,
    When the environment is reset and stepped for `1000` steps,
    Then the simulator shall complete the run with agent indexing errors `<= 0` and invalid cross-agent references `<= 0`.
- Tests:
    Unit:        tests/unit/test_multi_agent_baseline.py
    Integration: tests/integration/test_multi_agent_baseline_integration.py
    E2E:         tests/e2e/test_multi_agent_baseline_e2e.py
- Evidence:
    reports/multi_agent_baseline/
    evidence_pack/multi_agent_baseline/

### Aerodynamic Coefficient Calibration Support
- ID: REQ-008
- Title: Provide a tunable aerodynamic coefficient configuration and calibration workflow
- Context: 정밀 공력 계수 튜닝을 이번 단계에 완전 검증 수준으로 끝내기는 어렵지만, 향후 개선 가능한 구조와 초기 보정 기능은 포함하는 것이 유리하다.
- Inputs:
    aero_coeff_config: structured coefficient config, dimensionless and SI mixed units, valid schema
    calibration_cases: structured test cases, SI units + tolerances, valid schema
- Outputs:
    tuned_aero_model: structured dynamics parameter set, valid schema
    calibration_report: structured metrics, error and pass/fail values, valid schema
- Constraints:
    Calibration workflow must be file/config driven.
    Calibration workflow must accept open-model-derived coefficient data or reference trajectories as optional inputs.
    Calibration report must quantify fit error for each calibration case.
    This stage does not require proof of real-flight-grade accuracy.
- Acceptance Criteria:
    Given a valid aerodynamic coefficient configuration or open-model-derived coefficient seed and at least `5` calibration cases,
    When the calibration workflow is executed,
    Then the system shall emit a calibration report with `100%` case coverage and numeric error metrics for every case.
    Given a tuned aerodynamic model and the calibration regression suite,
    When the suite is re-run,
    Then `100%` of expected report fields shall be generated with `0` missing metrics.
- Tests:
    Unit:        tests/unit/test_aero_calibration.py
    Integration: tests/integration/test_aero_calibration_integration.py
    E2E:         tests/e2e/test_aero_calibration_e2e.py
- Evidence:
    reports/aero_calibration/
    evidence_pack/aero_calibration/

## Non-Functional Requirements

### World-Model Evaluation Priority Order
- ID: REQ-009
- Title: Prioritize evaluation metrics for learning validation
- Context: 이번 단계는 world-model 학습 성공 여부 검증이 목적이므로, 평가 체계의 우선순위가 명확해야 한다.
- Inputs:
    eval_results: structured metrics bundle, numeric values, valid schema
- Outputs:
    ranked_eval_summary: structured ranking output, valid schema
- Constraints:
    Metric ranking must be stable and explicitly reported.
    Priority order must be prediction error > latent consistency > policy convergence.
- Acceptance Criteria:
    Given a complete evaluation result bundle,
    When the ranking summary is generated,
    Then the first-priority section shall be prediction error metrics, the second-priority section shall be latent rollout consistency metrics, and the third-priority section shall be policy convergence metrics in `100%` of generated summaries.
- Tests:
    Unit:        tests/unit/test_eval_priority.py
    Integration: tests/integration/test_eval_priority_integration.py
    E2E:         tests/e2e/test_eval_priority_e2e.py
- Evidence:
    reports/eval_priority/
    evidence_pack/eval_priority/

### Experiment Reproducibility
- ID: REQ-010
- Title: Record enough metadata to reproduce simulator and learning runs
- Context: 시뮬레이터 성능과 학습 결과를 비교하려면 실행 환경과 설정을 재현 가능하게 남겨야 한다.
- Inputs:
    run_config: structured config, valid schema
    hardware_profile: structured system info, valid schema
    seed_bundle: structured seed values, integer ranges
- Outputs:
    run_manifest: structured metadata file, valid schema
    reproducibility_log: structured log, valid schema
- Constraints:
    The manifest must include config, seed, hardware profile, and code revision fields.
    Manifest generation must complete within `5 s` per run.
- Acceptance Criteria:
    Given a simulator or training run start event,
    When metadata capture is executed,
    Then a valid run manifest including config, seed, hardware profile, and revision fields shall be written within `5 s`.
- Tests:
    Unit:        tests/unit/test_run_manifest.py
    Integration: tests/integration/test_run_manifest_integration.py
    E2E:         tests/e2e/test_run_manifest_e2e.py
- Evidence:
    reports/run_manifest/
    evidence_pack/run_manifest/

### Scope Exclusion Enforcement
- ID: REQ-011
- Title: Exclude non-MVP features from the initial implementation scope
- Context: 초기 단계에서 범위를 통제하지 않으면 throughput과 학습 검증 일정이 무너질 수 있다.
- Inputs:
    feature_plan: structured implementation plan, categorical items, valid schema
- Outputs:
    scope_check_report: structured scope audit, valid schema
- Constraints:
    The initial implementation scope must exclude photoreal rendering, HIL/SIL, manned-aircraft control handoff, and real-flight data correction.
- Acceptance Criteria:
    Given the initial implementation plan,
    When the scope audit is executed,
    Then the audit shall flag `100%` of listed non-MVP features if they appear in the phase-1 plan and mark them as excluded or deferred.
- Tests:
    Unit:        tests/unit/test_scope_exclusion.py
    Integration: tests/integration/test_scope_exclusion_integration.py
    E2E:         tests/e2e/test_scope_exclusion_e2e.py
- Evidence:
    reports/scope_exclusion/
    evidence_pack/scope_exclusion/

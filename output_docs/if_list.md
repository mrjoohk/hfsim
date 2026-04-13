# Integration Function List

## Scenario and Resource Orchestration
- IF-ID: IF-01
- Title: Build learnability-first scenarios and hardware-adaptive rollout plans
- Producer: experiment configuration and local machine runtime
- Consumer: simulator execution core
- Input Contract:
    execution_request: structured config object, dimensionless + SI mixed schema, valid experiment range
    hardware_profile: structured system profile, CPU cores / RAM bytes / GPU VRAM bytes, machine-local range
- Output Contract:
    execution_bundle: structured scenario + rollout plan object, valid schema with scenario seed, agent_count [1,4], resource budget, benchmark mode
- Constraints:
    Auto-sizing must complete within 30 s.
    Execution bundle must preserve deterministic seed information.
    Baseline scenario policy must support curriculum level control and rare-case disable by default.
- Failure Modes:
    - Invalid resource estimation causes OOM during batch initialization.
    - Inconsistent seed handling breaks scenario reproducibility.
    - Curriculum policy misconfiguration produces non-monotonic difficulty scaling.
- Linked REQs: REQ-003, REQ-004, REQ-006, REQ-007, REQ-010, REQ-011

---

## Flight and Threat Dynamics Propagation
- IF-ID: IF-02
- Title: Advance the full active motion-model stack for the mission environment
- Producer: simulator execution core
- Consumer: state storage, observation builder, benchmark evaluator
- Input Contract:
    dynamics_step_request: structured state + control bundle, SI units and normalized control, valid schema with dt_internal (0.0005, 0.02], agent_count [1,4]
- Output Contract:
    dynamics_step_result: structured multi-entity state bundle, SI units + discrete flags, finite numeric range defined by config
- Constraints:
    Must include ownship 6-DoF dynamics, active threat kinematics, target/environment transitions, and aerodynamic parameter set.
    Must remain numerically stable for at least 600 simulated seconds.
    Must support calibration-ready aerodynamic coefficient configuration.
- Failure Modes:
    - Numerical instability produces NaN/Inf state values.
    - Cross-agent state indexing errors corrupt shared-environment state.
    - Aerodynamic parameter misconfiguration yields unrealistic or divergent motion.
- Linked REQs: REQ-001, REQ-004, REQ-007, REQ-008

---

## Snapshot Branch Rollout Service
- IF-ID: IF-03
- Title: Capture, restore, and branch deterministic simulator rollouts
- Producer: simulator execution core and training/planning clients
- Consumer: world-model dataset builder, planner evaluation, counterfactual rollout client
- Input Contract:
    snapshot_rollout_request: structured snapshot/control request, bytes + integer step index + normalized control tensor, valid schema
- Output Contract:
    snapshot_rollout_result: structured snapshot payload and branch trajectory object, SI units + event flags, horizon [1, 10^6]
- Constraints:
    Snapshot must preserve control-relevant hidden state, RNG state, and environment continuation state.
    Replay and branch rollout must be deterministic.
    Snapshot operations must not reduce reference benchmark below 60x.
- Failure Modes:
    - Missing hidden state causes restore mismatch.
    - Snapshot mutation corrupts branch reproducibility.
    - Excess serialization overhead degrades benchmark acceleration.
- Linked REQs: REQ-002, REQ-004, REQ-010

---

## Structured Observation Interface
- IF-ID: IF-04
- Title: Convert simulator state into structured learning observations
- Producer: simulator state services
- Consumer: world-model learner and policy learner
- Input Contract:
    observation_request: structured simulator state object, SI units + flags + terrain/threat references, valid schema
- Output Contract:
    observation_batch: structured observation object, normalized float vectors + binary masks, finite range with backward-compatible extension hooks
- Constraints:
    Base observation must include vehicle state, relative terrain features, and threat features.
    API must remain backward-compatible when image/virtual sensor channels are added later.
- Failure Modes:
    - Non-finite observation values destabilize training.
    - Schema drift breaks downstream learner compatibility.
    - Missing terrain/threat features reduce scenario observability.
- Linked REQs: REQ-005, REQ-007

---

## Evaluation, Benchmark, and Reproducibility Reporting
- IF-ID: IF-05
- Title: Evaluate benchmark performance and record reproducible experiment evidence
- Producer: simulator execution core and training/evaluation jobs
- Consumer: researchers, validation pipeline, downstream design stages
- Input Contract:
    evaluation_request: structured metrics + run metadata bundle, numeric metrics + config + seed + hardware profile, valid schema
- Output Contract:
    evaluation_report_bundle: structured benchmark/eval/manifest bundle, ranked metrics + acceleration report + reproducibility manifest, valid schema
- Constraints:
    Must rank evaluation priority as prediction error > latent consistency > policy convergence.
    Must emit manifest metadata within 5 s per run.
    Must flag excluded non-MVP features when phase-1 scope is audited.
- Failure Modes:
    - Missing manifest fields break experiment reproducibility.
    - Misordered metric reporting obscures validation priority.
    - Scope audit misses excluded features and causes scope creep.
- Linked REQs: REQ-004, REQ-009, REQ-010, REQ-011

## REQ-IF Coverage Matrix

| REQ ID | IF Coverage | Status |
|--------|-------------|--------|
| REQ-001 | IF-02 | Covered |
| REQ-002 | IF-03 | Covered |
| REQ-003 | IF-01 | Covered |
| REQ-004 | IF-01, IF-02, IF-03, IF-05 | Covered |
| REQ-005 | IF-04 | Covered |
| REQ-006 | IF-01 | Covered |
| REQ-007 | IF-01, IF-02, IF-04 | Covered |
| REQ-008 | IF-02 | Covered |
| REQ-009 | IF-05 | Covered |
| REQ-010 | IF-01, IF-03, IF-05 | Covered |
| REQ-011 | IF-01, IF-05 | Covered |

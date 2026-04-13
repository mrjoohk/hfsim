# AGENTS.md

## Purpose
Physics-consistent simulation environment for **world-model learning validation** — not a full-fidelity digital twin.
Primary goals: stable 6-DoF dynamics, branchable rollouts, determinism, and 60x time-acceleration throughput.

---

## Project State (as of 2026-04-13)
- **101 tests passing** (unit + integration)
- All 5 IFs and 30 UFs implemented and verified
- Gymnasium wrapper, Ray runtime layer, and world_model interface placeholders in place
- See [project_summary.md](project_summary.md) for full history and [output_docs/todo.md](output_docs/todo.md) for deferred work

---

## Key Files

### Schema (single source of truth for all I/O contracts)
- [src/hf_sim/models.py](src/hf_sim/models.py) — 42 dataclasses covering ExecutionRequest/Bundle, OwnshipState, EnvironmentRuntime, EnvironmentCheckpoint, ObservationBatch, EvaluationReportBundle, etc.

### Integration Functions (IF layer — thin entry points)
- [src/if/if01_orchestration.py](src/if/if01_orchestration.py) — `if_01_build_execution_bundle(ExecutionRequest) → ExecutionBundle`
- [src/if/if02_dynamics.py](src/if/if02_dynamics.py) — `if_02_advance_motion_model_stack(DynamicsStepRequest) → DynamicsStepResult`
- [src/if/if03_snapshot.py](src/if/if03_snapshot.py) — `if_03_branch_snapshot_rollout(SnapshotRolloutRequest) → SnapshotRolloutResult`
- [src/if/if04_observation.py](src/if/if04_observation.py) — `if_04_build_structured_observation(ObservationRequest) → ObservationBatch`
- [src/if/if05_reporting.py](src/if/if05_reporting.py) — `if_05_build_evaluation_report(EvaluationRequest) → EvaluationReportBundle`

### Unit Functions (UF layer — core logic, 6 UFs per IF)
- [src/uf/if01_orchestration.py](src/uf/if01_orchestration.py) — parse → inspect → synthesize → size → assemble → finalize
- [src/uf/if02_dynamics.py](src/uf/if02_dynamics.py) — decode → ownship(6-DoF) → threat → environment → calibration → compose
- [src/uf/if03_snapshot.py](src/uf/if03_snapshot.py) — capture → restore → inject → rollout → verify → package
- [src/uf/if04_observation.py](src/uf/if04_observation.py) — vehicle → terrain → threat → normalize → mask → assemble
- [src/uf/if05_reporting.py](src/uf/if05_reporting.py) — metadata → benchmark → rank → audit → manifest → compose

### Runtime & Training
- [src/hf_sim/env.py](src/hf_sim/env.py) — `HFSimEnv` (Gymnasium.Env wrapper; reset/step call IF-02 + IF-04 + reward + termination)
- [src/hf_sim/ray_runtime.py](src/hf_sim/ray_runtime.py) — `LocalEnvWorker`, `LocalCollector`, `LocalLoggerWorker`; optional Ray actor wrapping
- [src/hf_sim/dataset.py](src/hf_sim/dataset.py) — `SequenceBuffer`, `TransitionBuffer` for trajectory collection
- [src/hf_sim/reward.py](src/hf_sim/reward.py) — reward computation
- [src/hf_sim/noise.py](src/hf_sim/noise.py) — sensor/process noise injection
- [src/hf_sim/domain_rand.py](src/hf_sim/domain_rand.py) — curriculum-driven domain randomization
- [src/hf_sim/termination.py](src/hf_sim/termination.py) — episode termination conditions
- [src/hf_sim/validation_logging.py](src/hf_sim/validation_logging.py) — event logging and metadata capture
- [src/hf_sim/pyvista_viewer.py](src/hf_sim/pyvista_viewer.py) — optional offline 3D visualization (pyvista not yet installed)

### World Model Interfaces (placeholders)
- [src/world_model/base.py](src/world_model/base.py) — abstract interface
- [src/world_model/rssm.py](src/world_model/rssm.py) — RSSM stub
- [src/world_model/dreamer_v3.py](src/world_model/dreamer_v3.py) — DreamerV3 stub

### Tests
- [tests/unit/](tests/unit/) — 13 unit test files (one per module)
- [tests/integration/](tests/integration/) — 6 integration test files (one per IF + gym rollout)
- Run: `python -m pytest tests/unit tests/integration -q -p no:cacheprovider`

### Design Documents
- [output_docs/requirements.md](output_docs/requirements.md) — 11 REQs with acceptance criteria
- [output_docs/uf.md](output_docs/uf.md) — canonical UF doc (30 UFs, I/O contracts, verification ownership)
- [output_docs/uf_split/](output_docs/uf_split/) — per-IF UF docs
- [output_docs/if_list.md](output_docs/if_list.md) — IF boundary contracts
- [output_docs/todo.md](output_docs/todo.md) — deferred work items

---

## System Principles
- **Determinism first**: same seed + snapshot + controls → same rollout
- **Branchability by design**: one saved state → multiple future rollouts under different controls
- **Learnability over realism**: add fidelity only when it improves world-model prediction or policy learning
- **Throughput-critical**: 60x time acceleration is an acceptance requirement, not a nice-to-have
- **Minimal hidden state**: all state that affects rollout must be serializable

## What To Avoid
- Full-object cloning each step for rollback/branching (use explicit snapshot objects)
- Photoreal sensor simulation before throughput and replayability are stable
- Coupling simulator state to non-serializable runtime behavior
- Adding fidelity that improves realism but harms throughput or determinism

## Next Priorities (from [output_docs/todo.md](output_docs/todo.md))
1. threat + radar validation harness (bring to IF-02 acceptance level)
2. full-environment long-horizon acceptance tests
3. `evidence_pack` schema and artifact policy
4. JSBSim/open-model secondary 6-DoF comparison
5. benchmark/profiling automation for 60x regression tracking

## Source Documents
- Global rules: [GLOBAL_RULES.md](GLOBAL_RULES.md)
- Engineering process: [.codex/skills/core-engineering/SKILL.md](.codex/skills/core-engineering/SKILL.md)
- Project history: [project_summary.md](project_summary.md)

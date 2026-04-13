# Ray Runtime Implementation Analysis

## Goal
- Add a Ray-ready orchestration layer without turning IF-02 or IF-03 into RPC-heavy kernels.
- Preserve deterministic local physics and expose worker-oriented rollout, branch rollout, logging, and collection APIs.

## Key Decisions
- Keep IF-02 and IF-03 local and deterministic.
- Add `LocalEnvWorker`, `LocalCollector`, and `LocalLoggerWorker` as the base runtime layer.
- Add `create_ray_actor_classes()` as an optional wrapper so the same worker contracts can be used with Ray later.
- Avoid hard dependency on `ray` and `gymnasium` for testability in lightweight environments.

## Supporting Changes
- Added `gym_compat.py` to let `HFSimEnv` import in environments without `gymnasium`.
- Added tests for local chunk equivalence, branch rollout, collection, log export, and fake-Ray wrapping.
- Normalized temp-file based tests to workspace-local files because the current Windows environment rejects default temp directories.

## Outcome
- The project now has a concrete orchestration layer where Ray can be applied later with minimal refactoring.
- Core simulation code remains local-function based and unaffected by actor/RPC concerns.

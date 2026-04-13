# MVP Runtime Branching Implementation Analysis
Date: 2026-04-08 14:54

## Scope

- Implement the approved MVP enhancement plan
- Expand checkpoint target from ownship-only semantics to full-environment runtime semantics
- Refactor IF-03 from lightweight snapshot replay into branchable environment runtime service

## Current State

- `IF-02` currently propagates ownship, threats, targets, and environment only.
- `IF-03` currently serializes a lightweight dict and rolls it forward with a custom mini-stepper that does not reuse `IF-02`.
- No first-class runtime object exists for radar, sensor, atmosphere, RNG state, or environment-wide hidden state.

## Implementation Direction

1. Extend shared models with explicit runtime sub-objects:
   - radar
   - sensor
   - atmosphere
   - rng state / mode flags
   - environment runtime aggregate

2. Add a reusable environment step kernel in `IF-02` UF layer.
   - This kernel will become the common engine for:
     - direct IF-02 stepping
     - IF-03 branch rollout replay

3. Replace IF-03 snapshot pipeline with environment checkpoint pipeline.
   - checkpoint capture
   - completeness validation
   - branch control normalization
   - branch runtime cloning
   - environment-kernel rollout
   - isolation/determinism validation

4. Update tests to verify:
   - 6-DoF stability and determinism
   - checkpoint completeness
   - branch isolation
   - single-action and action-sequence branching

5. Create `todo.md` for deferred items outside this implementation pass.

## Judgment Rationale

- The user clarified that "saved object" means the whole simulation environment runtime, not only the 6-DoF ownship model.
- Therefore a state-dict snapshot that omits environment subsystems would be semantically incorrect even if it passes a narrow replay test.
- Reusing one IF-02 step kernel for both direct stepping and branch rollout is the cleanest way to guarantee determinism and reduce model drift between simulation and branching paths.

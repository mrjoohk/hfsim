# IF-02 Harness Strengthening Analysis
Date: 2026-04-08 15:12

## Scope

- Strengthen the IF-02 6-DoF validation harness
- Promote existing smoke checks into explicit acceptance-style tests
- Keep validation centered on ownship 6-DoF while leaving full-environment long-horizon checks for a later stage

## Current Gap

- Current tests already cover:
  - finite state output
  - invalid dt guard
  - short deterministic stability
- Current tests do not yet clearly encode:
  - 600 simulated-second acceptance
  - named deterministic replay acceptance
  - throttle sanity acceptance
  - pitch sanity acceptance
  - roll sanity acceptance
  - parameter sensitivity acceptance

## Implementation Direction

1. Keep the grouped IF-02 test layout.
2. Add named acceptance tests inside the grouped unit file.
3. Use ownship-only MUST criteria for long-horizon acceptance.
4. Use mixed sanity criteria:
   - directionality is mandatory
   - weak numeric lower bound only for throttle
5. Keep integration test lightweight and use unit/acceptance tests for most harness detail.

## Judgment Rationale

- The current simplified 6-DoF model is stable enough to support stronger regression gates.
- Acceptance should be explicit and individually traceable, but it does not require splitting files.
- Ownship-first acceptance matches the current maturity of the model and avoids over-claiming full-environment fidelity too early.

# IF Integration Implementation Analysis

- Date: 2026-04-08 12:38
- Scope: Review whether `$if-integrator` can proceed immediately and define the implementation sequence needed to satisfy the validated IF/UF design.

## Current Repository State

- `output_docs/if_list.md`, `output_docs/if_decomposition.md`, and `output_docs/uf.md` are present and validated.
- `src/uf/` does not exist yet.
- `src/if/` does not exist yet.
- `tests/unit/` and `tests/integration/` do not exist yet.
- Prior UF-chain validation passed on document structure and I/O continuity, but flagged missing code/test/evidence artifacts.

## Findings

1. `$if-integrator` is not independently executable yet.
   - The skill requires implemented UF modules under `src/uf/*.py`.
   - Without UF functions, IF modules would become wrappers around placeholders and would not satisfy the skill's interface-validation intent.

2. The user request can still move forward without changing design direction.
   - We can implement the minimum UF layer and the IF integration layer in one continuous pass.
   - This keeps the repository aligned with the validated design and avoids writing throwaway integration glue.

3. The safest implementation slice is to build shared domain models first, then UF modules, then IF entry points, then tests and report.
   - The validated UF documents already define stable I/O chains.
   - IF-01, IF-03, IF-04, and IF-05 can be implemented with relatively low ambiguity.
   - IF-02 should be delivered as a workable 6-DoF baseline plus calibration hooks, not as a claim of fully tuned high-fidelity aerodynamics.

## Proposed Implementation Sequence

1. Create shared schema/types module for requests, intermediate contexts, and results used by UF and IF layers.
2. Implement `src/uf/` modules aligned with the validated UF chains.
3. Implement `src/if/` modules that orchestrate UF calls and expose one public IF entry point per IF.
4. Add unit tests for representative UFs and integration tests for all IF entry points.
5. Add `reports/impl/if_integration_report_<timestamp>.md` summarizing implemented IF call sequences, test coverage status, and remaining risks.

## Recommended Initial File Set

- `src/hf_sim/models.py`
- `src/hf_sim/errors.py`
- `src/uf/if01_orchestration.py`
- `src/uf/if02_dynamics.py`
- `src/uf/if03_snapshot.py`
- `src/uf/if04_observation.py`
- `src/uf/if05_reporting.py`
- `src/if/if01_orchestration.py`
- `src/if/if02_dynamics.py`
- `src/if/if03_snapshot.py`
- `src/if/if04_observation.py`
- `src/if/if05_reporting.py`
- `tests/unit/test_if01_orchestration.py`
- `tests/unit/test_if02_dynamics.py`
- `tests/unit/test_if03_snapshot.py`
- `tests/unit/test_if04_observation.py`
- `tests/unit/test_if05_reporting.py`
- `tests/integration/test_if01_orchestration.py`
- `tests/integration/test_if02_dynamics.py`
- `tests/integration/test_if03_snapshot.py`
- `tests/integration/test_if04_observation.py`
- `tests/integration/test_if05_reporting.py`
- `reports/impl/if_integration_report_260408_XXXX.md`

## Scope Decision

- Proceed with combined `UF minimum implementation + IF integration`.
- Do not wait for a separate UF-only phase, because the design artifacts are already stabilized and the user explicitly asked to continue implementation.
- Keep the first pass focused on correctness, determinism hooks, and extensible interfaces rather than full physical fidelity tuning.

## Judgment Rationale

- `$if-integrator` depends on `src/uf/*.py`; this dependency is explicit in the skill definition.
- The repository currently contains design artifacts only, so direct IF integration would produce structurally correct but operationally hollow modules.
- Implementing shared models and UFs first preserves interface fidelity and lets the IF layer be validated against real function signatures.
- This sequence matches the project goal: prove world-model learnability quickly while preserving the core requirements of 6-DoF propagation, snapshot branching, structured observations, and reproducible benchmark reporting.

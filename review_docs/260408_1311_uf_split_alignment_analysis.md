# UF Split Alignment Analysis
Date: 2026-04-08 13:11

## Scope

- Re-validate the implementation against `output_docs/uf_split/uf_if01.md` through `uf_if05.md`
- Determine whether the split documents reduce validator ambiguity
- Define the minimum update needed for `output_docs/uf.md` so future validation is less confusing

## Findings

1. `output_docs/uf_split` is a better inspection baseline than monolithic `uf.md`.
   - Each file isolates one IF chain.
   - The current repository also implements code and tests per IF group:
     - `src/uf/if01_orchestration.py` ... `src/uf/if05_reporting.py`
     - `tests/unit/test_if01_orchestration.py` ... `tests/unit/test_if05_reporting.py`
     - `tests/integration/test_if01_orchestration.py` ... `tests/integration/test_if05_reporting.py`
   - This makes `uf_split` conceptually closer to the implemented layout than the single large `uf.md`.

2. The split UF documents still carry the same verification-path mismatch as `uf.md`.
   - Example in `output_docs/uf_split/uf_if01.md`:
     - `tests/unit/test_parse_execution_config.py`
     - `tests/unit/test_inspect_hardware_profile.py`
     - `tests/unit/test_synthesize_scenario.py`
   - Actual repository layout uses grouped unit files:
     - `tests/unit/test_if01_orchestration.py`
   - The same mismatch exists in all split files for IF-02 through IF-05.

3. Using `uf_split` as the validation baseline changes the interpretation, but not the strict outcome.
   - Chain integrity by IF group: PASS
   - Runtime validation by IF-grouped tests: PASS
   - Exact documented verification-path match: FAIL
   - Evidence-pack completeness: still FAIL

4. The least confusing repair is to align both document layers to the repository's grouped test strategy.
   - `output_docs/uf.md` should reference grouped unit tests per IF file, not imagined one-file-per-UF tests.
   - Ideally `output_docs/uf_split/*.md` should be updated the same way afterward for full consistency.
   - If only `uf.md` is updated, confusion decreases, but `uf_split` will still lag behind and can reintroduce the same misunderstanding later.

## Recommended Update Direction

### Verification-plan alignment

- Replace per-UF unit test file paths such as:
  - `tests/unit/test_parse_execution_config.py::...`
- With grouped file paths such as:
  - `tests/unit/test_if01_orchestration.py::test_if01_uf_chain_builds_60x_bundle`
  - `tests/unit/test_if01_orchestration.py::test_parse_execution_config_none_raises`

- Apply the same strategy for IF-02 through IF-05:
  - IF-02 -> `tests/unit/test_if02_dynamics.py`
  - IF-03 -> `tests/unit/test_if03_snapshot.py`
  - IF-04 -> `tests/unit/test_if04_observation.py`
  - IF-05 -> `tests/unit/test_if05_reporting.py`

### Validation conclusion wording

- Future validator reports should explicitly distinguish:
  - `implementation/runtime pass`
  - `documentation/test-plan exact match`
  - `evidence-pack completeness`

## Current Validation Status Using `uf_split`

- Code path existence: PASS
- IF-group chain continuity: PASS
- `pytest` execution: PASS (`15 passed`)
- Exact Verification Plan path match: FAIL
- Evidence pack field realization: FAIL

## Judgment Rationale

- `uf_split` mirrors the implemented module boundaries better than the monolithic file, so it is the clearer baseline for human review.
- However, the text inside `uf_split` was copied from the canonical UF spec and still assumes per-UF test files that do not exist.
- Therefore, changing the validation viewpoint from `uf.md` to `uf_split` improves readability but does not by itself resolve the strict validator mismatch.
- The most effective next correction is to update `output_docs/uf.md` first, then optionally propagate the same alignment to `output_docs/uf_split/*.md`.

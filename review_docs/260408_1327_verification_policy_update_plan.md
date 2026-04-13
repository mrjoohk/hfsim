# Verification Policy Update Plan
Date: 2026-04-08 13:27

## Goal

Reflect the new verification-granularity policy across:
- `output_docs/uf.md`
- optionally `output_docs/uf_split/*.md` for consistency
- `.codex/skills/if-designer/SKILL.md`
- `.codex/skills/uf-designer/SKILL.md`
- `.codex/skills/uf-chain-validator/SKILL.md`

Also create a reusable rationale memo for future skill edits.

## Why This Change Is Needed

### Problem observed

- The current UF documents assume that every UF should have a standalone functional test file.
- The actual implementation naturally grouped tests by IF/module boundary, which is often the correct engineering choice.
- As a result, the validator flagged mismatches even though the code and runtime chains were healthy.

### Root cause

- The design instructions implicitly equated "leaf UF" with "independently functionally testable unit."
- That assumption is too strong for composition-heavy UFs.
- Some UFs are locally testable, but others only make real behavioral sense inside the full parent IF chain.

## New Policy

### Principle

Verification ownership must be assigned by **observability of correctness**, not by UF count.

### Categories

1. `UF-local functional verification`
   - Use when the UF's contract can be validated with local input/output alone.

2. `UF guard-rail verification + IF-chain functional verification`
   - Use when the UF is mostly an assembler, composer, packager, or merger.
   - UF unit checks cover errors, schema, and missing dependencies.
   - Main functional behavior is owned by the parent IF test.

3. `IF-level acceptance verification`
   - Use for emergent properties spanning multiple UFs, such as:
     - end-to-end determinism
     - time-acceleration targets
     - full-stack stability
     - ranked evaluation policy
     - backward-compatible final schema

## Planned Document Changes

### 1. `output_docs/uf.md`

- Rewrite `Verification Plan` sections to distinguish:
  - `Unit Verification`
  - `Chain Verification`
  - `Coverage / Acceptance Ownership`
- Replace fake per-UF test-file assumptions with the actual grouped test structure where appropriate.
- Mark composition-heavy UFs as IF-owned for main functional acceptance.

### 2. `output_docs/uf_split/*.md`

- Strongly recommended follow-up for full consistency.
- Same rewrite pattern as `uf.md`, but applied per IF document.
- This is especially helpful because `uf_split` is now the clearer human-review baseline.

### 3. `if-designer` skill

- Relax the rule "each subfunction must be independently testable."
- Replace it with:
  - each subfunction must have a clear verification owner
  - some leaf nodes may be locally unit-testable
  - some leaf nodes may depend on parent IF-chain validation

### 4. `uf-designer` skill

- Replace the current blanket rule that every UF block names standalone unit-test files.
- Require the designer to classify each UF as:
  - `local-functional`
  - `guard-rail + chain-owned`
  - `IF-acceptance-owned`
- Update the verification-plan template accordingly.

### 5. `uf-chain-validator` skill

- Validator must stop treating every missing per-UF test path as an automatic failure.
- It should validate:
  - whether the declared verification ownership is explicit
  - whether the referenced tests actually exist
  - whether IF-owned functional checks are present when composition-heavy UFs defer to parent IF tests
- Remaining FAIL should focus on real gaps:
  - missing declared tests
  - missing chain acceptance
  - missing evidence linkage

## Deliverables To Produce After Approval

1. A rationale memo for future skill edits:
   - `review_docs/260408_XXXX_verification_policy_rationale.md`
2. Updated `output_docs/uf.md`
3. Recommended consistency update for `output_docs/uf_split/*.md`
4. Updated skill files:
   - `.codex/skills/if-designer/SKILL.md`
   - `.codex/skills/uf-designer/SKILL.md`
   - `.codex/skills/uf-chain-validator/SKILL.md`

## Judgment Rationale

- The current mismatch is not primarily a code defect; it is a design-policy defect.
- Preserving the old "every UF must have standalone functional tests" rule will keep reintroducing document drift.
- Updating the design documents alone is not enough; the skills must encode the corrected policy or the same issue will recur in future projects.
- Therefore the right fix is a coordinated update of both the artifacts and the skill instructions.

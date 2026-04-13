# Skill Update Plan

This file records future skill-update direction only. No skill files were modified in this task.

## Why The Direction Changed

- The previous UF verification policy implicitly assumed that every leaf UF should own a standalone functional test.
- Implementation showed that this assumption was too rigid:
  - some UFs are naturally testable in isolation
  - some UFs are composition-heavy and only meaningful inside the parent IF chain
  - some requirements such as `>= 60x`, end-to-end determinism, and final schema stability are clearly IF-level acceptance properties
- This created repeated drift between design documents and the real repository layout.

## Core Policy Shift

Verification should be assigned by where correctness is observable, not by UF count.

### Verification ownership categories

1. `UF-local functional verification`
   - for locally decidable transforms, validators, and calculators
2. `UF guard-rail verification + IF-chain functional verification`
   - for assembly, composition, packaging, and merge nodes
3. `IF-level acceptance verification`
   - for emergent properties spanning multiple UFs

## Direction Per Skill

### `if-designer`

- stop requiring every leaf node to be independently functionally testable
- require every leaf node to have an explicit verification owner
- allow leaf nodes whose main behavioral validation is owned by the parent IF chain

### `uf-designer`

- replace the blanket rule that every UF must name a standalone functional test file
- require each UF block to classify verification as:
  - local-functional
  - guard-rail plus chain-owned
  - IF-acceptance-owned
- make `Verification Plan` explicitly distinguish:
  - `Unit Verification`
  - `Chain Verification`
  - `Ownership`
- keep one canonical `uf.md`
- also generate per-IF companion documents:
  - `uf_split/uf_if01.md`
  - `uf_split/uf_if02.md`
  - `uf_split/uf_if03.md`
  - `uf_split/uf_if04.md`
  - `uf_split/uf_if05.md`

### `uf-chain-validator`

- stop treating the absence of per-UF standalone functional tests as an automatic failure
- validate whether declared verification ownership is explicit and satisfied
- treat the following as separate gates:
  - implementation/runtime validation
  - document-to-test-plan alignment
  - evidence-pack completeness

## Main Cause Summary

- root cause: design policy over-constrained verification granularity
- observed symptom: strict validator FAIL despite healthy code/runtime chain
- corrective insight: composition-heavy UFs often need guard-rail tests locally and functional acceptance at IF level

## Judgment Rationale

- A verification plan is useful only when it reflects where behavior can actually be observed.
- Forcing standalone functional ownership onto every UF creates false precision, document drift, and maintenance overhead.
- Explicit verification ownership is a more stable rule for both future design artifacts and future validators.

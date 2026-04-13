# Unit Function Blocks

## IF-05

- UF-ID: UF-05-01
- Goal: collect reproducibility metadata
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-05-02
- Goal: compute benchmark and acceleration metrics
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local verification plus IF-05 reporting acceptance

- UF-ID: UF-05-03
- Goal: rank learning metrics by validation priority
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local verification plus IF-05 ordering acceptance

- UF-ID: UF-05-04
- Goal: audit phase-one scope exclusions
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-05-05
- Goal: build reproducibility manifest
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if05_reporting.py`
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - UF-local verification plus IF-05 reporting acceptance

- UF-ID: UF-05-06
- Goal: compose final evaluation report bundle
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if05_reporting.py`
    Chain Verification:
      - `tests/integration/test_if05_reporting.py::test_if05_reporting_acceptance`
    Ownership:
      - parent IF chain functional verification

# Unit Function Blocks

## IF-04

- UF-ID: UF-04-01
- Goal: extract vehicle state features
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-04-02
- Goal: extract terrain-relative features
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-04-03
- Goal: extract threat-relative features
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-04-04
- Goal: normalize observation feature groups
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-04-05
- Goal: build observation validity masks
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if04_observation.py`
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-04-06
- Goal: assemble backward-compatible observation batch
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if04_observation.py`
    Chain Verification:
      - `tests/integration/test_if04_observation.py::test_if04_observation_acceptance`
    Ownership:
      - parent IF chain functional verification

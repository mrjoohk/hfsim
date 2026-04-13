# Unit Function Blocks

## IF-02

- UF-ID: UF-02-01
- Goal: decode step request into typed entity states
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-02-02
- Goal: propagate ownship 6-DoF state
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local dynamics verification plus IF-02 stability acceptance

- UF-ID: UF-02-03
- Goal: propagate threat and adversary kinematics
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-02-04
- Goal: propagate target and environment state
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local functional verification

- UF-ID: UF-02-05
- Goal: apply aerodynamic calibration overrides
- Verification Plan:
    Unit Verification:
      - grouped checks in `tests/unit/test_if02_dynamics.py`
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - UF-local calibration verification plus IF-02 stability acceptance

- UF-ID: UF-02-06
- Goal: compose next-step dynamics result bundle
- Verification Plan:
    Unit Verification:
      - grouped guard-rail checks in `tests/unit/test_if02_dynamics.py`
    Chain Verification:
      - `tests/integration/test_if02_dynamics.py::test_if02_dynamics_acceptance`
    Ownership:
      - parent IF chain functional verification

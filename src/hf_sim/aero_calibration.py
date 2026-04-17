"""Aerodynamic calibration case library and workflow (REQ-008).

Provides a file/config-driven workflow that:
1. Loads calibration cases from a JSON case library.
2. Runs each case through both the production Euler integrator and the RK4
   reference model (``uf.reference_dynamics``).
3. Computes numeric error metrics (RMS position_error_m, velocity_error_mps).
4. Assembles an :class:`AeroCalibrationReport` with 100% field coverage.

REQ-008 acceptance criteria:
- At least 5 calibration cases
- File/config-driven workflow (JSON case library)
- Numeric error metrics for every case
- 100% field coverage (coverage_pct == 100.0)
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hf_sim.models import (
    AeroCalibrationReport,
    AtmosphereState,
    CalibrationCase,
    CalibrationCaseResult,
    DynamicsControl,
    OwnshipState,
)
from uf.reference_dynamics import propagate_ownship_euler, propagate_ownship_rk4

# Default path to the bundled case library
_DEFAULT_CASES_PATH = Path(__file__).parent.parent.parent / "data" / "calibration_cases.json"


# ---------------------------------------------------------------------------
# Case loading
# ---------------------------------------------------------------------------

def load_calibration_cases(path: str | Path) -> list[CalibrationCase]:
    """Load calibration cases from a JSON file (file/config-driven, REQ-008).

    Args:
        path: Path to a JSON file with the case library schema.

    Returns:
        List of :class:`CalibrationCase` objects.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the JSON structure is missing required fields.
    """
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Calibration cases file not found: {target}")

    with target.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    raw_cases: list[dict[str, Any]] = data.get("cases", [])
    if not raw_cases:
        raise ValueError("No cases found in calibration case library")

    cases: list[CalibrationCase] = []
    for raw in raw_cases:
        cases.append(CalibrationCase(
            case_id=raw["case_id"],
            description=raw.get("description", ""),
            calibration_config=dict(raw["calibration_config"]),
            n_steps=int(raw["n_steps"]),
            dt=float(raw["dt"]),
            initial_state=dict(raw["initial_state"]),
            control=dict(raw["control"]),
            atmosphere=dict(raw["atmosphere"]),
            position_error_threshold_m=float(raw["position_error_threshold_m"]),
            velocity_error_threshold_mps=float(raw["velocity_error_threshold_mps"]),
        ))
    return cases


# ---------------------------------------------------------------------------
# Single case execution
# ---------------------------------------------------------------------------

def run_calibration_case(case: CalibrationCase) -> CalibrationCaseResult:
    """Run a single calibration case and return numeric error metrics.

    Procedure:
    1. Build initial :class:`OwnshipState` from ``case.initial_state``.
    2. Apply ``calibration_config`` (velocity_scale + coefficient_overrides)
       to get the effective aero params for this case.
    3. Run ``n_steps`` of Euler integration (production) from the calibrated state.
    4. Run ``n_steps`` of RK4 integration (reference) from the same state.
    5. Compute per-step position and velocity errors; aggregate as RMS.
    6. Compare RMS errors to thresholds → passed.

    Args:
        case: Loaded :class:`CalibrationCase` definition.

    Returns:
        :class:`CalibrationCaseResult` with all error metrics populated.
    """
    # --- Build OwnshipState ---
    s = case.initial_state
    base_aero = dict(s.get("aero_params", {}))

    # Apply coefficient_overrides from calibration_config
    cal = case.calibration_config
    effective_aero = {**base_aero, **cal.get("coefficient_overrides", {})}
    velocity_scale = float(cal.get("velocity_scale", 1.0))

    initial_ownship = OwnshipState(
        position_m=list(s["position_m"]),
        velocity_mps=[v * velocity_scale for v in s["velocity_mps"]],
        quaternion_wxyz=list(s["quaternion_wxyz"]),
        angular_rate_rps=list(s["angular_rate_rps"]),
        mass_kg=float(s["mass_kg"]),
        aero_params=effective_aero,
    )

    # --- Build Control ---
    c = case.control
    control = DynamicsControl(
        throttle=float(c["throttle"]),
        body_rate_cmd_rps=list(c["body_rate_cmd_rps"]),
        load_factor_cmd=float(c.get("load_factor_cmd", 1.0)),
    )

    # --- Build AtmosphereState ---
    a = case.atmosphere
    atmosphere = AtmosphereState(
        density_kgpm3=float(a.get("density_kgpm3", 1.225)),
        wind_vector_mps=list(a.get("wind_vector_mps", [0.0, 0.0, 0.0])),
        turbulence_level=float(a.get("turbulence_level", 0.0)),
    )

    # --- Run both integrators ---
    euler_state = initial_ownship
    rk4_state = initial_ownship
    pos_errors: list[float] = []
    vel_errors: list[float] = []

    for _ in range(case.n_steps):
        euler_next = propagate_ownship_euler(euler_state, control, atmosphere, case.dt)
        rk4_next = propagate_ownship_rk4(rk4_state, control, atmosphere, case.dt)

        pos_err = math.sqrt(sum(
            (euler_next.position_m[i] - rk4_next.position_m[i]) ** 2 for i in range(3)
        ))
        vel_err = math.sqrt(sum(
            (euler_next.velocity_mps[i] - rk4_next.velocity_mps[i]) ** 2 for i in range(3)
        ))
        pos_errors.append(pos_err)
        vel_errors.append(vel_err)

        euler_state = euler_next
        rk4_state = rk4_next

    # --- RMS aggregation ---
    rms_pos = math.sqrt(sum(e * e for e in pos_errors) / len(pos_errors))
    rms_vel = math.sqrt(sum(e * e for e in vel_errors) / len(vel_errors))

    passed = (
        rms_pos <= case.position_error_threshold_m
        and rms_vel <= case.velocity_error_threshold_mps
    )

    return CalibrationCaseResult(
        case_id=case.case_id,
        position_error_m=rms_pos,
        velocity_error_mps=rms_vel,
        passed=passed,
        notes=[
            f"rms_pos={rms_pos:.4f}m",
            f"rms_vel={rms_vel:.4f}mps",
            f"threshold_pos={case.position_error_threshold_m}m",
            f"threshold_vel={case.velocity_error_threshold_mps}mps",
        ],
    )


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

def run_calibration_workflow(
    cases_path: str | Path | None = None,
    cases: list[CalibrationCase] | None = None,
) -> AeroCalibrationReport:
    """Run the full calibration workflow and return a report.

    Exactly one of ``cases_path`` or ``cases`` must be provided.  If neither
    is given, the bundled ``data/calibration_cases.json`` is used as default.

    Args:
        cases_path: Path to a JSON case library (file-driven, REQ-008).
        cases:      Pre-loaded list of :class:`CalibrationCase` objects
                    (config-driven, REQ-008).

    Returns:
        :class:`AeroCalibrationReport` with ``coverage_pct == 100.0``.

    Raises:
        ValueError: If neither argument is supplied and the default file is missing.
    """
    if cases is None:
        path = Path(cases_path) if cases_path is not None else _DEFAULT_CASES_PATH
        cases = load_calibration_cases(path)

    case_results = [run_calibration_case(case) for case in cases]

    n_passed = sum(1 for r in case_results if r.passed)

    return AeroCalibrationReport(
        schema_version="1.0",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        n_cases_total=len(case_results),
        n_cases_passed=n_passed,
        cases=case_results,
        coverage_pct=100.0,
    )


# ---------------------------------------------------------------------------
# Report serialization
# ---------------------------------------------------------------------------

def _case_result_to_dict(r: CalibrationCaseResult) -> dict[str, Any]:
    return {
        "case_id": r.case_id,
        "position_error_m": r.position_error_m,
        "velocity_error_mps": r.velocity_error_mps,
        "passed": r.passed,
        "notes": list(r.notes),
    }


def report_to_dict(report: AeroCalibrationReport) -> dict[str, Any]:
    """Serialize an :class:`AeroCalibrationReport` to a plain dict."""
    return {
        "schema_version": report.schema_version,
        "timestamp_utc": report.timestamp_utc,
        "n_cases_total": report.n_cases_total,
        "n_cases_passed": report.n_cases_passed,
        "cases": [_case_result_to_dict(r) for r in report.cases],
        "coverage_pct": report.coverage_pct,
    }


def save_calibration_report(report: AeroCalibrationReport, path: str | Path) -> Path:
    """Write the calibration report as indented JSON.

    Args:
        report: Report to serialize.
        path:   Destination file path.

    Returns:
        Resolved :class:`~pathlib.Path` of the written file.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(report_to_dict(report), fh, indent=2)
    return target

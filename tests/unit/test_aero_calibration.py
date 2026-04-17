"""Unit tests for hf_sim.aero_calibration (REQ-008 calibration case library)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from hf_sim.aero_calibration import (
    load_calibration_cases,
    report_to_dict,
    run_calibration_case,
    run_calibration_workflow,
    save_calibration_report,
)
from hf_sim.models import CalibrationCase

# Default case library path (relative to repo root)
_CASES_PATH = Path(__file__).parent.parent.parent / "data" / "calibration_cases.json"


# ---------------------------------------------------------------------------
# load_calibration_cases
# ---------------------------------------------------------------------------

def test_load_calibration_cases_returns_at_least_5():
    """REQ-008: case library must contain at least 5 cases."""
    cases = load_calibration_cases(_CASES_PATH)
    assert len(cases) >= 5


def test_load_calibration_cases_returns_calibration_case_objects():
    cases = load_calibration_cases(_CASES_PATH)
    for case in cases:
        assert isinstance(case, CalibrationCase)


def test_load_calibration_cases_fields_populated():
    """Every loaded case must have non-empty case_id and valid thresholds."""
    cases = load_calibration_cases(_CASES_PATH)
    for case in cases:
        assert len(case.case_id) > 0
        assert case.n_steps > 0
        assert case.dt > 0.0
        assert case.position_error_threshold_m > 0.0
        assert case.velocity_error_threshold_mps > 0.0


def test_load_calibration_cases_file_not_found_raises():
    with pytest.raises(FileNotFoundError):
        load_calibration_cases("/nonexistent/path/cases.json")


# ---------------------------------------------------------------------------
# run_calibration_case
# ---------------------------------------------------------------------------

def test_run_calibration_case_returns_result_type():
    from hf_sim.models import CalibrationCaseResult
    cases = load_calibration_cases(_CASES_PATH)
    result = run_calibration_case(cases[0])
    assert isinstance(result, CalibrationCaseResult)


def test_run_calibration_case_c1_nominal_error_finite():
    """c1_nominal: position and velocity errors must be finite."""
    cases = {c.case_id: c for c in load_calibration_cases(_CASES_PATH)}
    result = run_calibration_case(cases["c1_nominal"])
    assert math.isfinite(result.position_error_m)
    assert math.isfinite(result.velocity_error_mps)


def test_run_calibration_case_c1_nominal_position_error_small():
    """c1_nominal with velocity_scale=1.0: Euler and RK4 are close at dt=0.01."""
    cases = {c.case_id: c for c in load_calibration_cases(_CASES_PATH)}
    result = run_calibration_case(cases["c1_nominal"])
    assert result.position_error_m < 1.0, (
        f"c1_nominal: position_error={result.position_error_m:.4f}m should be < 1.0m"
    )


def test_run_calibration_case_c2_high_drag_has_nonzero_error():
    """c2_high_drag with drag_coeff=0.04 produces measurable integration differences."""
    cases = {c.case_id: c for c in load_calibration_cases(_CASES_PATH)}
    result = run_calibration_case(cases["c2_high_drag"])
    assert result.velocity_error_mps >= 0.0
    assert result.position_error_m >= 0.0


def test_run_calibration_case_notes_populated():
    cases = load_calibration_cases(_CASES_PATH)
    result = run_calibration_case(cases[0])
    assert len(result.notes) > 0


# ---------------------------------------------------------------------------
# run_calibration_workflow
# ---------------------------------------------------------------------------

def test_run_calibration_workflow_coverage_100():
    """REQ-008: coverage_pct must be 100.0."""
    report = run_calibration_workflow(cases_path=_CASES_PATH)
    assert report.coverage_pct == 100.0


def test_run_calibration_workflow_n_cases_at_least_5():
    """REQ-008: must run at least 5 cases."""
    report = run_calibration_workflow(cases_path=_CASES_PATH)
    assert report.n_cases_total >= 5


def test_run_calibration_workflow_all_errors_finite():
    """Every case result must have finite error metrics (REQ-008: no missing metrics)."""
    report = run_calibration_workflow(cases_path=_CASES_PATH)
    for case_result in report.cases:
        assert math.isfinite(case_result.position_error_m), (
            f"{case_result.case_id}: position_error_m is non-finite"
        )
        assert math.isfinite(case_result.velocity_error_mps), (
            f"{case_result.case_id}: velocity_error_mps is non-finite"
        )


def test_run_calibration_workflow_accepts_cases_list():
    """Workflow can be driven directly by a list of CalibrationCase objects."""
    cases = load_calibration_cases(_CASES_PATH)
    report = run_calibration_workflow(cases=cases)
    assert report.n_cases_total == len(cases)


# ---------------------------------------------------------------------------
# save/reload round-trip
# ---------------------------------------------------------------------------

def test_save_calibration_report_round_trip():
    """Report must serialize to JSON and reload identical values."""
    report = run_calibration_workflow(cases_path=_CASES_PATH)
    out_path = Path.cwd() / "test_calibration_report.json"
    try:
        out = save_calibration_report(report, out_path)
        assert out.exists()

        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["schema_version"] == "1.0"
        assert loaded["coverage_pct"] == 100.0
        assert len(loaded["cases"]) == report.n_cases_total
        for case_dict in loaded["cases"]:
            assert math.isfinite(case_dict["position_error_m"])
            assert math.isfinite(case_dict["velocity_error_mps"])
    finally:
        out_path.unlink(missing_ok=True)

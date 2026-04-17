"""Integration tests for the aero calibration workflow (REQ-008).

Verifies:
- File-driven workflow loads and runs all 5 cases from calibration_cases.json.
- All error metrics are finite (zero missing metrics — REQ-008 acceptance).
- Deterministic: two identical workflow runs produce the same report.
- Report JSON round-trip preserves all fields.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from hf_sim.aero_calibration import (
    load_calibration_cases,
    run_calibration_workflow,
    save_calibration_report,
)

_CASES_PATH = Path(__file__).parent.parent.parent / "data" / "calibration_cases.json"


def test_file_driven_workflow_n_cases_at_least_5():
    """REQ-008: file-driven workflow must produce at least 5 case results."""
    report = run_calibration_workflow(cases_path=_CASES_PATH)
    assert report.n_cases_total >= 5, (
        f"REQ-008 FAIL: only {report.n_cases_total} cases, need >= 5"
    )


def test_file_driven_workflow_zero_missing_metrics():
    """REQ-008: every case result must have finite position_error_m and velocity_error_mps."""
    report = run_calibration_workflow(cases_path=_CASES_PATH)
    missing = []
    for r in report.cases:
        if not math.isfinite(r.position_error_m) or not math.isfinite(r.velocity_error_mps):
            missing.append(r.case_id)
    assert len(missing) == 0, (
        f"REQ-008 FAIL: missing metrics for cases: {missing}"
    )


def test_file_driven_workflow_coverage_100():
    """REQ-008: coverage_pct must be exactly 100.0."""
    report = run_calibration_workflow(cases_path=_CASES_PATH)
    assert report.coverage_pct == 100.0, (
        f"REQ-008 FAIL: coverage_pct={report.coverage_pct} (expected 100.0)"
    )


def test_workflow_deterministic():
    """Two runs with the same case library produce identical error metrics."""
    r1 = run_calibration_workflow(cases_path=_CASES_PATH)
    r2 = run_calibration_workflow(cases_path=_CASES_PATH)
    assert r1.n_cases_total == r2.n_cases_total
    for c1, c2 in zip(r1.cases, r2.cases):
        assert c1.case_id == c2.case_id
        assert c1.position_error_m == c2.position_error_m
        assert c1.velocity_error_mps == c2.velocity_error_mps
        assert c1.passed == c2.passed


def test_report_json_round_trip():
    """Save and reload report; all numeric fields must be preserved."""
    report = run_calibration_workflow(cases_path=_CASES_PATH)
    out_path = Path.cwd() / "test_calibration_report_integration.json"
    try:
        out = save_calibration_report(report, out_path)
        assert out.exists()

        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["schema_version"] == "1.0"
        assert loaded["coverage_pct"] == 100.0
        assert len(loaded["cases"]) == report.n_cases_total
        for orig, reloaded in zip(report.cases, loaded["cases"]):
            assert reloaded["case_id"] == orig.case_id
            assert abs(reloaded["position_error_m"] - orig.position_error_m) < 1e-9
            assert abs(reloaded["velocity_error_mps"] - orig.velocity_error_mps) < 1e-9
            assert reloaded["passed"] == orig.passed
    finally:
        out_path.unlink(missing_ok=True)

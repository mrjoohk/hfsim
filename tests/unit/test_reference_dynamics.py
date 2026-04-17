"""Unit tests for uf.reference_dynamics (C1 — RK4 reference model)."""

from __future__ import annotations

import math

import pytest

from hf_sim.models import AtmosphereState, DynamicsControl, OwnshipState, SixDofComparisonResult
from uf.reference_dynamics import (
    build_standard_maneuver_library,
    compare_6dof_euler_vs_rk4,
    propagate_ownship_euler,
    propagate_ownship_rk4,
    run_maneuver_regression_suite,
    run_6dof_comparison_trajectory,
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

def _ownship() -> OwnshipState:
    return OwnshipState(
        position_m=[0.0, 0.0, 1000.0],
        velocity_mps=[200.0, 0.0, 0.0],
        quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
        angular_rate_rps=[0.0, 0.0, 0.0],
        mass_kg=9000.0,
        aero_params={"drag_coeff": 0.02, "max_thrust_n": 20000.0, "lift_gain": 9.0},
    )


def _control() -> DynamicsControl:
    return DynamicsControl(throttle=0.6, body_rate_cmd_rps=[0.0, 0.0, 0.0], load_factor_cmd=1.0)


def _atm() -> AtmosphereState:
    return AtmosphereState(density_kgpm3=1.225, wind_vector_mps=[0.0, 0.0, 0.0], turbulence_level=0.0)


# ---------------------------------------------------------------------------
# RK4 produces finite state
# ---------------------------------------------------------------------------

def test_rk4_produces_finite_position():
    state = propagate_ownship_rk4(_ownship(), _control(), _atm(), dt=0.01)
    assert all(math.isfinite(v) for v in state.position_m)


def test_rk4_produces_finite_velocity():
    state = propagate_ownship_rk4(_ownship(), _control(), _atm(), dt=0.01)
    assert all(math.isfinite(v) for v in state.velocity_mps)


def test_rk4_quaternion_normalized():
    state = propagate_ownship_rk4(_ownship(), _control(), _atm(), dt=0.01)
    q_norm = math.sqrt(sum(v * v for v in state.quaternion_wxyz))
    assert abs(q_norm - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Euler and RK4 differ (distinct integration methods)
# ---------------------------------------------------------------------------

def test_euler_and_rk4_positions_differ():
    """Euler and RK4 must produce slightly different positions (not identical)."""
    euler = propagate_ownship_euler(_ownship(), _control(), _atm(), dt=0.01)
    rk4 = propagate_ownship_rk4(_ownship(), _control(), _atm(), dt=0.01)
    # They should be close but not identical
    diff = math.sqrt(sum((e - r) ** 2 for e, r in zip(euler.position_m, rk4.position_m)))
    assert diff > 0.0, "Euler and RK4 produced identical positions — methods are not distinct"


# ---------------------------------------------------------------------------
# dt convergence: smaller dt → smaller Euler-RK4 difference
# ---------------------------------------------------------------------------

def test_smaller_dt_reduces_euler_rk4_error():
    """At smaller dt, Euler and RK4 converge — verifies integration order effect."""
    ownship = _ownship()
    control = _control()
    atm = _atm()

    result_coarse = compare_6dof_euler_vs_rk4(ownship, control, atm, dt=0.01)
    result_fine = compare_6dof_euler_vs_rk4(ownship, control, atm, dt=0.001)

    assert result_fine.position_error_m <= result_coarse.position_error_m, (
        "Expected finer dt to reduce Euler-RK4 error; got "
        f"coarse={result_coarse.position_error_m:.2e}, fine={result_fine.position_error_m:.2e}"
    )


# ---------------------------------------------------------------------------
# compare_6dof_euler_vs_rk4
# ---------------------------------------------------------------------------

def test_compare_returns_six_dof_comparison_result():
    result = compare_6dof_euler_vs_rk4(_ownship(), _control(), _atm(), dt=0.01)
    assert isinstance(result, SixDofComparisonResult)


def test_compare_errors_are_finite():
    result = compare_6dof_euler_vs_rk4(_ownship(), _control(), _atm(), dt=0.01)
    assert math.isfinite(result.position_error_m)
    assert math.isfinite(result.velocity_error_mps)


def test_compare_errors_are_nonnegative():
    result = compare_6dof_euler_vs_rk4(_ownship(), _control(), _atm(), dt=0.01)
    assert result.position_error_m >= 0.0
    assert result.velocity_error_mps >= 0.0


def test_compare_euler_and_rk4_positions_embedded():
    result = compare_6dof_euler_vs_rk4(_ownship(), _control(), _atm(), dt=0.01, step=42)
    assert result.step == 42
    assert len(result.euler_position_m) == 3
    assert len(result.rk4_position_m) == 3
    assert all(math.isfinite(v) for v in result.euler_position_m)
    assert all(math.isfinite(v) for v in result.rk4_position_m)


# ---------------------------------------------------------------------------
# run_6dof_comparison_trajectory
# ---------------------------------------------------------------------------

def test_trajectory_output_length_matches_controls():
    controls = [_control()] * 50
    results = run_6dof_comparison_trajectory(_ownship(), controls, _atm(), dt=0.01)
    assert len(results) == 50


def test_trajectory_step_indices_sequential():
    controls = [_control()] * 10
    results = run_6dof_comparison_trajectory(_ownship(), controls, _atm(), dt=0.01)
    for i, r in enumerate(results):
        assert r.step == i


def test_trajectory_all_errors_finite():
    controls = [_control()] * 100
    results = run_6dof_comparison_trajectory(_ownship(), controls, _atm(), dt=0.01)
    for r in results:
        assert math.isfinite(r.position_error_m)
        assert math.isfinite(r.velocity_error_mps)


def test_standard_maneuver_library_includes_regression_scenarios():
    maneuvers = build_standard_maneuver_library()
    assert {m.name for m in maneuvers} >= {
        "straight_hold",
        "throttle_step",
        "pitch_doublet",
        "roll_doublet",
        "coordinated_turn_like",
    }


def test_run_maneuver_regression_suite_returns_named_summaries():
    report = run_maneuver_regression_suite(_ownship(), _atm(), dt=0.01)
    assert report.scenario_count >= 5
    assert len(report.scenario_results) == report.scenario_count
    assert all(result.peak_position_error_m >= result.mean_position_error_m for result in report.scenario_results)

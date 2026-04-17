"""Integration tests for 6-DoF secondary validation (C1 - Euler vs RK4)."""

from __future__ import annotations

import math

from hf_sim.models import AtmosphereState, DynamicsControl, OwnshipState
from uf.reference_dynamics import (
    build_standard_maneuver_library,
    run_maneuver_regression_suite,
    run_6dof_comparison_trajectory,
)


def _ownship(aero_params: dict | None = None) -> OwnshipState:
    aero = aero_params or {"drag_coeff": 0.02, "max_thrust_n": 20000.0, "lift_gain": 9.0}
    return OwnshipState(
        position_m=[0.0, 0.0, 1000.0],
        velocity_mps=[200.0, 0.0, 0.0],
        quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
        angular_rate_rps=[0.0, 0.0, 0.0],
        mass_kg=9000.0,
        aero_params=aero,
    )


def _control(throttle: float = 0.6) -> DynamicsControl:
    return DynamicsControl(
        throttle=throttle,
        body_rate_cmd_rps=[0.0, 0.0, 0.0],
        load_factor_cmd=1.0,
    )


def _atm() -> AtmosphereState:
    return AtmosphereState(
        density_kgpm3=1.225,
        wind_vector_mps=[5.0, 0.0, 0.0],
        turbulence_level=0.1,
    )


def test_600_step_trajectory_mean_position_error_within_bound():
    controls = [_control()] * 600
    results = run_6dof_comparison_trajectory(_ownship(), controls, _atm(), dt=0.01)
    mean_error = sum(result.position_error_m for result in results) / len(results)
    assert mean_error <= 5.0


def test_comparison_trajectory_deterministic():
    controls = [_control()] * 100
    first = run_6dof_comparison_trajectory(_ownship(), controls, _atm(), dt=0.01)
    second = run_6dof_comparison_trajectory(_ownship(), controls, _atm(), dt=0.01)
    for left, right in zip(first, second):
        assert left.position_error_m == right.position_error_m
        assert left.velocity_error_mps == right.velocity_error_mps


def test_extreme_params_no_nan():
    extreme_aero = {"drag_coeff": 0.10, "max_thrust_n": 5000.0, "lift_gain": 3.0}
    controls = [_control(throttle=0.3)] * 200
    results = run_6dof_comparison_trajectory(_ownship(extreme_aero), controls, _atm(), dt=0.01)
    for result in results:
        assert math.isfinite(result.position_error_m)
        assert math.isfinite(result.velocity_error_mps)


def test_output_length_matches_controls_1200():
    controls = [_control()] * 1200
    results = run_6dof_comparison_trajectory(_ownship(), controls, _atm(), dt=0.01)
    assert len(results) == 1200


def test_regression_suite_mean_and_peak_errors_remain_bounded():
    report = run_maneuver_regression_suite(
        _ownship(),
        _atm(),
        dt=0.01,
        maneuvers=build_standard_maneuver_library(),
    )
    assert report.scenario_count >= 5
    assert all(result.mean_position_error_m <= 5.0 for result in report.scenario_results)
    assert all(result.peak_position_error_m <= 10.0 for result in report.scenario_results)

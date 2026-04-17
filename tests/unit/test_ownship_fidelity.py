from hf_sim.models import (
    AtmosphereState,
    EnvironmentRuntime,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
)
from hf_sim.ownship_fidelity import (
    build_standard_maneuver_library,
    run_ownship_fidelity_gate,
    rollout_control_response,
    summarize_control_response,
)


def _runtime() -> EnvironmentRuntime:
    return EnvironmentRuntime(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, 1000.0],
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.01, "max_thrust_n": 30000.0, "lift_gain": 8.0},
        ),
        threats=[],
        targets=[],
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 110.0, 120.0], flags={}),
        radar=RadarState(track_ids=[], detected_ranges_m=[]),
        sensor=SensorState(contact_count=0, quality=1.0),
        atmosphere=AtmosphereState(density_kgpm3=1.225, wind_vector_mps=[0.0, 0.0, 0.0], turbulence_level=0.05),
        rng_state={"seed": 9, "step_index": 0},
        mode_flags={"agent_count": 1},
        dt_internal=0.01,
        calibration_config={},
    )


def test_standard_maneuver_library_contains_expected_controls():
    maneuvers = build_standard_maneuver_library()
    names = {maneuver.name for maneuver in maneuvers}
    assert {"straight_hold", "throttle_step", "pitch_doublet", "roll_doublet", "yaw_pulse", "load_factor_hold", "coordinated_turn_like"} <= names


def test_throttle_step_reports_speed_response():
    maneuver = next(m for m in build_standard_maneuver_library() if m.name == "throttle_step")
    states = rollout_control_response(_runtime(), maneuver.controls)
    metrics = summarize_control_response(maneuver.name, states, maneuver.expected_signal)
    assert metrics.final_speed_mps > metrics.initial_speed_mps
    assert metrics.response_latency_steps < metrics.n_steps
    assert metrics.finite_state is True
    assert metrics.monotonic_sim_time is True


def test_pitch_doublet_reports_pitch_rate_response():
    maneuver = next(m for m in build_standard_maneuver_library() if m.name == "pitch_doublet")
    states = rollout_control_response(_runtime(), maneuver.controls)
    metrics = summarize_control_response(maneuver.name, states, maneuver.expected_signal)
    assert metrics.max_abs_angular_rate_rps > 0.0
    assert metrics.quaternion_norm_error_max <= 1e-6


def test_fidelity_gate_runs_all_scenarios_with_monotonic_time():
    reports = run_ownship_fidelity_gate(_runtime())
    assert len(reports) >= 5
    assert all(report.finite_state for report in reports)
    assert all(report.monotonic_sim_time for report in reports)

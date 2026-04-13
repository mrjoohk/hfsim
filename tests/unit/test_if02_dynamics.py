import math

import pytest

from hf_sim.models import (
    AtmosphereState,
    DynamicsControl,
    DynamicsStepRequest,
    EnvironmentRuntime,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
    TargetState,
    ThreatState,
)
from uf.if02_dynamics import (
    apply_aero_calibration,
    compute_atmosphere_adjustment,
    compose_step_result,
    decode_state_bundle,
    propagate_ownship_6dof,
    propagate_target_environment,
    propagate_threat_kinematics,
    step_environment_runtime,
    update_sensor_state,
)


def _request():
    return DynamicsStepRequest(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, 1000.0],
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.01, "max_thrust_n": 30000.0, "lift_gain": 8.0},
        ),
        threats=[ThreatState(identifier="th-1", position_m=[2000.0, 0.0, 1000.0], velocity_mps=[-20.0, 0.0, 0.0])],
        targets=[TargetState(identifier="tg-1", position_m=[5000.0, 0.0, 0.0], velocity_mps=[0.0, 0.0, 0.0])],
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 110.0, 120.0], flags={}),
        radar=RadarState(track_ids=[], detected_ranges_m=[]),
        sensor=SensorState(contact_count=0, quality=1.0),
        atmosphere=AtmosphereState(density_kgpm3=1.225, wind_vector_mps=[0.0, 0.0, 0.0], turbulence_level=0.1),
        control=DynamicsControl(throttle=0.6, body_rate_cmd_rps=[0.1, 0.1, 0.0], load_factor_cmd=1.0),
        dt_internal=0.01,
        agent_count=4,
        rng_state={"seed": 11, "step_index": 0},
        mode_flags={"agent_count": 4},
        calibration_config={"velocity_scale": 1.0},
    )


def _runtime(
    *,
    throttle: float = 0.6,
    roll: float = 0.0,
    pitch: float = 0.0,
    drag_coeff: float = 0.01,
    max_thrust_n: float = 30000.0,
    density_kgpm3: float = 1.225,
    wind_vector_mps: list[float] | None = None,
    turbulence_level: float = 0.1,
):
    request = _request()
    request.ownship.aero_params["drag_coeff"] = drag_coeff
    request.ownship.aero_params["max_thrust_n"] = max_thrust_n
    request.atmosphere = AtmosphereState(
        density_kgpm3=density_kgpm3,
        wind_vector_mps=list(wind_vector_mps or [0.0, 0.0, 0.0]),
        turbulence_level=turbulence_level,
    )
    request.control = DynamicsControl(
        throttle=throttle,
        body_rate_cmd_rps=[roll, pitch, 0.0],
        load_factor_cmd=1.0,
    )
    return EnvironmentRuntime(
        ownship=request.ownship,
        threats=request.threats,
        targets=request.targets,
        environment=request.environment,
        radar=request.radar,
        sensor=request.sensor,
        atmosphere=request.atmosphere,
        rng_state=request.rng_state,
        mode_flags=request.mode_flags,
        dt_internal=request.dt_internal,
        calibration_config=request.calibration_config,
    ), request.control


def _roll(runtime: EnvironmentRuntime, control: DynamicsControl, steps: int) -> EnvironmentRuntime:
    rolled = runtime
    for _ in range(steps):
        rolled = step_environment_runtime(rolled, control)
    return rolled


def test_if02_uf_chain_returns_finite_state():
    entity = decode_state_bundle(_request())
    ownship = propagate_ownship_6dof(entity)
    threat = propagate_threat_kinematics(ownship)
    environment = propagate_target_environment(threat)
    calibrated = apply_aero_calibration(environment)
    result = compose_step_result(calibrated)
    assert all(math.isfinite(value) for value in result.ownship.position_m + result.ownship.velocity_mps)


def test_decode_state_bundle_invalid_dt_raises():
    request = _request()
    request.dt_internal = 0.1
    with pytest.raises(ValueError):
        decode_state_bundle(request)


def test_if02_600s_ownship_stability_acceptance():
    runtime, control = _runtime()
    rolled = _roll(runtime, control, steps=int(600.0 / runtime.dt_internal))
    values = (
        rolled.ownship.position_m
        + rolled.ownship.velocity_mps
        + rolled.ownship.quaternion_wxyz
        + rolled.ownship.angular_rate_rps
    )
    assert all(math.isfinite(value) for value in values)
    q_norm = math.sqrt(sum(component * component for component in rolled.ownship.quaternion_wxyz))
    assert abs(q_norm - 1.0) <= 1e-6


def test_if02_deterministic_replay_acceptance():
    runtime_a, control_a = _runtime()
    runtime_b, control_b = _runtime()
    rolled_a = _roll(runtime_a, control_a, steps=400)
    rolled_b = _roll(runtime_b, control_b, steps=400)
    state_a = (
        rolled_a.ownship.position_m
        + rolled_a.ownship.velocity_mps
        + rolled_a.ownship.quaternion_wxyz
        + rolled_a.ownship.angular_rate_rps
        + [rolled_a.sensor.quality, rolled_a.sensor.detection_confidence, rolled_a.atmosphere.density_kgpm3]
    )
    state_b = (
        rolled_b.ownship.position_m
        + rolled_b.ownship.velocity_mps
        + rolled_b.ownship.quaternion_wxyz
        + rolled_b.ownship.angular_rate_rps
        + [rolled_b.sensor.quality, rolled_b.sensor.detection_confidence, rolled_b.atmosphere.density_kgpm3]
    )
    assert max(abs(a - b) for a, b in zip(state_a, state_b)) <= 1e-6


def test_if02_throttle_sanity_acceptance():
    low_runtime, low_control = _runtime(throttle=0.2)
    high_runtime, high_control = _runtime(throttle=0.8)
    low_rolled = _roll(low_runtime, low_control, steps=100)
    high_rolled = _roll(high_runtime, high_control, steps=100)
    low_speed = math.sqrt(sum(component * component for component in low_rolled.ownship.velocity_mps))
    high_speed = math.sqrt(sum(component * component for component in high_rolled.ownship.velocity_mps))
    assert high_speed > low_speed
    assert (high_speed - low_speed) > 1e-3


def test_if02_pitch_sanity_acceptance():
    pos_runtime, pos_control = _runtime(pitch=0.15)
    neg_runtime, neg_control = _runtime(pitch=-0.15)
    pos_rolled = _roll(pos_runtime, pos_control, steps=50)
    neg_rolled = _roll(neg_runtime, neg_control, steps=50)
    assert pos_rolled.ownship.angular_rate_rps[1] > 0.0
    assert neg_rolled.ownship.angular_rate_rps[1] < 0.0


def test_if02_roll_sanity_acceptance():
    pos_runtime, pos_control = _runtime(roll=0.15)
    neg_runtime, neg_control = _runtime(roll=-0.15)
    pos_rolled = _roll(pos_runtime, pos_control, steps=50)
    neg_rolled = _roll(neg_runtime, neg_control, steps=50)
    assert pos_rolled.ownship.angular_rate_rps[0] > 0.0
    assert neg_rolled.ownship.angular_rate_rps[0] < 0.0


def test_if02_parameter_sensitivity_acceptance():
    high_thrust_runtime, high_thrust_control = _runtime(max_thrust_n=32000.0)
    low_thrust_runtime, low_thrust_control = _runtime(max_thrust_n=22000.0)
    high_drag_runtime, high_drag_control = _runtime(drag_coeff=0.03)
    low_drag_runtime, low_drag_control = _runtime(drag_coeff=0.005)

    high_thrust = _roll(high_thrust_runtime, high_thrust_control, steps=100)
    low_thrust = _roll(low_thrust_runtime, low_thrust_control, steps=100)
    high_drag = _roll(high_drag_runtime, high_drag_control, steps=100)
    low_drag = _roll(low_drag_runtime, low_drag_control, steps=100)

    assert high_thrust.ownship.velocity_mps[0] > low_thrust.ownship.velocity_mps[0]
    assert high_drag.ownship.velocity_mps[0] < low_drag.ownship.velocity_mps[0]


def test_if02_atmosphere_influence_helper_reflects_density_and_wind():
    request = _request()
    request.atmosphere = AtmosphereState(
        density_kgpm3=0.95,
        wind_vector_mps=[15.0, 0.0, -3.0],
        turbulence_level=0.4,
    )
    adjustment = compute_atmosphere_adjustment(request.ownship, request.atmosphere)
    assert adjustment["density_scale"] < 1.0
    assert adjustment["wind_speed_mps"] > 0.0
    assert adjustment["airspeed_mps"] > 0.0


def test_if02_sensor_state_degrades_with_harsher_atmosphere():
    request = _request()
    baseline = update_sensor_state(request.ownship, request.threats, request.atmosphere, request.radar, request.sensor)
    harsher = update_sensor_state(
        request.ownship,
        request.threats,
        AtmosphereState(density_kgpm3=0.8, wind_vector_mps=[20.0, 0.0, 0.0], turbulence_level=0.8),
        request.radar,
        request.sensor,
    )
    assert harsher.quality < baseline.quality
    assert harsher.detection_confidence <= baseline.detection_confidence


def test_if02_atmosphere_sensitivity_acceptance():
    calm_runtime, calm_control = _runtime(
        density_kgpm3=1.225,
        wind_vector_mps=[0.0, 0.0, 0.0],
        turbulence_level=0.05,
    )
    harsh_runtime, harsh_control = _runtime(
        density_kgpm3=0.9,
        wind_vector_mps=[12.0, 3.0, 2.0],
        turbulence_level=0.6,
    )
    calm = _roll(calm_runtime, calm_control, steps=150)
    harsh = _roll(harsh_runtime, harsh_control, steps=150)

    calm_speed = math.sqrt(sum(component * component for component in calm.ownship.velocity_mps))
    harsh_speed = math.sqrt(sum(component * component for component in harsh.ownship.velocity_mps))
    altitude_delta = abs(harsh.ownship.position_m[2] - calm.ownship.position_m[2])

    assert harsh.sensor.quality < calm.sensor.quality
    assert harsh_speed != pytest.approx(calm_speed)
    assert altitude_delta > 0.0


def test_if02_sensor_continuity_acceptance():
    baseline_runtime, baseline_control = _runtime(turbulence_level=0.1)
    baseline = _roll(baseline_runtime, baseline_control, steps=20)
    nearby_runtime, nearby_control = _runtime(turbulence_level=0.12)
    nearby = _roll(nearby_runtime, nearby_control, steps=20)
    assert abs(nearby.sensor.quality - baseline.sensor.quality) < 0.1
    assert abs(nearby.sensor.detection_confidence - baseline.sensor.detection_confidence) < 0.1

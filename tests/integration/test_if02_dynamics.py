import importlib

from hf_sim.models import (
    AtmosphereState,
    DynamicsControl,
    DynamicsStepRequest,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
    TargetState,
    ThreatState,
)


def test_if02_environment_step_acceptance():
    module = importlib.import_module("if.if02_dynamics")
    result = module.if_02_advance_motion_model_stack(
        DynamicsStepRequest(
            ownship=OwnshipState(
                position_m=[0.0, 0.0, 1000.0],
                velocity_mps=[200.0, 0.0, 0.0],
                quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
                angular_rate_rps=[0.0, 0.0, 0.0],
                mass_kg=9000.0,
                aero_params={"drag_coeff": 0.01, "max_thrust_n": 30000.0, "lift_gain": 8.0},
            ),
            threats=[ThreatState(identifier="th-1", position_m=[2000.0, 0.0, 1000.0], velocity_mps=[0.0, 0.0, 0.0])],
            targets=[TargetState(identifier="tg-1", position_m=[5000.0, 0.0, 0.0], velocity_mps=[0.0, 0.0, 0.0])],
            environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 120.0], flags={}),
            radar=RadarState(track_ids=[], detected_ranges_m=[]),
            sensor=SensorState(contact_count=0, quality=1.0),
            atmosphere=AtmosphereState(density_kgpm3=1.225, wind_vector_mps=[0.0, 0.0, 0.0], turbulence_level=0.1),
            control=DynamicsControl(throttle=0.5, body_rate_cmd_rps=[0.1, 0.1, 0.0], load_factor_cmd=1.0),
            dt_internal=0.01,
            agent_count=4,
            rng_state={"seed": 7, "step_index": 0},
            mode_flags={"agent_count": 4},
            calibration_config={"velocity_scale": 1.0},
        )
    )
    assert result.environment.sim_time_s == 0.01
    assert result.sensor.contact_count >= 0
    assert len(result.radar.track_ids) == 1


def test_if02_contract_shape_acceptance():
    module = importlib.import_module("if.if02_dynamics")
    result = module.if_02_advance_motion_model_stack(
        DynamicsStepRequest(
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
            environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 120.0], flags={}),
            radar=RadarState(track_ids=[], detected_ranges_m=[]),
            sensor=SensorState(contact_count=0, quality=1.0),
            atmosphere=AtmosphereState(density_kgpm3=1.225, wind_vector_mps=[0.0, 0.0, 0.0], turbulence_level=0.0),
            control=DynamicsControl(throttle=0.4, body_rate_cmd_rps=[0.0, 0.0, 0.0], load_factor_cmd=1.0),
            dt_internal=0.01,
            agent_count=1,
            rng_state={"seed": 3, "step_index": 0},
            mode_flags={"agent_count": 1},
            calibration_config={},
        )
    )
    assert len(result.ownship.position_m) == 3
    assert len(result.ownship.quaternion_wxyz) == 4
    assert result.event_flags["nonfinite"] is False


# ---------------------------------------------------------------------------
# Threat + Radar Integration Acceptance Tests
# ---------------------------------------------------------------------------

def _base_request_with_threats(threats: list[ThreatState]) -> DynamicsStepRequest:
    return DynamicsStepRequest(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, 1000.0],
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.01, "max_thrust_n": 30000.0, "lift_gain": 8.0},
        ),
        threats=threats,
        targets=[TargetState(identifier="tg-1", position_m=[5000.0, 0.0, 0.0], velocity_mps=[0.0, 0.0, 0.0])],
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 120.0], flags={}),
        radar=RadarState(track_ids=[], detected_ranges_m=[]),
        sensor=SensorState(contact_count=0, quality=1.0),
        atmosphere=AtmosphereState(density_kgpm3=1.225, wind_vector_mps=[0.0, 0.0, 0.0], turbulence_level=0.0),
        control=DynamicsControl(throttle=0.5, body_rate_cmd_rps=[0.0, 0.0, 0.0], load_factor_cmd=1.0),
        dt_internal=0.01,
        agent_count=4,
        rng_state={"seed": 77, "step_index": 0},
        mode_flags={"agent_count": 4},
        calibration_config={},
    )


def test_if02_threat_radar_long_horizon_acceptance():
    """Two threats tracked over 600 steps — positions finite, track_ids stable."""
    import importlib as _il
    from uf.if02_dynamics import step_environment_runtime
    from hf_sim.models import EnvironmentRuntime

    module = _il.import_module("if.if02_dynamics")
    threats = [
        ThreatState(identifier="th-1", position_m=[3000.0, 0.0, 1000.0], velocity_mps=[-20.0, 0.0, 0.0]),
        ThreatState(identifier="th-2", position_m=[4000.0, 500.0, 900.0], velocity_mps=[-15.0, 0.0, 0.0]),
    ]
    req = _base_request_with_threats(threats)
    runtime = EnvironmentRuntime(
        ownship=req.ownship,
        threats=req.threats,
        targets=req.targets,
        environment=req.environment,
        radar=req.radar,
        sensor=req.sensor,
        atmosphere=req.atmosphere,
        rng_state=req.rng_state,
        mode_flags=req.mode_flags,
        dt_internal=req.dt_internal,
        calibration_config=req.calibration_config,
    )

    for _ in range(600):
        runtime = step_environment_runtime(runtime, req.control)

    for threat in runtime.threats:
        assert all(
            __import__("math").isfinite(v) for v in threat.position_m
        ), f"threat {threat.identifier} position non-finite"

    assert set(runtime.radar.track_ids) == {"th-1", "th-2"}
    assert len(runtime.radar.detected_ranges_m) == 2
    assert all(__import__("math").isfinite(r) for r in runtime.radar.detected_ranges_m)


def test_if02_threat_detection_range_acceptance():
    """Near threat detected; far threat outside detection range — sensor reflects difference."""
    import importlib as _il
    from uf.if02_dynamics import step_environment_runtime
    from hf_sim.models import EnvironmentRuntime

    def _make_runtime(threat_pos: list[float]) -> EnvironmentRuntime:
        req = _base_request_with_threats([
            ThreatState(identifier="th-x", position_m=threat_pos, velocity_mps=[0.0, 0.0, 0.0])
        ])
        return EnvironmentRuntime(
            ownship=req.ownship,
            threats=req.threats,
            targets=req.targets,
            environment=req.environment,
            radar=req.radar,
            sensor=req.sensor,
            atmosphere=req.atmosphere,
            rng_state=req.rng_state,
            mode_flags=req.mode_flags,
            dt_internal=req.dt_internal,
            calibration_config=req.calibration_config,
        )

    near_rt = step_environment_runtime(_make_runtime([1000.0, 0.0, 1000.0]), _base_request_with_threats([]).control)
    far_rt  = step_environment_runtime(_make_runtime([15000.0, 0.0, 1000.0]), _base_request_with_threats([]).control)

    assert near_rt.sensor.contact_count >= 1, "Near threat should be detected"
    assert near_rt.sensor.detection_confidence > 0.0
    assert far_rt.sensor.contact_count == 0, "Far threat should not be detected"
    assert far_rt.sensor.detection_confidence == 0.0

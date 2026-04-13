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

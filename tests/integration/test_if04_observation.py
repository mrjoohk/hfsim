import importlib

from hf_sim.models import EnvironmentState, ObservationRequest, OwnshipState, ThreatState


def test_if04_observation_acceptance():
    module = importlib.import_module("if.if04_observation")
    result = module.if_04_build_structured_observation(
        ObservationRequest(
            ownships=[
                OwnshipState(
                    position_m=[0.0, 0.0, 1000.0],
                    velocity_mps=[200.0, 0.0, 0.0],
                    quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
                    angular_rate_rps=[0.0, 0.0, 0.0],
                    mass_kg=9000.0,
                    aero_params={"drag_coeff": 0.01},
                )
            ],
            threats=[ThreatState(identifier="th-1", position_m=[1000.0, 100.0, 1000.0], velocity_mps=[0.0, 0.0, 0.0])],
            environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 110.0], flags={}),
        )
    )
    assert result.schema_version == "1.0"


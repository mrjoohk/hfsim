import pytest

from hf_sim.models import EnvironmentState, ObservationRequest, OwnshipState, ThreatState
from uf.if04_observation import (
    assemble_observation_batch,
    build_observation_masks,
    extract_terrain_features,
    extract_threat_features,
    extract_vehicle_features,
    normalize_observation_features,
)


def _request():
    return ObservationRequest(
        ownships=[
            OwnshipState(
                position_m=[0.0, 0.0, 1000.0],
                velocity_mps=[200.0, 5.0, -1.0],
                quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
                angular_rate_rps=[0.01, 0.02, 0.03],
                mass_kg=9000.0,
                aero_params={"drag_coeff": 0.01},
            )
        ],
        threats=[ThreatState(identifier="th", position_m=[1000.0, 200.0, 1100.0], velocity_mps=[0.0, 0.0, 0.0])],
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 105.0, 110.0], flags={}),
    )


def test_if04_uf_chain_builds_observation_batch():
    vehicle = extract_vehicle_features(_request())
    terrain = extract_terrain_features(vehicle)
    threat = extract_threat_features(terrain)
    normalized = normalize_observation_features(threat)
    assembly = build_observation_masks(normalized)
    batch = assemble_observation_batch(assembly)
    assert batch.schema_version == "1.0"
    assert len(batch.features[0]) == len(batch.masks[0])


def test_extract_vehicle_features_none_raises():
    with pytest.raises(ValueError):
        extract_vehicle_features(None)


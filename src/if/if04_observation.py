"""IF-04 integration module."""

from __future__ import annotations

from hf_sim.models import ObservationBatch, ObservationRequest
from uf.if04_observation import (
    assemble_observation_batch,
    build_observation_masks,
    extract_terrain_features,
    extract_threat_features,
    extract_vehicle_features,
    normalize_observation_features,
)


def if_04_build_structured_observation(observation_request: ObservationRequest) -> ObservationBatch:
    """Convert simulator state into structured learning observations."""
    vehicle_context = extract_vehicle_features(observation_request)
    terrain_context = extract_terrain_features(vehicle_context)
    threat_context = extract_threat_features(terrain_context)
    normalized_features = normalize_observation_features(threat_context)
    assembly_context = build_observation_masks(normalized_features)
    assembly_context.extension_channels = dict(observation_request.extension_channels)
    return assemble_observation_batch(assembly_context)


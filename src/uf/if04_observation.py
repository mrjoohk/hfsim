"""UF implementations for IF-04 observation construction."""

from __future__ import annotations

import math

from hf_sim.models import (
    ObservationAssemblyContext,
    ObservationBatch,
    ObservationFeatureSet,
    ObservationRequest,
    TerrainFeatureContext,
    ThreatFeatureContext,
    VehicleFeatureContext,
)


def extract_vehicle_features(observation_request: ObservationRequest) -> VehicleFeatureContext:
    """Extract vehicle state features."""
    if observation_request is None:
        raise ValueError("observation_request cannot be None")
    vehicle_features: list[list[float]] = []
    masks: list[list[int]] = []
    for ownship in observation_request.ownships:
        if ownship.position_m is None:
            raise KeyError("position_m")
        values = list(ownship.position_m) + list(ownship.velocity_mps) + list(ownship.angular_rate_rps)
        mask = [1] * len(values)
        for index, value in enumerate(values):
            if not math.isfinite(value):
                values[index] = 0.0
                mask[index] = 0
        vehicle_features.append(values)
        masks.append(mask)
    return VehicleFeatureContext(
        ownships=observation_request.ownships,
        threats=observation_request.threats,
        environment=observation_request.environment,
        vehicle_features=vehicle_features,
        masks=masks,
    )


def extract_terrain_features(vehicle_feature_context: VehicleFeatureContext) -> TerrainFeatureContext:
    """Extract terrain-relative features."""
    if not vehicle_feature_context.environment.terrain_reference:
        raise ValueError("terrain source required")
    terrain_features: list[list[float]] = []
    max_height = max(vehicle_feature_context.environment.terrain_reference)
    for ownship in vehicle_feature_context.ownships:
        altitude = ownship.position_m[2]
        mean_height = sum(vehicle_feature_context.environment.terrain_reference) / len(vehicle_feature_context.environment.terrain_reference)
        terrain_features.append([altitude - mean_height, altitude - max_height, max_height])
    return TerrainFeatureContext(
        ownships=vehicle_feature_context.ownships,
        threats=vehicle_feature_context.threats,
        environment=vehicle_feature_context.environment,
        vehicle_features=vehicle_feature_context.vehicle_features,
        terrain_features=terrain_features,
        masks=vehicle_feature_context.masks,
    )


def extract_threat_features(terrain_feature_context: TerrainFeatureContext) -> ThreatFeatureContext:
    """Extract threat-relative features."""
    threat_features: list[list[float]] = []
    for ownship in terrain_feature_context.ownships:
        if not terrain_feature_context.threats:
            threat_features.append([0.0, 0.0, 0.0, 0.0])
            continue
        nearest = min(
            terrain_feature_context.threats,
            key=lambda threat: sum((threat.position_m[idx] - ownship.position_m[idx]) ** 2 for idx in range(3)),
        )
        dx = nearest.position_m[0] - ownship.position_m[0]
        dy = nearest.position_m[1] - ownship.position_m[1]
        dz = nearest.position_m[2] - ownship.position_m[2]
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        threat_features.append([dx, dy, dz, distance])
    return ThreatFeatureContext(
        ownships=terrain_feature_context.ownships,
        environment=terrain_feature_context.environment,
        vehicle_features=terrain_feature_context.vehicle_features,
        terrain_features=terrain_feature_context.terrain_features,
        threat_features=threat_features,
        masks=terrain_feature_context.masks,
    )


def normalize_observation_features(threat_feature_context: ThreatFeatureContext) -> ObservationFeatureSet:
    """Normalize observation features."""
    if not threat_feature_context.vehicle_features:
        raise ValueError("normalization config required")
    features: list[list[float]] = []
    clip_events = 0
    for vehicle, terrain, threat in zip(
        threat_feature_context.vehicle_features,
        threat_feature_context.terrain_features,
        threat_feature_context.threat_features,
    ):
        raw = vehicle + terrain + threat
        normalized: list[float] = []
        for value in raw:
            scaled = value / 1000.0
            clipped = min(1.0, max(-1.0, scaled))
            if clipped != scaled:
                clip_events += 1
            normalized.append(clipped)
        features.append(normalized)
    expected_width = len(threat_feature_context.vehicle_features[0]) + len(threat_feature_context.terrain_features[0]) + len(threat_feature_context.threat_features[0])
    if any(len(row) != expected_width for row in features):
        raise ValueError("feature width mismatch")
    return ObservationFeatureSet(features=features, masks=threat_feature_context.masks, clip_events=clip_events)


def build_observation_masks(normalized_features: ObservationFeatureSet) -> ObservationAssemblyContext:
    """Build observation masks."""
    if not normalized_features.features:
        return ObservationAssemblyContext(normalized_features=normalized_features, observation_masks=[[0]], extension_channels={})
    observation_masks: list[list[int]] = []
    for row in normalized_features.features:
        mask = [0 if abs(value) < 1e-12 else 1 for value in row]
        observation_masks.append(mask)
    return ObservationAssemblyContext(
        normalized_features=normalized_features,
        observation_masks=observation_masks,
        extension_channels={},
    )


def assemble_observation_batch(observation_assembly_context: ObservationAssemblyContext) -> ObservationBatch:
    """Assemble backward-compatible observation batch."""
    if observation_assembly_context.observation_masks is None:
        raise RuntimeError("observation_masks missing")
    if any(key in {"features", "masks", "schema_version"} for key in observation_assembly_context.extension_channels):
        raise ValueError("reserved extension key")
    return ObservationBatch(
        features=observation_assembly_context.normalized_features.features,
        masks=observation_assembly_context.observation_masks,
        schema_version="1.0",
        extension_channels=dict(observation_assembly_context.extension_channels),
    )

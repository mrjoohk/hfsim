"""Validation logging helpers for deterministic replay and viewer playback."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

from hf_sim.models import BranchRuntimeResult, DynamicsControl, EnvironmentRuntime


def _vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))


def _coerce_control(control: DynamicsControl | dict[str, Any]) -> dict[str, Any]:
    if isinstance(control, dict):
        return {
            "throttle": float(control.get("throttle", 0.0)),
            "body_rate_cmd_rps": [
                float(control.get("roll", 0.0)),
                float(control.get("pitch", 0.0)),
                float(control.get("yaw", 0.0)),
            ],
            "load_factor_cmd": float(control.get("load_factor", control.get("load_factor_cmd", 1.0))),
        }
    return {
        "throttle": float(control.throttle),
        "body_rate_cmd_rps": [float(value) for value in control.body_rate_cmd_rps],
        "load_factor_cmd": float(control.load_factor_cmd),
    }


def _quaternion_to_euler_deg(quaternion_wxyz: list[float]) -> dict[str, float]:
    w, x, y, z = quaternion_wxyz
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.degrees(math.copysign(math.pi / 2.0, sinp))
    else:
        pitch = math.degrees(math.asin(sinp))

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.degrees(math.atan2(siny_cosp, cosy_cosp))
    heading = (yaw + 360.0) % 360.0
    return {
        "roll_deg": float(roll),
        "pitch_deg": float(pitch),
        "yaw_deg": float(yaw),
        "heading_deg": float(heading),
    }


def _build_acceptance_snapshot(
    *,
    position_m: list[float],
    velocity_mps: list[float],
    quaternion_wxyz: list[float],
    step_index: int,
    sim_time_s: float,
) -> dict[str, Any]:
    speed_mps = _vector_norm(velocity_mps)
    quaternion_norm = _vector_norm(quaternion_wxyz)
    state_values = list(position_m) + list(velocity_mps) + list(quaternion_wxyz)
    return {
        "finite_state": all(math.isfinite(value) for value in state_values),
        "quaternion_norm_error": abs(quaternion_norm - 1.0),
        "kinetic_energy_like": 0.5 * speed_mps * speed_mps,
        "sim_time_s": float(sim_time_s),
        "step_index": int(step_index),
    }


def build_replay_record(
    runtime: EnvironmentRuntime,
    control: DynamicsControl | dict[str, Any],
    *,
    step_index: int,
    branch_id: str = "main",
    scenario_tags: list[str] | None = None,
    record_type: str = "runtime_step",
) -> dict[str, Any]:
    """Build a viewer-ready deterministic replay record."""
    control_payload = _coerce_control(control)
    position_m = [float(value) for value in runtime.ownship.position_m]
    velocity_mps = [float(value) for value in runtime.ownship.velocity_mps]
    quaternion_wxyz = [float(value) for value in runtime.ownship.quaternion_wxyz]
    angular_rate_rps = [float(value) for value in runtime.ownship.angular_rate_rps]
    speed_mps = _vector_norm(velocity_mps)
    quaternion_norm = _vector_norm(quaternion_wxyz)
    terrain_reference = [float(value) for value in runtime.environment.terrain_reference]
    terrain_mean_m = float(sum(terrain_reference) / max(1, len(terrain_reference)))
    terrain_max_m = float(max(terrain_reference) if terrain_reference else 0.0)
    wind_vector = [float(value) for value in runtime.atmosphere.wind_vector_mps]
    wind_speed_mps = _vector_norm(wind_vector)
    attitude = _quaternion_to_euler_deg(quaternion_wxyz)

    threats = [
        {
            "identifier": threat.identifier,
            "position_m": [float(value) for value in threat.position_m],
            "distance_m": float(_distance(position_m, [float(value) for value in threat.position_m])),
        }
        for threat in runtime.threats
    ]
    nearest_threat_distance_m = min(
        (threat["distance_m"] for threat in threats),
        default=float("inf"),
    )
    nearest_track_range_m = min(
        (float(value) for value in runtime.radar.detected_ranges_m),
        default=float("inf"),
    )

    return {
        "schema_version": "2.0",
        "record_type": record_type,
        "branch_id": branch_id,
        "step_index": int(step_index),
        "sim_time_s": float(runtime.environment.sim_time_s),
        "scenario_tags": list(scenario_tags or []),
        "ownship": {
            "position_m": position_m,
            "velocity_mps": velocity_mps,
            "quaternion_wxyz": quaternion_wxyz,
            "angular_rate_rps": angular_rate_rps,
            "speed_mps": float(speed_mps),
            "quaternion_norm": float(quaternion_norm),
            "altitude_m": float(position_m[2]),
            **attitude,
        },
        "control": control_payload,
        "threats": threats,
        "radar": {
            "track_ids": list(runtime.radar.track_ids),
            "detected_ranges_m": [float(value) for value in runtime.radar.detected_ranges_m],
            "track_count": int(len(runtime.radar.track_ids)),
            "nearest_track_range_m": float(nearest_track_range_m),
            "mode": runtime.radar.mode,
        },
        "sensor": {
            "contact_count": int(runtime.sensor.contact_count),
            "quality": float(runtime.sensor.quality),
            "detection_confidence": float(runtime.sensor.detection_confidence),
            "mode": runtime.sensor.mode,
        },
        "atmosphere": {
            "density_kgpm3": float(runtime.atmosphere.density_kgpm3),
            "wind_vector_mps": wind_vector,
            "wind_speed_mps": float(wind_speed_mps),
            "turbulence_level": float(runtime.atmosphere.turbulence_level),
        },
        "environment": {
            "terrain_reference": terrain_reference,
            "terrain_mean_m": terrain_mean_m,
            "terrain_max_m": terrain_max_m,
            "agent_count": int(runtime.mode_flags.get("agent_count", len(runtime.threats) + 1)),
        },
        "derived_metrics": {
            "terrain_mean_m": terrain_mean_m,
            "terrain_max_m": terrain_max_m,
            "altitude_agl_estimate_m": float(position_m[2] - terrain_mean_m),
            "nearest_threat_distance_m": float(nearest_threat_distance_m),
            "radar_track_count": int(len(runtime.radar.track_ids)),
            "speed_mps": float(speed_mps),
            "heading_deg": float(attitude["heading_deg"]),
            "kinetic_energy_like": 0.5 * speed_mps * speed_mps,
        },
        "acceptance_snapshot": _build_acceptance_snapshot(
            position_m=position_m,
            velocity_mps=velocity_mps,
            quaternion_wxyz=quaternion_wxyz,
            step_index=step_index,
            sim_time_s=runtime.environment.sim_time_s,
        ),
        "event_flags": {
            "mode_flags": dict(runtime.mode_flags),
            "rng_step_index": int(runtime.rng_state.get("step_index", 0)),
        },
    }


def build_runtime_log_entry(
    runtime: EnvironmentRuntime,
    control: DynamicsControl | dict[str, Any],
    *,
    step_index: int,
    branch_id: str = "main",
) -> dict[str, Any]:
    """Backward-compatible wrapper for the richer replay record."""
    return build_replay_record(runtime, control, step_index=step_index, branch_id=branch_id)


def _build_replay_record_from_branch_state(
    state: dict[str, Any],
    *,
    branch_id: str,
) -> dict[str, Any]:
    position_m = [float(value) for value in state.get("ownship_position_m", state.get("ownship", {}).get("position_m", [0.0, 0.0, 0.0]))]
    velocity_mps = [float(value) for value in state.get("ownship_velocity_mps", state.get("ownship", {}).get("velocity_mps", [0.0, 0.0, 0.0]))]
    quaternion_wxyz = [float(value) for value in state.get("ownship_quaternion_wxyz", state.get("ownship", {}).get("quaternion_wxyz", [1.0, 0.0, 0.0, 0.0]))]
    angular_rate_rps = [float(value) for value in state.get("ownship_angular_rate_rps", state.get("ownship", {}).get("angular_rate_rps", [0.0, 0.0, 0.0]))]
    terrain_reference = [float(value) for value in state.get("terrain_reference", state.get("environment", {}).get("terrain_reference", []))]
    terrain_mean_m = float(sum(terrain_reference) / max(1, len(terrain_reference))) if terrain_reference else float(state.get("derived_metrics", {}).get("terrain_mean_m", 0.0))
    terrain_max_m = float(max(terrain_reference) if terrain_reference else state.get("derived_metrics", {}).get("terrain_max_m", terrain_mean_m))
    threats_raw = state.get("threats")
    if threats_raw is None:
        threat_positions = state.get("threat_positions_m", [])
        threats_raw = [
            {
                "identifier": f"th-{index}",
                "position_m": [float(value) for value in position],
            }
            for index, position in enumerate(threat_positions)
        ]
    threats = []
    for threat in threats_raw:
        threat_position = [float(value) for value in threat.get("position_m", [0.0, 0.0, 0.0])]
        threats.append(
            {
                "identifier": threat.get("identifier", f"th-{len(threats)}"),
                "position_m": threat_position,
                "distance_m": float(_distance(position_m, threat_position)),
            }
        )

    control_payload = state.get("control", {})
    if "body_rate_cmd_rps" not in control_payload:
        control_payload = _coerce_control(control_payload)
    attitude = _quaternion_to_euler_deg(quaternion_wxyz)
    speed_mps = _vector_norm(velocity_mps)
    wind_vector = [float(value) for value in state.get("wind_vector_mps", state.get("atmosphere", {}).get("wind_vector_mps", [0.0, 0.0, 0.0]))]
    wind_speed_mps = _vector_norm(wind_vector)
    radar_track_ids = list(state.get("radar_tracks", state.get("radar", {}).get("track_ids", [])))
    radar_ranges = [float(value) for value in state.get("radar_detected_ranges_m", state.get("radar", {}).get("detected_ranges_m", []))]
    nearest_threat_distance_m = min((threat["distance_m"] for threat in threats), default=float("inf"))
    nearest_track_range_m = min(radar_ranges, default=float("inf"))

    return {
        "schema_version": "2.0",
        "record_type": "branch_replay_step",
        "branch_id": branch_id,
        "step_index": int(state.get("step", state.get("step_index", 0))),
        "sim_time_s": float(state.get("sim_time_s", 0.0)),
        "scenario_tags": list(state.get("scenario_tags", [])),
        "ownship": {
            "position_m": position_m,
            "velocity_mps": velocity_mps,
            "quaternion_wxyz": quaternion_wxyz,
            "angular_rate_rps": angular_rate_rps,
            "speed_mps": float(speed_mps),
            "quaternion_norm": float(_vector_norm(quaternion_wxyz)),
            "altitude_m": float(position_m[2]),
            **attitude,
        },
        "control": control_payload,
        "threats": threats,
        "radar": {
            "track_ids": radar_track_ids,
            "detected_ranges_m": radar_ranges,
            "track_count": int(len(radar_track_ids)),
            "nearest_track_range_m": float(nearest_track_range_m),
            "mode": state.get("radar_mode", "search"),
        },
        "sensor": {
            "contact_count": int(state.get("sensor_contact_count", state.get("sensor", {}).get("contact_count", 0))),
            "quality": float(state.get("sensor_quality", state.get("sensor", {}).get("quality", 0.0))),
            "detection_confidence": float(state.get("sensor_detection_confidence", state.get("sensor", {}).get("detection_confidence", 0.0))),
            "mode": state.get("sensor_mode", state.get("sensor", {}).get("mode", "nominal")),
        },
        "atmosphere": {
            "density_kgpm3": float(state.get("atmosphere_density_kgpm3", state.get("atmosphere", {}).get("density_kgpm3", 0.0))),
            "wind_vector_mps": wind_vector,
            "wind_speed_mps": float(wind_speed_mps),
            "turbulence_level": float(state.get("turbulence_level", state.get("atmosphere", {}).get("turbulence_level", 0.0))),
        },
        "environment": {
            "terrain_reference": terrain_reference,
            "terrain_mean_m": terrain_mean_m,
            "terrain_max_m": terrain_max_m,
            "agent_count": int(state.get("environment", {}).get("agent_count", len(threats) + 1)),
        },
        "derived_metrics": {
            "terrain_mean_m": terrain_mean_m,
            "terrain_max_m": terrain_max_m,
            "altitude_agl_estimate_m": float(position_m[2] - terrain_mean_m),
            "nearest_threat_distance_m": float(nearest_threat_distance_m),
            "radar_track_count": int(len(radar_track_ids)),
            "speed_mps": float(speed_mps),
            "heading_deg": float(attitude["heading_deg"]),
            "kinetic_energy_like": 0.5 * speed_mps * speed_mps,
        },
        "acceptance_snapshot": state.get(
            "acceptance_snapshot",
            _build_acceptance_snapshot(
                position_m=position_m,
                velocity_mps=velocity_mps,
                quaternion_wxyz=quaternion_wxyz,
                step_index=int(state.get("step", state.get("step_index", 0))),
                sim_time_s=float(state.get("sim_time_s", 0.0)),
            ),
        ),
        "event_flags": {
            "mode_flags": dict(state.get("mode_flags", {})),
            "rng_step_index": int(state.get("rng_step_index", 0)),
        },
    }


def flatten_branch_runtime_result(branch_runtime_result: BranchRuntimeResult) -> list[dict[str, Any]]:
    """Flatten branch rollout result into viewer-ready replay records."""
    rows: list[dict[str, Any]] = []
    for branch_index, trajectory in enumerate(branch_runtime_result.branch_trajectories):
        branch_id = f"branch_{branch_index}"
        for state in trajectory.states:
            rows.append(_build_replay_record_from_branch_state(state, branch_id=branch_id))
    return rows


def export_validation_log_jsonl(entries: Iterable[dict[str, Any]], output_path: str | Path) -> Path:
    """Export deterministic JSONL log entries."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return target


def export_validation_summary_csv(entries: Iterable[dict[str, Any]], output_path: str | Path) -> Path:
    """Export compact validation summary rows."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = list(entries)
    fieldnames = [
        "branch_id",
        "step_index",
        "sim_time_s",
        "speed_mps",
        "sensor_quality",
        "sensor_contact_count",
        "atmosphere_density_kgpm3",
        "turbulence_level",
        "wind_speed_mps",
        "heading_deg",
        "nearest_threat_distance_m",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            ownship = row.get("ownship", {})
            sensor = row.get("sensor", {})
            atmosphere = row.get("atmosphere", {})
            derived_metrics = row.get("derived_metrics", {})
            writer.writerow(
                {
                    "branch_id": row.get("branch_id", "main"),
                    "step_index": row.get("step_index", 0),
                    "sim_time_s": row.get("sim_time_s", 0.0),
                    "speed_mps": ownship.get("speed_mps", 0.0),
                    "sensor_quality": sensor.get("quality", row.get("sensor_quality", 0.0)),
                    "sensor_contact_count": sensor.get("contact_count", row.get("sensor_contact_count", 0)),
                    "atmosphere_density_kgpm3": atmosphere.get("density_kgpm3", row.get("atmosphere_density_kgpm3", 0.0)),
                    "turbulence_level": atmosphere.get("turbulence_level", row.get("turbulence_level", 0.0)),
                    "wind_speed_mps": atmosphere.get("wind_speed_mps", 0.0),
                    "heading_deg": ownship.get("heading_deg", derived_metrics.get("heading_deg", 0.0)),
                    "nearest_threat_distance_m": derived_metrics.get("nearest_threat_distance_m", 0.0),
                }
            )
    return target

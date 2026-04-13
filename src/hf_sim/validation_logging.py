"""Validation logging helpers for rollout analysis."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

from hf_sim.models import BranchRuntimeResult, DynamicsControl, EnvironmentRuntime


def build_runtime_log_entry(
    runtime: EnvironmentRuntime,
    control: DynamicsControl | dict[str, Any],
    *,
    step_index: int,
    branch_id: str = "main",
) -> dict[str, Any]:
    """Build a deterministic per-step validation log entry."""
    if isinstance(control, dict):
        throttle = float(control.get("throttle", 0.0))
        body_rate_cmd_rps = [
            float(control.get("roll", 0.0)),
            float(control.get("pitch", 0.0)),
            float(control.get("yaw", 0.0)),
        ]
        load_factor_cmd = float(control.get("load_factor", 1.0))
    else:
        throttle = float(control.throttle)
        body_rate_cmd_rps = [float(value) for value in control.body_rate_cmd_rps]
        load_factor_cmd = float(control.load_factor_cmd)

    speed_mps = math.sqrt(sum(component * component for component in runtime.ownship.velocity_mps))
    q_norm = math.sqrt(sum(component * component for component in runtime.ownship.quaternion_wxyz))
    wind_vector = list(runtime.atmosphere.wind_vector_mps)
    wind_mps = math.sqrt(sum(component * component for component in wind_vector))

    return {
        "branch_id": branch_id,
        "step_index": int(step_index),
        "sim_time_s": float(runtime.environment.sim_time_s),
        "ownship": {
            "position_m": [float(value) for value in runtime.ownship.position_m],
            "velocity_mps": [float(value) for value in runtime.ownship.velocity_mps],
            "quaternion_wxyz": [float(value) for value in runtime.ownship.quaternion_wxyz],
            "angular_rate_rps": [float(value) for value in runtime.ownship.angular_rate_rps],
            "speed_mps": float(speed_mps),
            "quaternion_norm": float(q_norm),
        },
        "sensor": {
            "contact_count": int(runtime.sensor.contact_count),
            "quality": float(runtime.sensor.quality),
            "detection_confidence": float(runtime.sensor.detection_confidence),
            "mode": runtime.sensor.mode,
        },
        "atmosphere": {
            "density_kgpm3": float(runtime.atmosphere.density_kgpm3),
            "wind_vector_mps": [float(value) for value in wind_vector],
            "wind_speed_mps": float(wind_mps),
            "turbulence_level": float(runtime.atmosphere.turbulence_level),
        },
        "control": {
            "throttle": throttle,
            "body_rate_cmd_rps": body_rate_cmd_rps,
            "load_factor_cmd": load_factor_cmd,
        },
        "derived_metrics": {
            "terrain_mean_m": float(sum(runtime.environment.terrain_reference) / max(1, len(runtime.environment.terrain_reference))),
            "radar_track_count": int(len(runtime.radar.track_ids)),
        },
        "event_flags": {
            "mode_flags": dict(runtime.mode_flags),
            "rng_step_index": int(runtime.rng_state.get("step_index", 0)),
        },
    }


def flatten_branch_runtime_result(branch_runtime_result: BranchRuntimeResult) -> list[dict[str, Any]]:
    """Flatten branch rollout result into branch-separated log entries."""
    rows: list[dict[str, Any]] = []
    for branch_index, trajectory in enumerate(branch_runtime_result.branch_trajectories):
        branch_id = f"branch_{branch_index}"
        for state in trajectory.states:
            rows.append(
                {
                    "branch_id": branch_id,
                    "step_index": int(state["step"]),
                    "sim_time_s": float(state.get("sim_time_s", 0.0)),
                    "ownship_position_m": list(state["ownship_position_m"]),
                    "ownship_velocity_mps": list(state["ownship_velocity_mps"]),
                    "sensor_contact_count": int(state.get("sensor_contact_count", 0)),
                    "sensor_quality": float(state.get("sensor_quality", 0.0)),
                    "atmosphere_density_kgpm3": float(state.get("atmosphere_density_kgpm3", 0.0)),
                    "turbulence_level": float(state.get("turbulence_level", 0.0)),
                    "wind_vector_mps": list(state.get("wind_vector_mps", [0.0, 0.0, 0.0])),
                    "radar_tracks": list(state.get("radar_tracks", [])),
                }
            )
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
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            ownship = row.get("ownship", {})
            sensor = row.get("sensor", {})
            atmosphere = row.get("atmosphere", {})
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
                }
            )
    return target

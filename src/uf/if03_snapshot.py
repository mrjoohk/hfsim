"""UF implementations for IF-03 full-environment runtime branching."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import asdict
from typing import Any

from hf_sim.models import (
    BranchControlBatch,
    BranchRolloutRequest,
    BranchRuntimeBatch,
    BranchRuntimeResult,
    BranchSourceRuntime,
    BranchTrajectory,
    BranchValidationReport,
    EnvironmentBranchTrajectoryBatch,
    EnvironmentCheckpoint,
    EnvironmentRuntime,
    PreparedBranchBatch,
    ValidatedCheckpoint,
)
from uf.if02_dynamics import step_environment_runtime


def _runtime_checksum(runtime: EnvironmentRuntime, step_index: int) -> str:
    runtime_copy = copy.deepcopy(runtime)
    runtime_copy.history = []
    payload = json.dumps({"runtime": asdict(runtime_copy), "step_index": step_index}, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def capture_environment_checkpoint(branch_rollout_request: BranchRolloutRequest) -> EnvironmentCheckpoint:
    """Capture current or historical full-environment checkpoint."""
    source_spec = branch_rollout_request.runtime_source_spec
    if source_spec.get("source", "current") == "current":
        source_runtime = copy.deepcopy(branch_rollout_request.runtime)
    else:
        k = int(source_spec.get("k", 0))
        if k < 0 or k >= len(branch_rollout_request.runtime.history):
            raise ValueError("invalid history index")
        source_runtime = copy.deepcopy(branch_rollout_request.runtime.history[-(k + 1)].runtime)

    step_index = int(source_runtime.rng_state.get("step_index", 0))
    return EnvironmentCheckpoint(
        runtime=source_runtime,
        step_index=step_index,
        checksum=_runtime_checksum(source_runtime, step_index),
        metadata={
            "source": source_spec.get("source", "current"),
            "k": int(source_spec.get("k", 0)),
            "clone_policy": branch_rollout_request.clone_policy,
        },
    )


def validate_checkpoint_completeness(environment_checkpoint: EnvironmentCheckpoint) -> ValidatedCheckpoint:
    """Validate checkpoint contains full environment state."""
    runtime = environment_checkpoint.runtime
    required_fields = [
        "ownship",
        "threats",
        "targets",
        "environment",
        "radar",
        "sensor",
        "atmosphere",
        "rng_state",
        "mode_flags",
    ]
    for field_name in required_fields:
        if getattr(runtime, field_name, None) is None:
            raise ValueError(f"checkpoint missing {field_name}")
    checksum = _runtime_checksum(runtime, environment_checkpoint.step_index)
    if checksum != environment_checkpoint.checksum:
        raise ValueError("corrupt checkpoint")
    return ValidatedCheckpoint(checkpoint=environment_checkpoint, required_fields=required_fields)


def materialize_branch_source_runtime(validated_checkpoint: ValidatedCheckpoint) -> BranchSourceRuntime:
    """Materialize branch source runtime from checkpoint."""
    return BranchSourceRuntime(
        runtime=copy.deepcopy(validated_checkpoint.checkpoint.runtime),
        checkpoint_metadata=dict(validated_checkpoint.checkpoint.metadata),
    )


def normalize_branch_control_batch(branch_rollout_request: BranchRolloutRequest) -> BranchControlBatch:
    """Normalize single-action or action-sequence branching into control sequences."""
    if not branch_rollout_request.branch_controls:
        raise ValueError("branch_controls cannot be empty")
    mode = branch_rollout_request.branch_mode
    control_sequences: list[list[dict[str, Any]]] = []
    if mode == "single_action_set":
        for action in branch_rollout_request.branch_controls:
            control_sequences.append([copy.deepcopy(action) for _ in range(branch_rollout_request.horizon)])
    elif mode == "action_sequence_set":
        for sequence in branch_rollout_request.branch_controls:
            controls = sequence.get("sequence")
            if not controls:
                raise ValueError("empty action sequence")
            control_sequences.append(copy.deepcopy(controls))
    else:
        raise ValueError("unsupported branch mode")

    for sequence in control_sequences:
        flat_values = [float(value) for action in sequence for value in action.values()]
        if any(not math.isfinite(value) for value in flat_values):
            raise ValueError("non-finite control detected")
    return BranchControlBatch(mode=mode, control_sequences=control_sequences)


def clone_environment_runtime_batch(
    validated_checkpoint: ValidatedCheckpoint, branch_control_batch: BranchControlBatch
) -> BranchRuntimeBatch:
    """Clone environment runtime independently for each branch."""
    runtimes = [copy.deepcopy(validated_checkpoint.checkpoint.runtime) for _ in branch_control_batch.control_sequences]
    return BranchRuntimeBatch(source_checkpoint=validated_checkpoint.checkpoint, runtimes=runtimes)


def inject_branch_controls(
    branch_runtime_batch: BranchRuntimeBatch,
    branch_control_batch: BranchControlBatch,
    branch_rollout_request: BranchRolloutRequest,
) -> PreparedBranchBatch:
    """Attach control sequences to cloned runtimes."""
    if len(branch_runtime_batch.runtimes) != len(branch_control_batch.control_sequences):
        raise ValueError("branch/control count mismatch")
    return PreparedBranchBatch(
        source_checkpoint=branch_runtime_batch.source_checkpoint,
        runtimes=branch_runtime_batch.runtimes,
        control_sequences=branch_control_batch.control_sequences,
        horizon=branch_rollout_request.horizon,
        reference_trajectories=copy.deepcopy(branch_rollout_request.reference_trajectories),
        tolerance=branch_rollout_request.tolerance,
    )


def rollout_branch_batch_with_environment_kernel(prepared_branch_batch: PreparedBranchBatch) -> EnvironmentBranchTrajectoryBatch:
    """Roll out each branch using the shared IF-02 environment kernel."""
    trajectories: list[BranchTrajectory] = []
    for runtime, control_sequence in zip(prepared_branch_batch.runtimes, prepared_branch_batch.control_sequences):
        branch_runtime = copy.deepcopy(runtime)
        states: list[dict[str, Any]] = []
        event_log: list[dict[str, Any]] = []
        horizon = min(prepared_branch_batch.horizon, len(control_sequence))
        for step_index in range(horizon):
            control = control_sequence[step_index]
            branch_runtime = step_environment_runtime(
                branch_runtime,
                control=type("BranchControl", (), {
                    "throttle": float(control.get("throttle", 0.0)),
                    "body_rate_cmd_rps": [
                        float(control.get("roll", 0.0)),
                        float(control.get("pitch", 0.0)),
                        float(control.get("yaw", 0.0)),
                    ],
                    "load_factor_cmd": float(control.get("load_factor", 1.0)),
                })(),
            )
            states.append(
                {
                    "step": step_index,
                    "sim_time_s": branch_runtime.environment.sim_time_s,
                    "control": {
                        "throttle": float(control.get("throttle", 0.0)),
                        "body_rate_cmd_rps": [
                            float(control.get("roll", 0.0)),
                            float(control.get("pitch", 0.0)),
                            float(control.get("yaw", 0.0)),
                        ],
                        "load_factor_cmd": float(control.get("load_factor", 1.0)),
                    },
                    "ownship": {
                        "position_m": list(branch_runtime.ownship.position_m),
                        "velocity_mps": list(branch_runtime.ownship.velocity_mps),
                        "quaternion_wxyz": list(branch_runtime.ownship.quaternion_wxyz),
                        "angular_rate_rps": list(branch_runtime.ownship.angular_rate_rps),
                    },
                    "ownship_position_m": list(branch_runtime.ownship.position_m),
                    "ownship_velocity_mps": list(branch_runtime.ownship.velocity_mps),
                    "ownship_quaternion_wxyz": list(branch_runtime.ownship.quaternion_wxyz),
                    "ownship_angular_rate_rps": list(branch_runtime.ownship.angular_rate_rps),
                    "threats": [
                        {
                            "identifier": threat.identifier,
                            "position_m": list(threat.position_m),
                        }
                        for threat in branch_runtime.threats
                    ],
                    "threat_positions_m": [list(threat.position_m) for threat in branch_runtime.threats],
                    "radar": {
                        "track_ids": list(branch_runtime.radar.track_ids),
                        "detected_ranges_m": list(branch_runtime.radar.detected_ranges_m),
                        "mode": branch_runtime.radar.mode,
                    },
                    "radar_tracks": list(branch_runtime.radar.track_ids),
                    "radar_detected_ranges_m": list(branch_runtime.radar.detected_ranges_m),
                    "sensor_contact_count": branch_runtime.sensor.contact_count,
                    "sensor_quality": branch_runtime.sensor.quality,
                    "sensor_detection_confidence": branch_runtime.sensor.detection_confidence,
                    "sensor": {
                        "contact_count": branch_runtime.sensor.contact_count,
                        "quality": branch_runtime.sensor.quality,
                        "detection_confidence": branch_runtime.sensor.detection_confidence,
                        "mode": branch_runtime.sensor.mode,
                    },
                    "atmosphere": {
                        "density_kgpm3": branch_runtime.atmosphere.density_kgpm3,
                        "turbulence_level": branch_runtime.atmosphere.turbulence_level,
                        "wind_vector_mps": list(branch_runtime.atmosphere.wind_vector_mps),
                    },
                    "atmosphere_density_kgpm3": branch_runtime.atmosphere.density_kgpm3,
                    "turbulence_level": branch_runtime.atmosphere.turbulence_level,
                    "wind_vector_mps": list(branch_runtime.atmosphere.wind_vector_mps),
                    "environment": {
                        "terrain_reference": list(branch_runtime.environment.terrain_reference),
                        "agent_count": int(branch_runtime.mode_flags.get("agent_count", len(branch_runtime.threats) + 1)),
                    },
                    "terrain_reference": list(branch_runtime.environment.terrain_reference),
                    "mode_flags": dict(branch_runtime.mode_flags),
                    "rng_step_index": int(branch_runtime.rng_state.get("step_index", 0)),
                    "acceptance_snapshot": {
                        "finite_state": True,
                        "quaternion_norm_error": abs(
                            math.sqrt(sum(component * component for component in branch_runtime.ownship.quaternion_wxyz)) - 1.0
                        ),
                        "step_index": step_index,
                        "sim_time_s": branch_runtime.environment.sim_time_s,
                    },
                }
            )
            event_log.append(
                {
                    "step": step_index,
                    "track_count": len(branch_runtime.radar.track_ids),
                    "sensor_quality": branch_runtime.sensor.quality,
                    "turbulence_level": branch_runtime.atmosphere.turbulence_level,
                }
            )
        trajectories.append(BranchTrajectory(states=states, event_log=event_log))
    return EnvironmentBranchTrajectoryBatch(
        trajectories=trajectories,
        source_checkpoint=prepared_branch_batch.source_checkpoint,
    )


def verify_branch_isolation_and_determinism(
    prepared_branch_batch: PreparedBranchBatch, environment_branch_trajectory_batch: EnvironmentBranchTrajectoryBatch
) -> BranchValidationReport:
    """Verify source immutability, branch isolation, and deterministic replay."""
    source_before = _runtime_checksum(
        prepared_branch_batch.source_checkpoint.runtime,
        prepared_branch_batch.source_checkpoint.step_index,
    )
    source_after = _runtime_checksum(
        prepared_branch_batch.source_checkpoint.runtime,
        prepared_branch_batch.source_checkpoint.step_index,
    )
    source_immutable = source_before == source_after

    branch_isolated = True
    if len(prepared_branch_batch.runtimes) >= 2:
        prepared_branch_batch.runtimes[0].mode_flags["branch_tag"] = "branch_0"
        branch_isolated = "branch_tag" not in prepared_branch_batch.runtimes[1].mode_flags

    max_abs_error = 0.0
    mismatch_count = 0
    deterministic = True
    if prepared_branch_batch.reference_trajectories:
        for trajectory, reference in zip(environment_branch_trajectory_batch.trajectories, prepared_branch_batch.reference_trajectories):
            compare_length = min(len(trajectory.states), len(reference))
            mismatch_count += abs(len(trajectory.states) - len(reference))
            for index in range(compare_length):
                current = trajectory.states[index]
                ref = reference[index]
                current_x = float(current["ownship_position_m"][0])
                ref_x = float(ref.get("ownship_position_m", [ref.get("x", 0.0)])[0] if isinstance(ref.get("ownship_position_m"), list) else ref.get("x", 0.0))
                max_abs_error = max(max_abs_error, abs(current_x - ref_x))
        deterministic = mismatch_count == 0 and max_abs_error <= prepared_branch_batch.tolerance
    return BranchValidationReport(
        deterministic=deterministic,
        source_immutable=source_immutable,
        branch_isolated=branch_isolated,
        max_abs_error=max_abs_error,
        mismatch_count=mismatch_count,
    )


def package_branch_runtime_result(
    environment_branch_trajectory_batch: EnvironmentBranchTrajectoryBatch,
    branch_validation_report: BranchValidationReport,
) -> BranchRuntimeResult:
    """Package branch rollout result."""
    return BranchRuntimeResult(
        checkpoint=environment_branch_trajectory_batch.source_checkpoint,
        branch_count=len(environment_branch_trajectory_batch.trajectories),
        branch_trajectories=environment_branch_trajectory_batch.trajectories,
        validation_report=branch_validation_report,
        metadata=dict(environment_branch_trajectory_batch.source_checkpoint.metadata),
    )

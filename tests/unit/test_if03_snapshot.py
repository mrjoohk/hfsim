import pytest

from hf_sim.models import (
    AtmosphereState,
    BranchRolloutRequest,
    DynamicsControl,
    EnvironmentCheckpoint,
    EnvironmentRuntime,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
    TargetState,
    ThreatState,
)
from uf.if02_dynamics import step_environment_runtime
from uf.if03_snapshot import (
    capture_environment_checkpoint,
    clone_environment_runtime_batch,
    inject_branch_controls,
    materialize_branch_source_runtime,
    normalize_branch_control_batch,
    package_branch_runtime_result,
    rollout_branch_batch_with_environment_kernel,
    validate_checkpoint_completeness,
    verify_branch_isolation_and_determinism,
)


def _runtime():
    runtime = EnvironmentRuntime(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, 1000.0],
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.01, "max_thrust_n": 30000.0, "lift_gain": 8.0},
        ),
        threats=[ThreatState(identifier="th-1", position_m=[2000.0, 100.0, 1000.0], velocity_mps=[10.0, 0.0, 0.0])],
        targets=[TargetState(identifier="tg-1", position_m=[5000.0, 0.0, 0.0], velocity_mps=[0.0, 0.0, 0.0])],
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 110.0, 120.0], flags={}),
        radar=RadarState(track_ids=[], detected_ranges_m=[]),
        sensor=SensorState(contact_count=0, quality=1.0),
        atmosphere=AtmosphereState(density_kgpm3=1.225, wind_vector_mps=[0.0, 0.0, 0.0], turbulence_level=0.1),
        rng_state={"seed": 1, "step_index": 0},
        mode_flags={"agent_count": 4},
        dt_internal=0.01,
        calibration_config={"velocity_scale": 1.0},
    )
    history_runtime = runtime
    for _ in range(2):
        history_checkpoint = EnvironmentCheckpoint(
            runtime=history_runtime,
            step_index=int(history_runtime.rng_state.get("step_index", 0)),
            checksum="placeholder",
            metadata={"source": "history"},
        )
        history_runtime.history.append(history_checkpoint)
        history_runtime = step_environment_runtime(
            history_runtime,
            DynamicsControl(throttle=0.5, body_rate_cmd_rps=[0.0, 0.0, 0.0], load_factor_cmd=1.0),
        )
    return history_runtime


def test_if03_uf_chain_supports_branching_and_isolation():
    runtime = _runtime()
    request = BranchRolloutRequest(
        runtime=runtime,
        runtime_source_spec={"source": "current", "k": 0},
        branch_mode="single_action_set",
        branch_controls=[
            {"throttle": 0.8, "roll": 0.1, "pitch": 0.0},
            {"throttle": 0.2, "roll": -0.1, "pitch": 0.0},
        ],
        horizon=3,
    )
    checkpoint = capture_environment_checkpoint(request)
    validated = validate_checkpoint_completeness(checkpoint)
    source_runtime = materialize_branch_source_runtime(validated)
    control_batch = normalize_branch_control_batch(request)
    runtime_batch = clone_environment_runtime_batch(validated, control_batch)
    prepared = inject_branch_controls(runtime_batch, control_batch, request)
    trajectories = rollout_branch_batch_with_environment_kernel(prepared)
    validation = verify_branch_isolation_and_determinism(prepared, trajectories)
    result = package_branch_runtime_result(trajectories, validation)
    assert source_runtime.runtime.environment.sim_time_s == checkpoint.runtime.environment.sim_time_s
    assert result.branch_count == 2
    assert result.validation_report.branch_isolated
    assert result.branch_trajectories[0].states[-1]["ownship_position_m"] != result.branch_trajectories[1].states[-1]["ownship_position_m"]


def test_if03_history_runtime_checkpoint_is_supported():
    runtime = _runtime()
    request = BranchRolloutRequest(
        runtime=runtime,
        runtime_source_spec={"source": "history", "k": 0},
        branch_mode="action_sequence_set",
        branch_controls=[{"sequence": [{"throttle": 0.4, "roll": 0.0, "pitch": 0.0}, {"throttle": 0.6, "roll": 0.0, "pitch": 0.1}]}],
        horizon=2,
    )
    checkpoint = capture_environment_checkpoint(request)
    validated = validate_checkpoint_completeness(checkpoint)
    assert validated.checkpoint.metadata["source"] == "history"


def test_normalize_branch_control_batch_empty_raises():
    runtime = _runtime()
    with pytest.raises(ValueError):
        normalize_branch_control_batch(
            BranchRolloutRequest(
                runtime=runtime,
                runtime_source_spec={"source": "current", "k": 0},
                branch_mode="single_action_set",
                branch_controls=[],
                horizon=1,
            )
        )

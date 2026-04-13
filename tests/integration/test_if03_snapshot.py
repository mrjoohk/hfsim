import importlib
import json
from pathlib import Path

from hf_sim.models import (
    AtmosphereState,
    BranchRolloutRequest,
    EnvironmentCheckpoint,
    EnvironmentRuntime,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
    TargetState,
    ThreatState,
)
from hf_sim.validation_logging import export_validation_log_jsonl, flatten_branch_runtime_result


def test_if03_snapshot_acceptance():
    module = importlib.import_module("if.if03_snapshot")
    runtime = EnvironmentRuntime(
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
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 110.0], flags={}),
        radar=RadarState(track_ids=[], detected_ranges_m=[]),
        sensor=SensorState(contact_count=0, quality=1.0),
        atmosphere=AtmosphereState(density_kgpm3=1.225, wind_vector_mps=[0.0, 0.0, 0.0], turbulence_level=0.1),
        rng_state={"seed": 1, "step_index": 0},
        mode_flags={"agent_count": 4},
        dt_internal=0.01,
        calibration_config={"velocity_scale": 1.0},
    )
    runtime.history.append(EnvironmentCheckpoint(runtime=runtime, step_index=0, checksum="placeholder", metadata={"source": "history"}))
    result = module.if_03_branch_snapshot_rollout(
        BranchRolloutRequest(
            runtime=runtime,
            runtime_source_spec={"source": "current", "k": 0},
            branch_mode="single_action_set",
            branch_controls=[
                {"throttle": 0.8, "roll": 0.1, "pitch": 0.0},
                {"throttle": 0.2, "roll": -0.1, "pitch": 0.0},
            ],
            horizon=2,
        )
    )
    assert result.validation_report.source_immutable
    assert result.validation_report.branch_isolated
    assert result.branch_count == 2


def test_if03_branch_logging_acceptance():
    module = importlib.import_module("if.if03_snapshot")
    runtime = EnvironmentRuntime(
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
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0, 110.0], flags={}),
        radar=RadarState(track_ids=[], detected_ranges_m=[]),
        sensor=SensorState(contact_count=0, quality=1.0),
        atmosphere=AtmosphereState(density_kgpm3=1.1, wind_vector_mps=[5.0, 0.0, 0.0], turbulence_level=0.2),
        rng_state={"seed": 1, "step_index": 0},
        mode_flags={"agent_count": 4},
        dt_internal=0.01,
        calibration_config={"velocity_scale": 1.0},
    )
    result = module.if_03_branch_snapshot_rollout(
        BranchRolloutRequest(
            runtime=runtime,
            runtime_source_spec={"source": "current", "k": 0},
            branch_mode="single_action_set",
            branch_controls=[
                {"throttle": 0.8, "roll": 0.1, "pitch": 0.0},
                {"throttle": 0.2, "roll": -0.1, "pitch": 0.0},
            ],
            horizon=2,
        )
    )
    rows = flatten_branch_runtime_result(result)
    path = Path.cwd() / "test_if03_branch_logging.jsonl"
    try:
        path = export_validation_log_jsonl(rows, path)
        payload = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert {row["branch_id"] for row in payload} == {"branch_0", "branch_1"}
        assert all("sensor_quality" in row for row in payload)
    finally:
        path.unlink(missing_ok=True)

import json
from pathlib import Path

from hf_sim.models import (
    AtmosphereState,
    BranchRuntimeResult,
    BranchTrajectory,
    BranchValidationReport,
    DynamicsControl,
    EnvironmentCheckpoint,
    EnvironmentRuntime,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
    ThreatState,
)
from hf_sim.validation_logging import (
    build_replay_record,
    build_runtime_log_entry,
    export_validation_log_jsonl,
    export_validation_summary_csv,
    flatten_branch_runtime_result,
)


def _runtime():
    return EnvironmentRuntime(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, 1000.0],
            velocity_mps=[200.0, 1.0, -2.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.1, 0.0, 0.05],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.01, "max_thrust_n": 30000.0, "lift_gain": 8.0},
        ),
        threats=[ThreatState(identifier="th-1", position_m=[1000.0, 500.0, 1000.0], velocity_mps=[0.0, 0.0, 0.0])],
        targets=[],
        environment=EnvironmentState(sim_time_s=1.5, terrain_reference=[100.0, 110.0, 120.0], flags={}),
        radar=RadarState(track_ids=["th-1"], detected_ranges_m=[1200.0]),
        sensor=SensorState(contact_count=1, quality=0.85, detection_confidence=0.6),
        atmosphere=AtmosphereState(density_kgpm3=1.1, wind_vector_mps=[4.0, 0.0, 0.0], turbulence_level=0.2),
        rng_state={"step_index": 3},
        mode_flags={"agent_count": 1},
        dt_internal=0.01,
        calibration_config={},
    )


def test_build_replay_record_contains_viewer_sections():
    entry = build_replay_record(
        _runtime(),
        DynamicsControl(throttle=0.5, body_rate_cmd_rps=[0.1, 0.0, 0.0], load_factor_cmd=1.0),
        step_index=3,
        branch_id="branch_0",
        scenario_tags=["acceptance", "ownship"],
    )
    assert entry["schema_version"] == "2.0"
    assert entry["control"]["throttle"] == 0.5
    assert entry["ownship"]["speed_mps"] > 0.0
    assert entry["ownship"]["heading_deg"] >= 0.0
    assert entry["radar"]["track_count"] == 1
    assert entry["threats"][0]["distance_m"] > 0.0
    assert entry["acceptance_snapshot"]["finite_state"] is True
    assert entry["event_flags"]["rng_step_index"] == 3


def test_build_runtime_log_entry_is_backward_compatible_wrapper():
    entry = build_runtime_log_entry(
        _runtime(),
        {"throttle": 0.5, "roll": 0.1, "pitch": 0.0},
        step_index=3,
        branch_id="branch_0",
    )
    assert entry["branch_id"] == "branch_0"
    assert entry["sensor"]["quality"] == 0.85
    assert entry["atmosphere"]["wind_speed_mps"] > 0.0


def test_export_validation_logs_are_deterministic():
    entry = build_runtime_log_entry(
        _runtime(),
        {"throttle": 0.5, "roll": 0.1, "pitch": 0.0},
        step_index=3,
        branch_id="branch_0",
    )
    jsonl_path = Path.cwd() / "test_validation_logging.jsonl"
    csv_path = Path.cwd() / "test_validation_logging.csv"
    try:
        jsonl_path = export_validation_log_jsonl([entry], jsonl_path)
        csv_path = export_validation_summary_csv([entry], csv_path)

        payload = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(payload) == 1
        assert json.loads(payload[0])["branch_id"] == "branch_0"
        csv_text = csv_path.read_text(encoding="utf-8")
        assert "sensor_quality" in csv_text
        assert "nearest_threat_distance_m" in csv_text
    finally:
        jsonl_path.unlink(missing_ok=True)
        csv_path.unlink(missing_ok=True)


def test_flatten_branch_runtime_result_emits_standard_records():
    result = BranchRuntimeResult(
        checkpoint=EnvironmentCheckpoint(runtime=_runtime(), step_index=0, checksum="x", metadata={}),
        branch_count=2,
        branch_trajectories=[
            BranchTrajectory(
                states=[{
                    "step": 0,
                    "sim_time_s": 0.01,
                    "control": {"throttle": 0.6, "body_rate_cmd_rps": [0.0, 0.0, 0.0], "load_factor_cmd": 1.0},
                    "ownship_position_m": [0.0, 0.0, 1000.0],
                    "ownship_velocity_mps": [1.0, 0.0, 0.0],
                    "ownship_quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                    "ownship_angular_rate_rps": [0.0, 0.0, 0.0],
                    "threat_positions_m": [[10.0, 0.0, 1000.0]],
                    "sensor_contact_count": 1,
                    "sensor_quality": 0.7,
                    "atmosphere_density_kgpm3": 1.1,
                    "turbulence_level": 0.2,
                    "wind_vector_mps": [1.0, 0.0, 0.0],
                    "radar_tracks": ["th-1"],
                    "radar_detected_ranges_m": [10.0],
                    "terrain_reference": [100.0, 120.0],
                }],
                event_log=[],
            ),
            BranchTrajectory(
                states=[{
                    "step": 0,
                    "sim_time_s": 0.01,
                    "control": {"throttle": 0.3, "body_rate_cmd_rps": [0.0, 0.1, 0.0], "load_factor_cmd": 1.0},
                    "ownship_position_m": [1.0, 0.0, 1000.0],
                    "ownship_velocity_mps": [2.0, 0.0, 0.0],
                    "ownship_quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                    "ownship_angular_rate_rps": [0.0, 0.1, 0.0],
                    "sensor_contact_count": 0,
                    "sensor_quality": 0.6,
                    "atmosphere_density_kgpm3": 1.0,
                    "turbulence_level": 0.3,
                    "wind_vector_mps": [0.0, 1.0, 0.0],
                    "radar_tracks": [],
                    "terrain_reference": [100.0, 120.0],
                }],
                event_log=[],
            ),
        ],
        validation_report=BranchValidationReport(
            deterministic=True,
            source_immutable=True,
            branch_isolated=True,
            max_abs_error=0.0,
            mismatch_count=0,
        ),
        metadata={},
    )
    rows = flatten_branch_runtime_result(result)
    assert rows[0]["branch_id"] == "branch_0"
    assert rows[1]["branch_id"] == "branch_1"
    assert rows[0]["radar"]["track_count"] == 1
    assert rows[0]["derived_metrics"]["nearest_threat_distance_m"] > 0.0

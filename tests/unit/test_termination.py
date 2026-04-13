"""Unit tests for hf_sim.termination."""

from __future__ import annotations

import math

import pytest

from hf_sim.models import (
    AtmosphereState,
    EnvironmentRuntime,
    EnvironmentState,
    ExecutionBundle,
    OwnshipState,
    RadarState,
    RolloutPlan,
    ScenarioInstance,
    SensorState,
    TargetState,
    ThreatState,
)
from hf_sim.termination import TerminationResult, check_termination


def _make_runtime(
    position_m=None,
    threat_positions=None,
    target_positions=None,
    terrain=None,
) -> EnvironmentRuntime:
    position_m = position_m or [0.0, 0.0, 1000.0]
    terrain = terrain or [100.0] * 4

    threats = [
        ThreatState(identifier=f"th-{i}", position_m=list(p), velocity_mps=[0.0, 0.0, 0.0])
        for i, p in enumerate(threat_positions or [[5000.0, 0.0, 1000.0]])
    ]
    targets = [
        TargetState(identifier=f"tg-{i}", position_m=list(p), velocity_mps=[0.0, 0.0, 0.0])
        for i, p in enumerate(target_positions or [[5000.0, 0.0, 0.0]])
    ]
    return EnvironmentRuntime(
        ownship=OwnshipState(
            position_m=list(position_m),
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.02, "max_thrust_n": 20000.0, "lift_gain": 9.0},
        ),
        threats=threats,
        targets=targets,
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=list(terrain), flags={}),
        radar=RadarState(),
        sensor=SensorState(),
        atmosphere=AtmosphereState(),
        rng_state={"seed": 0, "step_index": 0},
        mode_flags={},
        history=[],
    )


def _make_bundle() -> ExecutionBundle:
    sc = ScenarioInstance(
        scenario_id="test", run_id="r0", seed=0, curriculum_level=0,
        agent_count=1, rare_cases_enabled=False, difficulty=0.2,
        ownship_spawn=[[0.0, 0.0, 1000.0]],
        threat_spawn=[[5000.0, 0.0, 1000.0]],
        target_spawn=[[5000.0, 0.0, 0.0]],
        terrain_heights=[100.0] * 16,
    )
    rp = RolloutPlan(
        parallel_rollouts=1, estimated_env_step_per_sec=1000.0,
        estimated_time_acceleration=60.0, device="cpu",
        per_rollout_memory_bytes=1, batch_memory_bytes=1, benchmark_mode="baseline",
    )
    return ExecutionBundle(
        scenario_instance=sc, rollout_plan=rp,
        deterministic_seed=0, benchmark_mode="baseline",
        agent_count=1, reproducibility_manifest={}, checksum="abc",
    )


_BUNDLE = _make_bundle()


def test_nonfinite_terminates():
    rt = _make_runtime()
    result = check_termination(rt, _BUNDLE, 0, 1000, {"nonfinite": True})
    assert result.terminated is True
    assert result.truncated is False
    assert result.reason == "nonfinite"


def test_nan_position_terminates():
    rt = _make_runtime(position_m=[float("nan"), 0.0, 1000.0])
    result = check_termination(rt, _BUNDLE, 0, 1000, {"nonfinite": False})
    assert result.terminated is True
    assert result.reason == "nonfinite"


def test_ground_collision_terminates():
    # terrain max = 100.0, floor = 100.0 - 50.0 = 50.0
    rt = _make_runtime(position_m=[0.0, 0.0, 30.0], terrain=[100.0] * 4)
    result = check_termination(rt, _BUNDLE, 0, 1000, {"nonfinite": False})
    assert result.terminated is True
    assert result.reason == "ground"


def test_threat_kill_terminates():
    # put threat within 300 m
    rt = _make_runtime(threat_positions=[[100.0, 0.0, 1000.0]])
    result = check_termination(rt, _BUNDLE, 0, 1000, {"nonfinite": False})
    assert result.terminated is True
    assert result.reason == "threat_kill"


def test_success_terminates():
    # ownship within 200 m of target, both at safe altitude (z=200 > floor=50)
    rt = _make_runtime(position_m=[5050.0, 0.0, 200.0], target_positions=[[5000.0, 0.0, 200.0]])
    result = check_termination(rt, _BUNDLE, 0, 1000, {"nonfinite": False})
    assert result.terminated is True
    assert result.reason == "success"


def test_max_steps_truncates_not_terminates():
    rt = _make_runtime()
    result = check_termination(rt, _BUNDLE, 1000, 1000, {"nonfinite": False})
    assert result.terminated is False
    assert result.truncated is True
    assert result.reason == "max_steps"


def test_normal_step_no_termination():
    rt = _make_runtime()
    result = check_termination(rt, _BUNDLE, 0, 1000, {"nonfinite": False})
    assert result.terminated is False
    assert result.truncated is False
    assert result.reason == "none"


def test_priority_nonfinite_before_ground():
    """nonfinite must be checked before ground collision."""
    rt = _make_runtime(position_m=[0.0, 0.0, 10.0])  # would be ground
    result = check_termination(rt, _BUNDLE, 0, 1000, {"nonfinite": True})
    assert result.reason == "nonfinite"  # not "ground"

"""Unit tests for hf_sim.reward."""

from __future__ import annotations

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
from hf_sim.reward import compute_reward


def _runtime(pos_z=1000.0, threat_dist=5000.0, target_dist=4000.0) -> EnvironmentRuntime:
    return EnvironmentRuntime(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, pos_z],
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.02, "max_thrust_n": 20000.0, "lift_gain": 9.0},
        ),
        threats=[ThreatState("th-0", [threat_dist, 0.0, 1000.0], [0.0, 0.0, 0.0])],
        targets=[TargetState("tg-0", [target_dist, 0.0, 0.0], [0.0, 0.0, 0.0])],
        environment=EnvironmentState(0.0, [100.0] * 4, {}),
        radar=RadarState(), sensor=SensorState(), atmosphere=AtmosphereState(),
        rng_state={}, mode_flags={}, history=[],
    )


def _bundle() -> ExecutionBundle:
    sc = ScenarioInstance(
        scenario_id="t", run_id="r", seed=0, curriculum_level=0,
        agent_count=1, rare_cases_enabled=False, difficulty=0.2,
        ownship_spawn=[[0.0, 0.0, 1000.0]], threat_spawn=[[5000.0, 0.0, 1000.0]],
        target_spawn=[[4000.0, 0.0, 0.0]], terrain_heights=[100.0] * 16,
    )
    rp = RolloutPlan(1, 1000.0, 60.0, "cpu", 1, 1, "baseline")
    return ExecutionBundle(sc, rp, 0, "baseline", 1, {}, "abc")


_B = _bundle()


def test_reward_components_sum_to_total():
    rt = _runtime()
    total, comps = compute_reward(rt, _B, False, False, "none", 5000.0)
    assert abs(total - sum(comps.values())) < 1e-6


def test_survival_bonus_present_when_alive():
    rt = _runtime()
    _, comps = compute_reward(rt, _B, False, False, "none", 5000.0)
    assert comps["survival"] == pytest.approx(0.02)


def test_survival_zero_on_crash():
    rt = _runtime()
    _, comps = compute_reward(rt, _B, True, False, "threat_kill", 5000.0)
    assert comps["survival"] == 0.0
    assert comps["terminal"] == pytest.approx(-10.0)


def test_success_gives_positive_terminal():
    rt = _runtime()
    _, comps = compute_reward(rt, _B, True, False, "success", 5000.0)
    assert comps["terminal"] == pytest.approx(10.0)
    assert comps["survival"] == 0.0


def test_target_approach_increases_reward():
    """Moving closer to target should give positive target_shaping."""
    rt = _runtime(target_dist=3800.0)
    _, comps = compute_reward(rt, _B, False, False, "none", prev_target_dist=4000.0)
    assert comps["target_shaping"] > 0.0


def test_target_retreat_gives_negative_shaping():
    rt = _runtime(target_dist=4200.0)
    _, comps = compute_reward(rt, _B, False, False, "none", prev_target_dist=4000.0)
    assert comps["target_shaping"] < 0.0


def test_reward_bounded():
    """Total reward must be in [-10.1, +10.3] for any reasonable input."""
    for terminated, reason in [
        (False, "none"),
        (True, "threat_kill"),
        (True, "success"),
    ]:
        rt = _runtime()
        total, _ = compute_reward(rt, _B, terminated, False, reason, 5000.0)
        assert -10.1 < total < 10.3, f"Reward {total} out of bounds"


def test_altitude_shaping_zero_below_floor():
    rt = _runtime(pos_z=150.0)  # AGL ≈ 50 m < floor 100 m
    _, comps = compute_reward(rt, _B, False, False, "none", 5000.0)
    assert comps["altitude_shaping"] == pytest.approx(0.0)


def test_altitude_shaping_positive_above_floor():
    rt = _runtime(pos_z=700.0)  # AGL ≈ 600 m > floor 100 m
    _, comps = compute_reward(rt, _B, False, False, "none", 5000.0)
    assert comps["altitude_shaping"] > 0.0

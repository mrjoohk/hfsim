"""Unit tests for hf_sim.domain_rand."""

from __future__ import annotations

import numpy as np
import pytest

from hf_sim.domain_rand import DomainRandConfig, apply_domain_rand, apply_spawn_jitter
from hf_sim.models import (
    ExecutionBundle,
    RolloutPlan,
    ScenarioInstance,
)


def _bundle(curriculum_level: int = 5) -> ExecutionBundle:
    sc = ScenarioInstance(
        scenario_id="t", run_id="r", seed=0,
        curriculum_level=curriculum_level,
        agent_count=1, rare_cases_enabled=False, difficulty=0.5,
        ownship_spawn=[[0.0, 0.0, 1000.0]],
        threat_spawn=[[2500.0, 0.0, 900.0]],
        target_spawn=[[5000.0, 0.0, 0.0]],
        terrain_heights=[100.0] * 16,
    )
    rp = RolloutPlan(1, 1000.0, 60.0, "cpu", 1, 1, "baseline")
    return ExecutionBundle(sc, rp, 0, "baseline", 1, {}, "abc")


def test_zero_config_returns_nominal():
    bundle = _bundle(curriculum_level=10)
    config = DomainRandConfig()
    rng = np.random.default_rng(0)
    aero, atmo = apply_domain_rand(bundle, config, rng)
    assert aero["drag_coeff"] == pytest.approx(0.02)
    assert aero["max_thrust_n"] == pytest.approx(20000.0)
    assert aero["lift_gain"] == pytest.approx(9.0)
    assert atmo.density_kgpm3 == pytest.approx(1.225)
    assert atmo.wind_vector_mps == [0.0, 0.0, 0.0]
    assert atmo.turbulence_level == pytest.approx(0.0)


def test_aero_keys_present():
    bundle = _bundle()
    config = DomainRandConfig(drag_coeff_rand_frac=0.1)
    rng = np.random.default_rng(1)
    aero, _ = apply_domain_rand(bundle, config, rng)
    assert "drag_coeff" in aero
    assert "max_thrust_n" in aero
    assert "lift_gain" in aero


def test_density_within_physics_clamp():
    bundle = _bundle(curriculum_level=10)
    config = DomainRandConfig(density_rand_frac=0.5)
    rng = np.random.default_rng(99)
    for _ in range(20):
        _, atmo = apply_domain_rand(bundle, config, rng)
        assert 0.7 <= atmo.density_kgpm3 <= 1.5


def test_curriculum_level_zero_no_variation():
    """At curriculum_level=0, randomization scale = 0 → nominal values."""
    bundle = _bundle(curriculum_level=0)
    config = DomainRandConfig(
        drag_coeff_rand_frac=0.5,
        max_thrust_rand_frac=0.5,
        density_rand_frac=0.5,
        wind_max_mps=20.0,
        turbulence_max=1.0,
    )
    rng = np.random.default_rng(0)
    for _ in range(10):
        aero, atmo = apply_domain_rand(bundle, config, rng)
        assert aero["drag_coeff"] == pytest.approx(0.02)
        assert atmo.density_kgpm3 == pytest.approx(1.225)
        assert atmo.wind_vector_mps == [0.0, 0.0, 0.0]


def test_curriculum_scaling_produces_more_variation():
    """Higher curriculum_level should produce more variation on average."""
    config = DomainRandConfig(drag_coeff_rand_frac=0.3)
    rng_low = np.random.default_rng(42)
    rng_high = np.random.default_rng(42)

    low_bundle = _bundle(curriculum_level=2)
    high_bundle = _bundle(curriculum_level=9)

    deviations_low = []
    deviations_high = []
    for _ in range(30):
        a_low, _ = apply_domain_rand(low_bundle, config, rng_low)
        a_high, _ = apply_domain_rand(high_bundle, config, rng_high)
        deviations_low.append(abs(a_low["drag_coeff"] - 0.02))
        deviations_high.append(abs(a_high["drag_coeff"] - 0.02))

    assert sum(deviations_high) > sum(deviations_low)


def test_spawn_jitter_zero_unchanged():
    config = DomainRandConfig(spawn_jitter_m=0.0)
    rng = np.random.default_rng(0)
    spawn = [100.0, 200.0, 1000.0]
    result = apply_spawn_jitter(spawn, config, rng, curriculum_level=5)
    assert result == spawn


def test_spawn_jitter_changes_position():
    config = DomainRandConfig(spawn_jitter_m=200.0)
    rng = np.random.default_rng(5)
    spawn = [100.0, 200.0, 1000.0]
    result = apply_spawn_jitter(spawn, config, rng, curriculum_level=10)
    assert result != spawn


def test_negative_rand_frac_raises():
    with pytest.raises(ValueError):
        DomainRandConfig(drag_coeff_rand_frac=-0.1)

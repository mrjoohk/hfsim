"""Unit tests for hf_sim.noise."""

from __future__ import annotations

import numpy as np
import pytest

from hf_sim.models import (
    AtmosphereState,
    EnvironmentRuntime,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
    ThreatState,
    TargetState,
)
from hf_sim.noise import NoiseConfig, apply_obs_noise, apply_process_noise


def _runtime() -> EnvironmentRuntime:
    return EnvironmentRuntime(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, 1000.0],
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.02, "max_thrust_n": 20000.0, "lift_gain": 9.0},
        ),
        threats=[],
        targets=[],
        environment=EnvironmentState(0.0, [100.0] * 4, {}),
        radar=RadarState(), sensor=SensorState(), atmosphere=AtmosphereState(),
        rng_state={}, mode_flags={}, history=[],
    )


def test_zero_noise_config_is_identity():
    rt = _runtime()
    rng = np.random.default_rng(0)
    config = NoiseConfig(process_noise_scale=0.0)
    result = apply_process_noise(rt, config, rng)
    assert result is rt  # same object returned when scale=0


def test_process_noise_changes_velocity():
    rt = _runtime()
    rng = np.random.default_rng(42)
    config = NoiseConfig(process_noise_scale=1.0)
    noisy = apply_process_noise(rt, config, rng)
    assert noisy is not rt
    assert noisy.ownship.velocity_mps != rt.ownship.velocity_mps


def test_process_noise_history_stays_empty():
    rt = _runtime()
    rng = np.random.default_rng(0)
    config = NoiseConfig(process_noise_scale=0.5)
    noisy = apply_process_noise(rt, config, rng)
    assert noisy.history == []


def test_obs_noise_changes_obs():
    obs = np.zeros(16, dtype=np.float32)
    rng = np.random.default_rng(7)
    config = NoiseConfig(obs_noise_scale=0.1)
    noisy = apply_obs_noise(obs, config, rng)
    assert not np.array_equal(noisy, obs)


def test_obs_noise_clipped_to_bounds():
    obs = np.ones(16, dtype=np.float32)  # all at max
    rng = np.random.default_rng(0)
    config = NoiseConfig(obs_noise_scale=2.0)
    noisy = apply_obs_noise(obs, config, rng)
    assert np.all(noisy >= -1.0) and np.all(noisy <= 1.0)


def test_obs_zero_noise_is_identity():
    obs = np.linspace(-1, 1, 16, dtype=np.float32)
    rng = np.random.default_rng(0)
    config = NoiseConfig(obs_noise_scale=0.0)
    result = apply_obs_noise(obs, config, rng)
    assert result is obs  # no-op returns original


def test_process_noise_scale_too_large_raises():
    with pytest.raises(ValueError, match="process_noise_scale"):
        NoiseConfig(process_noise_scale=6.0)


def test_negative_scale_raises():
    with pytest.raises(ValueError):
        NoiseConfig(process_noise_scale=-0.1)

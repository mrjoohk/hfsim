"""Unit tests for hf_sim.env (HFSimEnv)."""

from __future__ import annotations

import numpy as np
import pytest

from hf_sim.env import HFSimEnv


def test_reset_returns_correct_obs_shape():
    env = HFSimEnv(seed=0)
    obs, info = env.reset()
    assert obs.shape == (16,)
    assert obs.dtype == np.float32


def test_obs_within_bounds_after_reset():
    env = HFSimEnv(seed=1)
    obs, _ = env.reset()
    assert np.all(obs >= -1.0) and np.all(obs <= 1.0)


def test_step_returns_correct_types():
    env = HFSimEnv(seed=0)
    env.reset()
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    assert obs.shape == (16,)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)


def test_step_deterministic_with_same_seed():
    """Identical seeds must produce identical obs trajectories."""
    env_a = HFSimEnv(seed=42)
    env_b = HFSimEnv(seed=42)
    np.random.seed(0)  # fix action sampling
    rng = np.random.default_rng(7)

    env_a.reset(seed=42)
    env_b.reset(seed=42)

    for _ in range(10):
        action = rng.uniform(
            low=env_a.action_space.low, high=env_a.action_space.high
        ).astype(np.float32)
        obs_a, *_ = env_a.step(action)
        obs_b, *_ = env_b.step(action)
        np.testing.assert_array_equal(obs_a, obs_b)


def test_action_clamping():
    """Out-of-bound actions must not crash and should be clamped."""
    env = HFSimEnv(seed=0)
    env.reset()
    bad_action = np.array([5.0, 5.0, 5.0, 5.0, 5.0], dtype=np.float32)
    obs, reward, terminated, truncated, info = env.step(bad_action)
    assert obs.shape == (16,)


def test_info_keys_complete():
    env = HFSimEnv(seed=0)
    env.reset()
    _, _, _, _, info = env.step(env.action_space.sample())
    required_keys = [
        "sim_time_s", "step_count", "continuation",
        "event_flags", "reward_components", "ownship",
        "threats", "targets", "wm_metadata",
    ]
    for key in required_keys:
        assert key in info, f"Missing info key: {key}"


def test_continuation_is_one_when_alive():
    env = HFSimEnv(seed=0)
    env.reset()
    _, _, terminated, truncated, info = env.step(env.action_space.sample())
    if not (terminated or truncated):
        assert info["continuation"] == 1.0


def test_max_steps_truncates():
    env = HFSimEnv(seed=0, max_steps=3)
    env.reset()
    for _ in range(2):
        _, _, terminated, truncated, _ = env.step(env.action_space.sample())
        if terminated:
            return  # early termination is fine
    _, _, terminated, truncated, _ = env.step(env.action_space.sample())
    # After max_steps steps, must be truncated or terminated
    assert truncated or terminated


def test_history_stays_empty():
    """EnvironmentRuntime.history must always be empty in RL mode."""
    env = HFSimEnv(seed=0)
    env.reset()
    for _ in range(20):
        env.step(env.action_space.sample())
        assert env._runtime.history == []


def test_observation_space_definition():
    env = HFSimEnv()
    assert env.observation_space.shape == (16,)
    assert env.observation_space.dtype == np.float32


def test_action_space_definition():
    env = HFSimEnv()
    assert env.action_space.shape == (5,)
    assert env.action_space.low[0] == 0.0   # throttle min
    assert env.action_space.high[0] == 1.0  # throttle max


def test_reset_increments_episode_count():
    env = HFSimEnv(seed=0)
    env.reset()
    assert env._episode_count == 1
    env.reset()
    assert env._episode_count == 2


def test_step_without_reset_raises():
    env = HFSimEnv()
    with pytest.raises(RuntimeError):
        env.step(env.action_space.sample())

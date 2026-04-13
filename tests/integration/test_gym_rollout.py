"""Integration tests for the full Gymnasium rollout pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from hf_sim.dataset import SequenceBuffer, TransitionBuffer, collect_episodes
from hf_sim.domain_rand import DomainRandConfig
from hf_sim.env import HFSimEnv, WorldModelEnvWrapper
from hf_sim.noise import NoiseConfig


def random_policy(obs: np.ndarray) -> np.ndarray:
    """Random policy: independent uniform in action space bounds."""
    return np.array(
        [np.random.uniform(0.0, 1.0)]           # throttle
        + list(np.random.uniform(-1.0, 1.0, 4)),  # rates + load_factor
        dtype=np.float32,
    )


def test_full_rollout_no_exception():
    """200 steps with a random policy must not raise any exception."""
    env = HFSimEnv(seed=0, max_steps=200)
    obs, _ = env.reset()
    for _ in range(200):
        obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
        assert obs.shape == (16,)
        assert np.all(np.isfinite(obs))
        if terminated or truncated:
            obs, _ = env.reset()


def test_collect_episodes_fills_buffer():
    env = HFSimEnv(seed=1, max_steps=50)
    buf = SequenceBuffer(capacity=10_000)
    stats = collect_episodes(env, random_policy, n_episodes=3, buffer=buf)
    assert len(buf) > 0
    assert stats["episodes"] == 3.0
    assert stats["mean_length"] > 0.0


def test_world_model_wrapper_auto_collects():
    env = HFSimEnv(seed=2, max_steps=50)
    seq_buf = SequenceBuffer(capacity=5000)
    wrapped = WorldModelEnvWrapper(env, seq_buf, auto_collect=True)
    obs, _ = wrapped.reset()
    steps = 0
    for _ in range(30):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = wrapped.step(action)
        steps += 1
        if terminated or truncated:
            obs, _ = wrapped.reset()
    assert len(seq_buf) == steps


def test_sequence_buffer_samples_after_collection():
    env = HFSimEnv(seed=3, max_steps=100)
    buf = SequenceBuffer(capacity=5000)
    collect_episodes(env, random_policy, n_episodes=5, buffer=buf)
    assert len(buf) >= 10

    obs_s, act_s, rew_s, cont_s = buf.sample_sequences(batch_size=4, seq_len=8)
    assert obs_s.shape == (4, 8, 16)
    assert act_s.shape == (4, 8, 5)
    # cont_seq must not have episode boundaries in first T-1 positions
    assert np.all(cont_s[:, :-1] == 1.0)


def test_domain_rand_rollout_no_exception():
    config = DomainRandConfig(
        drag_coeff_rand_frac=0.2,
        max_thrust_rand_frac=0.15,
        density_rand_frac=0.1,
        wind_max_mps=5.0,
        turbulence_max=0.3,
        spawn_jitter_m=50.0,
    )
    env = HFSimEnv(seed=5, max_steps=50, curriculum_level=5, domain_rand_config=config)
    obs, _ = env.reset()
    for _ in range(50):
        obs, _, terminated, truncated, _ = env.step(env.action_space.sample())
        if terminated or truncated:
            obs, _ = env.reset()
    assert obs.shape == (16,)


def test_noise_rollout_no_exception():
    noise = NoiseConfig(process_noise_scale=0.1, obs_noise_scale=0.02)
    env = HFSimEnv(seed=6, max_steps=50, noise_config=noise)
    obs, _ = env.reset()
    for _ in range(50):
        obs, _, terminated, truncated, _ = env.step(env.action_space.sample())
        assert np.all(obs >= -1.0) and np.all(obs <= 1.0)
        if terminated or truncated:
            obs, _ = env.reset()


def test_multiple_episodes_reset_correctly():
    """Episode count must increment and runtime must reinitialise on each reset."""
    env = HFSimEnv(seed=0, max_steps=10)
    for ep in range(1, 4):
        obs, _ = env.reset()
        assert env._episode_count == ep
        assert env._step_count == 0
        assert obs.shape == (16,)

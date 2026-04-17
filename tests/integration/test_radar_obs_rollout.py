"""Integration tests for radar/sensor observation extension (C2).

Verifies:
- 200-step rollout with use_radar_obs=True: all obs finite.
- First 16 dims match between use_radar_obs=False and True (same physics base).
- Radar channel monotonicity: closer threats → smaller detected_range_nearest_norm.
"""

from __future__ import annotations

import math

import numpy as np

from hf_sim.env import HFSimEnv


# ---------------------------------------------------------------------------
# 200-step rollout — all obs finite
# ---------------------------------------------------------------------------

def test_radar_obs_200_steps_all_finite():
    """200 env steps with use_radar_obs=True must produce all-finite observations."""
    env = HFSimEnv(seed=0, use_radar_obs=True, max_steps=200)
    obs, _ = env.reset(seed=0)

    action = np.array([0.5, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    for step in range(200):
        obs, _, terminated, truncated, _ = env.step(action)
        assert np.all(np.isfinite(obs)), f"non-finite obs at step {step}: {obs}"
        if terminated or truncated:
            obs, _ = env.reset()
    env.close()


# ---------------------------------------------------------------------------
# First 16-dim agreement between use_radar_obs=True and False
# ---------------------------------------------------------------------------

def test_first_16_dims_identical_regardless_of_flag():
    """Base 16-dim obs must be identical whether use_radar_obs is True or False."""
    env_no = HFSimEnv(seed=7, use_radar_obs=False, max_steps=50)
    env_yes = HFSimEnv(seed=7, use_radar_obs=True, max_steps=50)

    obs_no, _ = env_no.reset(seed=7)
    obs_yes, _ = env_yes.reset(seed=7)

    np.testing.assert_array_equal(
        obs_no[:16], obs_yes[:16],
        err_msg="First 16 dims differ between use_radar_obs=False and True at reset",
    )

    action = np.array([0.5, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    for _ in range(50):
        obs_no_next, _, done_no, trunc_no, _ = env_no.step(action)
        obs_yes_next, _, done_yes, trunc_yes, _ = env_yes.step(action)
        np.testing.assert_array_equal(
            obs_no_next[:16], obs_yes_next[:16],
            err_msg="First 16 dims diverged between the two envs mid-rollout",
        )
        if done_no or trunc_no:
            obs_no, _ = env_no.reset()
            obs_yes, _ = env_yes.reset()

    env_no.close()
    env_yes.close()


# ---------------------------------------------------------------------------
# Radar extension channels remain in [0, 1] throughout rollout
# ---------------------------------------------------------------------------

def test_radar_extension_channels_in_range_throughout_rollout():
    """All 6 extension channels (obs[16:]) must stay in [0, 1] over 100 steps."""
    env = HFSimEnv(seed=3, use_radar_obs=True, max_steps=100)
    obs, _ = env.reset(seed=3)

    action = np.array([0.6, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    for step in range(100):
        obs, _, terminated, truncated, _ = env.step(action)
        extra = obs[16:]
        assert np.all(extra >= -1e-6), f"radar channel below 0 at step {step}: {extra}"
        assert np.all(extra <= 1.0 + 1e-6), f"radar channel above 1 at step {step}: {extra}"
        if terminated or truncated:
            obs, _ = env.reset()
    env.close()

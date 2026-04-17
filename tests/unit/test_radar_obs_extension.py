"""Unit tests for C2 — radar/sensor observation extension (use_radar_obs flag)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from hf_sim.env import HFSimEnv, _build_radar_sensor_channels
from hf_sim.models import (
    AtmosphereState,
    EnvironmentRuntime,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
    TargetState,
    ThreatState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runtime(
    threats: list[ThreatState] | None = None,
    radar: RadarState | None = None,
    sensor: SensorState | None = None,
) -> EnvironmentRuntime:
    return EnvironmentRuntime(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, 1000.0],
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.02, "max_thrust_n": 20000.0, "lift_gain": 9.0},
        ),
        threats=threats or [],
        targets=[TargetState(identifier="tg-0", position_m=[8000.0, 0.0, 0.0], velocity_mps=[0.0, 0.0, 0.0])],
        environment=EnvironmentState(sim_time_s=0.0, terrain_reference=[100.0] * 4, flags={}),
        radar=radar or RadarState(),
        sensor=sensor or SensorState(contact_count=0, quality=1.0, detection_confidence=0.0),
        atmosphere=AtmosphereState(),
        rng_state={"seed": 0, "step_index": 0},
        mode_flags={"agent_count": 1},
        dt_internal=0.01,
        calibration_config={},
        history=[],
    )


# ---------------------------------------------------------------------------
# _build_radar_sensor_channels — 6 keys present and finite
# ---------------------------------------------------------------------------

def test_radar_sensor_channels_has_6_keys():
    runtime = _make_runtime()
    channels = _build_radar_sensor_channels(runtime)
    expected_keys = {
        "sensor_quality",
        "detection_confidence",
        "sensor_contact_count_norm",
        "radar_track_count_norm",
        "detected_range_nearest_norm",
        "detected_ranges_mean_norm",
    }
    assert expected_keys == set(channels.keys())


def test_radar_sensor_channels_all_finite():
    runtime = _make_runtime()
    channels = _build_radar_sensor_channels(runtime)
    for k, v in channels.items():
        assert math.isfinite(v), f"{k}={v} is not finite"


def test_radar_sensor_channels_all_in_0_1():
    runtime = _make_runtime(
        threats=[ThreatState("th-0", [2000.0, 0.0, 1000.0], [-20.0, 0.0, 0.0])],
        radar=RadarState(track_ids=["th-0"], detected_ranges_m=[2000.0]),
        sensor=SensorState(contact_count=1, quality=0.8, detection_confidence=0.6),
    )
    channels = _build_radar_sensor_channels(runtime)
    for k, v in channels.items():
        assert 0.0 <= v <= 1.0, f"{k}={v} out of [0,1]"


def test_radar_sensor_channels_no_threats_edge_case():
    """No threats → contact/track counts are 0, range channels 0.0."""
    runtime = _make_runtime(threats=[], radar=RadarState(), sensor=SensorState())
    channels = _build_radar_sensor_channels(runtime)
    assert channels["sensor_contact_count_norm"] == 0.0
    assert channels["radar_track_count_norm"] == 0.0
    assert channels["detected_range_nearest_norm"] == 0.0
    assert channels["detected_ranges_mean_norm"] == 0.0


# ---------------------------------------------------------------------------
# HFSimEnv observation_space shape
# ---------------------------------------------------------------------------

def test_default_obs_space_is_16():
    env = HFSimEnv(seed=0)
    assert env.observation_space.shape == (16,)
    env.close()


def test_radar_obs_space_is_22():
    env = HFSimEnv(seed=0, use_radar_obs=True)
    assert env.observation_space.shape == (22,)
    env.close()


# ---------------------------------------------------------------------------
# HFSimEnv reset returns correct obs shape
# ---------------------------------------------------------------------------

def test_default_reset_obs_shape_16():
    env = HFSimEnv(seed=0)
    obs, _ = env.reset(seed=0)
    assert obs.shape == (16,)
    env.close()


def test_radar_obs_reset_obs_shape_22():
    env = HFSimEnv(seed=0, use_radar_obs=True)
    obs, _ = env.reset(seed=0)
    assert obs.shape == (22,)
    env.close()


def test_radar_obs_last_6_channels_in_range():
    """The 6 radar/sensor channels appended must all be in [0, 1]."""
    env = HFSimEnv(seed=0, use_radar_obs=True)
    obs, _ = env.reset(seed=0)
    extra = obs[16:]
    assert extra.shape == (6,)
    assert np.all(extra >= -1e-6), f"channel below 0: {extra}"
    assert np.all(extra <= 1.0 + 1e-6), f"channel above 1: {extra}"
    env.close()

"""Unit tests for hf_sim.dataset."""

from __future__ import annotations

import pathlib

import numpy as np
import pytest

from hf_sim.dataset import (
    SequenceBuffer,
    Transition,
    TransitionBuffer,
    export_sequences_npz,
    export_transitions_npz,
)


def _make_obs(val: float = 0.0) -> np.ndarray:
    return np.full(16, val, dtype=np.float32)


def _make_action(val: float = 0.5) -> np.ndarray:
    return np.full(5, val, dtype=np.float32)


def _fill_buffer_one_episode(buf: SequenceBuffer, length: int = 100) -> None:
    for i in range(length):
        done = i == length - 1
        buf.add_transition(
            obs=_make_obs(float(i) / length),
            action=_make_action(),
            reward=1.0,
            next_obs=_make_obs(float(i + 1) / length),
            done=done,
        )


# ------------------------------------------------------------------
# TransitionBuffer
# ------------------------------------------------------------------

def test_transition_buffer_add_and_len():
    buf = TransitionBuffer(capacity=10)
    buf.add(Transition(_make_obs(), _make_action(), 1.0, _make_obs(), False, False))
    assert len(buf) == 1


def test_transition_buffer_respects_capacity():
    buf = TransitionBuffer(capacity=5)
    for _ in range(10):
        buf.add(Transition(_make_obs(), _make_action(), 0.0, _make_obs(), False, False))
    assert len(buf) == 5


def test_transition_buffer_sample():
    buf = TransitionBuffer(capacity=100)
    for i in range(50):
        buf.add(Transition(_make_obs(float(i)), _make_action(), float(i), _make_obs(), False, False))
    samples = buf.sample(batch_size=10)
    assert len(samples) == 10
    assert all(isinstance(s, Transition) for s in samples)


# ------------------------------------------------------------------
# SequenceBuffer
# ------------------------------------------------------------------

def test_sequence_buffer_add_and_len():
    buf = SequenceBuffer(capacity=200)
    _fill_buffer_one_episode(buf, length=50)
    assert len(buf) == 50


def test_sequence_buffer_capacity_ring():
    buf = SequenceBuffer(capacity=50)
    _fill_buffer_one_episode(buf, length=80)
    assert len(buf) == 50  # ring buffer capped


def test_sample_sequences_shapes():
    buf = SequenceBuffer(capacity=500)
    _fill_buffer_one_episode(buf, length=200)
    obs, act, rew, cont = buf.sample_sequences(batch_size=8, seq_len=16)
    assert obs.shape == (8, 16, 16)
    assert act.shape == (8, 16, 5)
    assert rew.shape == (8, 16)
    assert cont.shape == (8, 16)


def test_cont_seq_values_are_one_minus_done():
    buf = SequenceBuffer(capacity=100)
    # Single episode of length 50 (done=1 only at last step)
    for i in range(50):
        buf.add_transition(
            obs=_make_obs(), action=_make_action(), reward=1.0,
            next_obs=_make_obs(), done=(i == 49),
        )
    obs, act, rew, cont = buf.sample_sequences(batch_size=4, seq_len=10)
    # All cont values must be 0.0 or 1.0
    assert np.all((cont == 0.0) | (cont == 1.0))


def test_sequence_never_crosses_episode_boundary():
    """No valid sequence should have done=1 at positions [0..T-2]."""
    buf = SequenceBuffer(capacity=500)
    # 3 short episodes of length 20
    for _ep in range(3):
        for i in range(20):
            buf.add_transition(
                obs=_make_obs(), action=_make_action(), reward=1.0,
                next_obs=_make_obs(), done=(i == 19),
            )

    seq_len = 10
    obs, act, rew, cont = buf.sample_sequences(batch_size=50, seq_len=seq_len)
    # cont[b, t] = 0 means done at position t.  That's only valid at t == T-1.
    inner_cont = cont[:, :-1]  # positions 0..T-2
    assert np.all(inner_cont == 1.0), "Episode boundary found within sequence"


def test_empty_buffer_raises():
    buf = SequenceBuffer(capacity=100)
    with pytest.raises(ValueError):
        buf.sample_sequences(4, 10)


# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------

def test_export_transitions_npz_loadable():
    buf = TransitionBuffer(capacity=100)
    for i in range(20):
        buf.add(Transition(_make_obs(float(i)), _make_action(), float(i), _make_obs(), False, False))

    path = pathlib.Path.cwd() / "test_transitions_export.npz"
    try:
        export_transitions_npz(buf, path)
        with np.load(path) as data:
            assert "obs" in data
            assert "action" in data
            assert "reward" in data
            assert data["obs"].shape == (20, 16)
            assert data["action"].shape == (20, 5)
    finally:
        path.unlink(missing_ok=True)


def test_export_sequences_npz_loadable():
    buf = SequenceBuffer(capacity=500)
    _fill_buffer_one_episode(buf, length=200)

    path = pathlib.Path.cwd() / "test_sequences_export.npz"
    try:
        export_sequences_npz(buf, path, seq_len=10, n_sequences=50)
        with np.load(path) as data:
            assert "obs" in data
            assert "act" in data
            assert "rew" in data
            assert "cont" in data
            assert data["obs"].shape == (50, 10, 16)
            assert data["act"].shape == (50, 10, 5)
            assert data["rew"].shape == (50, 10)
            assert data["cont"].shape == (50, 10)
    finally:
        path.unlink(missing_ok=True)

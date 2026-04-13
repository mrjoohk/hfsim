"""Dataset collection and export for offline world-model training.

Two buffer types:
- TransitionBuffer: stores (obs, action, reward, next_obs, terminated, truncated)
  transitions. Good for basic MBRL algorithms.
- SequenceBuffer: ring-buffer with pre-allocated arrays.  Guarantees that
  sampled sequences never cross episode boundaries.  Outputs the
  (B, T, dim) format expected by RSSM / Dreamer training loops.

Export functions write compressed .npz files loadable with np.load().
"""

from __future__ import annotations

import pathlib
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


# ---------------------------------------------------------------------------
# TransitionBuffer
# ---------------------------------------------------------------------------

@dataclass
class Transition:
    obs: np.ndarray          # (obs_dim,) float32
    action: np.ndarray       # (act_dim,) float32
    reward: float
    next_obs: np.ndarray     # (obs_dim,) float32
    terminated: bool
    truncated: bool


class TransitionBuffer:
    """Simple ring buffer for (s, a, r, s', terminated, truncated) tuples."""

    def __init__(self, capacity: int = 100_000) -> None:
        self._buf: deque[Transition] = deque(maxlen=capacity)

    def add(self, transition: Transition) -> None:
        self._buf.append(transition)

    def sample(self, batch_size: int) -> list[Transition]:
        indices = np.random.randint(0, len(self._buf), size=batch_size)
        buf_list = list(self._buf)
        return [buf_list[i] for i in indices]

    def __len__(self) -> int:
        return len(self._buf)


# ---------------------------------------------------------------------------
# SequenceBuffer
# ---------------------------------------------------------------------------

class SequenceBuffer:
    """Ring buffer storing fixed-length sequences for RSSM / Dreamer training.

    Sequences are guaranteed to never cross episode boundaries.
    The done flag marks the end of an episode; valid sequence start indices
    are those where no done=1 exists at positions [0 .. seq_len-2] of the
    prospective window.

    Storage format (all float32, pre-allocated):
        obs   (capacity, obs_dim)
        acts  (capacity, act_dim)
        rews  (capacity,)
        dones (capacity,)   0.0 / 1.0 — combines terminated + truncated

    cont_seq = 1 - done  is derived on sample, so GRU state resets
    at episode boundaries in RSSM training loss computation.
    """

    def __init__(
        self,
        capacity: int = 50_000,
        obs_dim: int = 16,
        act_dim: int = 5,
    ) -> None:
        self._cap = capacity
        self._obs_dim = obs_dim
        self._act_dim = act_dim

        self._obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self._acts = np.zeros((capacity, act_dim), dtype=np.float32)
        self._rews = np.zeros((capacity,), dtype=np.float32)
        self._dones = np.zeros((capacity,), dtype=np.float32)

        self._head = 0   # next write position
        self._size = 0   # number of valid entries

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def add_transition(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_obs: np.ndarray,  # noqa: ARG002 — stored as next step's obs
        done: bool,
    ) -> None:
        """Store one (obs, action, reward, done) transition.

        next_obs is not stored explicitly; it will be obs at t+1.
        The caller is responsible for adding a final obs via add_obs_only()
        when the episode ends, or simply starting the next episode's reset obs
        as the next write — the done flag at the boundary handles the masking.
        """
        self._obs[self._head] = obs
        self._acts[self._head] = action
        self._rews[self._head] = float(reward)
        self._dones[self._head] = 1.0 if done else 0.0

        self._head = (self._head + 1) % self._cap
        self._size = min(self._size + 1, self._cap)

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def sample_sequences(
        self,
        batch_size: int,
        seq_len: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Sample (batch_size) sequences of length seq_len.

        Returns:
            obs_seq:  (B, T, obs_dim) float32
            act_seq:  (B, T, act_dim) float32
            rew_seq:  (B, T)          float32
            cont_seq: (B, T)          float32  — 1 - done (RSSM cont flag)

        A sequence is valid iff it does not contain done=1 at any position
        [0 .. seq_len-2] (a done at the last step T-1 is allowed).
        Raises ValueError if the buffer has fewer than seq_len entries.
        """
        if self._size < seq_len:
            raise ValueError(
                f"Buffer has {self._size} entries, need at least {seq_len}"
            )

        valid = self._valid_start_indices(seq_len)
        if len(valid) == 0:
            raise ValueError("No valid non-boundary sequence start indices found")

        chosen = valid[np.random.randint(0, len(valid), size=batch_size)]

        obs_out = np.empty((batch_size, seq_len, self._obs_dim), dtype=np.float32)
        act_out = np.empty((batch_size, seq_len, self._act_dim), dtype=np.float32)
        rew_out = np.empty((batch_size, seq_len), dtype=np.float32)
        cont_out = np.empty((batch_size, seq_len), dtype=np.float32)

        for b, start in enumerate(chosen):
            idx = [(start + t) % self._cap for t in range(seq_len)]
            obs_out[b] = self._obs[idx]
            act_out[b] = self._acts[idx]
            rew_out[b] = self._rews[idx]
            cont_out[b] = 1.0 - self._dones[idx]

        return obs_out, act_out, rew_out, cont_out

    def _valid_start_indices(self, seq_len: int) -> np.ndarray:
        """Return array of valid start positions in the ring buffer."""
        # Build flat view of the dones in ring-buffer order
        if self._size < self._cap:
            dones_flat = self._dones[: self._size]
            offset = 0
        else:
            # Wrap around: oldest data starts at self._head
            dones_flat = np.roll(self._dones, -self._head)
            offset = self._head

        n = len(dones_flat)
        if n < seq_len:
            return np.array([], dtype=np.int64)

        # A window [i, i+seq_len-1] is invalid if dones_flat[i..i+seq_len-2]
        # contains any 1. We only need to check positions 0..T-2 in the window.
        # Use cumsum to efficiently count dones in sliding windows.
        cs = np.concatenate([[0], np.cumsum(dones_flat[: n - 1])])
        window_done_count = cs[seq_len - 1:] - cs[: n - (seq_len - 1)]
        valid_linear = np.where(window_done_count == 0)[0]

        if self._size < self._cap:
            return valid_linear
        # Convert back to ring-buffer indices
        return (valid_linear + offset) % self._cap

    def __len__(self) -> int:
        return self._size


# ---------------------------------------------------------------------------
# Collection utility
# ---------------------------------------------------------------------------

def collect_episodes(
    env: Any,
    policy: Callable[[np.ndarray], np.ndarray],
    n_episodes: int,
    buffer: TransitionBuffer | SequenceBuffer,
) -> dict[str, float]:
    """Collect n_episodes using policy and fill buffer.

    policy: obs (16,) → action (5,) — use random_policy = env.action_space.sample
    Returns summary stats {"mean_return", "mean_length", "episodes"}.
    """
    returns = []
    lengths = []

    for _ in range(n_episodes):
        obs, _ = env.reset()
        ep_return = 0.0
        ep_len = 0
        done = False

        while not done:
            action = policy(obs)
            next_obs, reward, terminated, truncated, _ = env.step(action)
            buffer.add_transition(
                obs=obs,
                action=action,
                reward=reward,
                next_obs=next_obs,
                done=terminated or truncated,
            )
            obs = next_obs
            ep_return += float(reward)
            ep_len += 1
            done = terminated or truncated

        returns.append(ep_return)
        lengths.append(ep_len)

    return {
        "mean_return": float(np.mean(returns)) if returns else 0.0,
        "mean_length": float(np.mean(lengths)) if lengths else 0.0,
        "episodes": float(n_episodes),
    }


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------

def export_transitions_npz(
    buffer: TransitionBuffer,
    path: str | pathlib.Path,
) -> pathlib.Path:
    """Save all transitions in buffer as a compressed .npz file.

    Arrays saved: obs, action, reward, next_obs, terminated, truncated.
    All float32. Load with: data = np.load(path); data["obs"], ...
    """
    path = pathlib.Path(path)
    buf_list = list(buffer._buf)
    if not buf_list:
        raise ValueError("Buffer is empty")

    obs = np.array([t.obs for t in buf_list], dtype=np.float32)
    action = np.array([t.action for t in buf_list], dtype=np.float32)
    reward = np.array([t.reward for t in buf_list], dtype=np.float32)
    next_obs = np.array([t.next_obs for t in buf_list], dtype=np.float32)
    terminated = np.array([t.terminated for t in buf_list], dtype=np.float32)
    truncated = np.array([t.truncated for t in buf_list], dtype=np.float32)

    np.savez_compressed(
        path,
        obs=obs,
        action=action,
        reward=reward,
        next_obs=next_obs,
        terminated=terminated,
        truncated=truncated,
    )
    return path


def export_sequences_npz(
    buffer: SequenceBuffer,
    path: str | pathlib.Path,
    seq_len: int,
    n_sequences: int = 10_000,
) -> pathlib.Path:
    """Sample n_sequences and save as RSSM-ready .npz file.

    Arrays saved: obs (N,T,16), act (N,T,5), rew (N,T), cont (N,T).
    cont = 1 - done — the RSSM continuation flag.
    """
    path = pathlib.Path(path)
    obs_seq, act_seq, rew_seq, cont_seq = buffer.sample_sequences(n_sequences, seq_len)
    np.savez_compressed(
        path,
        obs=obs_seq,
        act=act_seq,
        rew=rew_seq,
        cont=cont_seq,
    )
    return path

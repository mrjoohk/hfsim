"""Minimal Gymnasium compatibility layer for test environments.

Used only when `gymnasium` is unavailable in the runtime environment.
"""

from __future__ import annotations

from typing import Any

import numpy as np


class _BaseEnv:
    metadata: dict[str, Any] = {}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):  # noqa: ARG002
        return None


class _BaseWrapper:
    def __init__(self, env: Any) -> None:
        self.env = env

    def reset(self, **kwargs: Any):
        return self.env.reset(**kwargs)

    def step(self, action: np.ndarray):
        return self.env.step(action)


class _Box:
    def __init__(self, low: Any, high: Any, shape: tuple[int, ...] | None = None, dtype: Any = np.float32) -> None:
        self.low = np.array(low, dtype=dtype)
        self.high = np.array(high, dtype=dtype)
        self.dtype = dtype
        self.shape = tuple(shape or self.low.shape)

    def sample(self) -> np.ndarray:
        return np.random.uniform(self.low, self.high).astype(self.dtype)


class _Spaces:
    Box = _Box


class GymnasiumCompat:
    Env = _BaseEnv
    Wrapper = _BaseWrapper
    spaces = _Spaces()


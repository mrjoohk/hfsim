"""DreamerV3 adapter — stub implementation.

This module provides a WorldModelBackend-compatible adapter for DreamerV3.
The actual DreamerV3 implementation is NOT included here; this stub shows
how to wire an external DreamerV3 library (dreamer-pytorch or jax-dreamer)
into the common WorldModelBackend interface.

To use:
1. Install a DreamerV3 library, e.g.:
     pip install dreamer-pytorch   # (if available)
   or use the official JAX implementation:
     https://github.com/danijar/dreamerv3

2. Replace the NotImplementedError bodies below with actual library calls,
   ensuring the (B, T, dim) tensor format is preserved.

The SequenceBuffer output format already matches DreamerV3's expected input:
    obs_seq  (B, T, 16)  float32
    act_seq  (B, T, 5)   float32
    rew_seq  (B, T)      float32
    cont_seq (B, T)      float32  — 1 - done
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    import torch
    from torch import Tensor

    from world_model.base import WorldModelOutput

    @dataclass
    class DreamerV3Config:
        """Configuration placeholder for DreamerV3 adapter."""
        obs_dim: int = 16
        act_dim: int = 5
        device: str = "cpu"
        library_kwargs: dict[str, Any] = field(default_factory=dict)

    class DreamerV3Adapter:
        """Adapter that wraps an external DreamerV3 library.

        All methods raise NotImplementedError until an actual DreamerV3
        library is integrated. The interface matches WorldModelBackend.
        """

        def __init__(self, config: DreamerV3Config | None = None) -> None:
            self.cfg = config or DreamerV3Config()
            self.device = torch.device(self.cfg.device)
            # TODO: initialise DreamerV3 model here, e.g.:
            #   from dreamer import DreamerV3
            #   self._model = DreamerV3(**self.cfg.library_kwargs)

        def train_step(
            self,
            obs_seq: Tensor,    # (B, T, obs_dim)
            act_seq: Tensor,    # (B, T, act_dim)
            rew_seq: Tensor,    # (B, T)
            cont_seq: Tensor,   # (B, T)
        ) -> WorldModelOutput:
            # TODO: call self._model.train_step(obs_seq, act_seq, rew_seq, cont_seq)
            #       and map output to WorldModelOutput NamedTuple.
            raise NotImplementedError(
                "DreamerV3Adapter.train_step: integrate a DreamerV3 library first. "
                "See dreamer_v3.py docstring for instructions."
            )

        def imagine_rollout(
            self,
            obs_init: Tensor,   # (B, obs_dim)
            act_seq: Tensor,    # (B, H, act_dim)
        ) -> WorldModelOutput:
            raise NotImplementedError("DreamerV3Adapter.imagine_rollout: not yet wired.")

        def encode(self, obs: Tensor) -> Tensor:
            raise NotImplementedError("DreamerV3Adapter.encode: not yet wired.")

        def save(self, path: str) -> None:
            raise NotImplementedError("DreamerV3Adapter.save: not yet wired.")

        def load(self, path: str) -> None:
            raise NotImplementedError("DreamerV3Adapter.load: not yet wired.")

except ImportError:
    class DreamerV3Config:  # type: ignore[no-redef]
        """Placeholder: install torch to use DreamerV3Adapter."""

    class DreamerV3Adapter:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError(
                "DreamerV3Adapter requires PyTorch. Install with: pip install torch"
            )

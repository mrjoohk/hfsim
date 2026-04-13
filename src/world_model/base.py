"""Abstract interface for world model backends.

All world model implementations (RSSM, DreamerV3, etc.) must satisfy
this Protocol so that training loops can swap backends without changes.

Input convention (matches SequenceBuffer.sample_sequences output):
    obs_seq:  (B, T, obs_dim) float32  — normalised observations [-1, 1]
    act_seq:  (B, T, act_dim) float32  — normalised actions
    rew_seq:  (B, T)          float32  — scalar rewards
    cont_seq: (B, T)          float32  — 1.0=continue, 0.0=episode boundary

All tensors are torch.Tensor.  Backends handle device placement internally.
"""

from __future__ import annotations

from typing import NamedTuple, Protocol, runtime_checkable

try:
    import torch

    class WorldModelOutput(NamedTuple):
        """Standard output from a world model forward / training pass."""

        obs_pred: torch.Tensor     # (B, T, obs_dim) predicted next observations
        reward_pred: torch.Tensor  # (B, T)          predicted rewards
        cont_pred: torch.Tensor    # (B, T)          predicted continuation probs
        latent: torch.Tensor       # (B, T, latent_dim) posterior latent states
        loss: torch.Tensor         # scalar — total training loss

    @runtime_checkable
    class WorldModelBackend(Protocol):
        """Common interface for world model backends.

        Implementations must provide:
        - train_step: one gradient update step
        - imagine_rollout: open-loop rollout from initial obs
        - encode: obs → latent vector (for policy input)
        - save / load: checkpoint persistence
        """

        def train_step(
            self,
            obs_seq: torch.Tensor,    # (B, T, obs_dim)
            act_seq: torch.Tensor,    # (B, T, act_dim)
            rew_seq: torch.Tensor,    # (B, T)
            cont_seq: torch.Tensor,   # (B, T)
        ) -> WorldModelOutput:
            """Execute one training step and return losses + predictions."""
            ...

        def imagine_rollout(
            self,
            obs_init: torch.Tensor,   # (B, obs_dim)
            act_seq: torch.Tensor,    # (B, H, act_dim) — H-step horizon
        ) -> WorldModelOutput:
            """Open-loop rollout from initial observation under given actions."""
            ...

        def encode(
            self,
            obs: torch.Tensor,        # (B, obs_dim)
        ) -> torch.Tensor:            # (B, latent_dim)
            """Encode observation into latent state for policy input."""
            ...

        def save(self, path: str) -> None:
            """Save model weights to path."""
            ...

        def load(self, path: str) -> None:
            """Load model weights from path."""
            ...

except ImportError:
    # PyTorch not installed — define placeholder so imports don't break
    class WorldModelOutput:  # type: ignore[no-redef]
        """Placeholder when torch is not installed."""

    class WorldModelBackend:  # type: ignore[no-redef]
        """Placeholder when torch is not installed."""

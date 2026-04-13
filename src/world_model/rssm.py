"""RSSM (Recurrent State Space Model) world model — PyTorch implementation.

Architecture (Dreamer-style RSSM with categorical latents):
  Encoder:        Linear(obs_dim → embed_dim)
  GRU (sequence model): (h_{t-1}, embed_t) → h_t  [deterministic]
  Prior network:  MLP(h_t) → logits over (n_categoricals, latent_dim)
  Posterior net:  MLP(h_t, embed_t) → logits over (n_categoricals, latent_dim)
  Decoder:        MLP(h_t ⊕ z_t → obs_dim)
  Reward head:    MLP(h_t ⊕ z_t → 1)
  Continue head:  MLP(h_t ⊕ z_t → 1) + Sigmoid  (Bernoulli)

Latent z_t: straight-through categorical of shape (n_categoricals, latent_dim)
  → flattened to (n_categoricals * latent_dim,) for downstream MLPs.

Training loss:
  L = recon_loss + beta * kl_loss + reward_loss + cont_loss
  where kl_loss is masked by cont_seq (no KL at episode boundaries).

Reference: Hafner et al. "Mastering Diverse Domains through World Models" (2023).
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch import Tensor

    from world_model.base import WorldModelOutput

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @dataclass
    class RSSMConfig:
        obs_dim: int = 16
        act_dim: int = 5
        embed_dim: int = 128          # encoder output dimension
        hidden_dim: int = 256         # GRU hidden state dimension
        n_categoricals: int = 32      # number of categorical variables
        latent_dim: int = 32          # categories per categorical variable
        reward_layers: int = 2
        cont_layers: int = 2
        beta_kl: float = 0.1          # KL loss weight
        learning_rate: float = 3e-4
        device: str = "cpu"

        @property
        def z_dim(self) -> int:
            """Flattened latent dimension."""
            return self.n_categoricals * self.latent_dim

        @property
        def feat_dim(self) -> int:
            """Concatenated (h, z) feature dimension fed to heads."""
            return self.hidden_dim + self.z_dim

    # ------------------------------------------------------------------
    # Network components
    # ------------------------------------------------------------------

    def _mlp(in_dim: int, out_dim: int, n_layers: int = 2, hidden: int = 256) -> nn.Sequential:
        layers: list[nn.Module] = []
        d = in_dim
        for _ in range(n_layers):
            layers += [nn.Linear(d, hidden), nn.SiLU()]
            d = hidden
        layers.append(nn.Linear(d, out_dim))
        return nn.Sequential(*layers)

    class _Encoder(nn.Module):
        def __init__(self, obs_dim: int, embed_dim: int) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(obs_dim, embed_dim),
                nn.SiLU(),
                nn.Linear(embed_dim, embed_dim),
                nn.SiLU(),
            )

        def forward(self, obs: Tensor) -> Tensor:  # (..., obs_dim) → (..., embed)
            return self.net(obs)

    class _SequenceModel(nn.Module):
        """GRU-based deterministic sequence model."""

        def __init__(self, embed_dim: int, act_dim: int, hidden_dim: int, z_dim: int) -> None:
            super().__init__()
            self.gru = nn.GRUCell(embed_dim + act_dim + z_dim, hidden_dim)

        def forward(
            self,
            embed: Tensor,    # (B, embed_dim)
            action: Tensor,   # (B, act_dim)
            z_prev: Tensor,   # (B, z_dim)
            h_prev: Tensor,   # (B, hidden_dim)
        ) -> Tensor:          # (B, hidden_dim)
            inp = torch.cat([embed, action, z_prev], dim=-1)
            return self.gru(inp, h_prev)

    class _CategoricalDistNet(nn.Module):
        """Maps features to straight-through categorical latent z."""

        def __init__(self, in_dim: int, n_categoricals: int, latent_dim: int) -> None:
            super().__init__()
            self.n_cat = n_categoricals
            self.lat = latent_dim
            self.net = nn.Linear(in_dim, n_categoricals * latent_dim)

        def forward(self, x: Tensor) -> tuple[Tensor, Tensor]:
            """Returns (z_sample, logits).
            z_sample: (B, n_cat * lat) via straight-through.
            logits:   (B, n_cat, lat) for KL computation.
            """
            logits = self.net(x).view(*x.shape[:-1], self.n_cat, self.lat)
            # Straight-through estimator
            probs = F.softmax(logits, dim=-1)
            one_hot = F.one_hot(probs.argmax(dim=-1), self.lat).float()
            z = (one_hot + probs - probs.detach()).view(*x.shape[:-1], -1)
            return z, logits

    # ------------------------------------------------------------------
    # RSSM World Model
    # ------------------------------------------------------------------

    class RSSMWorldModel:
        """RSSM world model satisfying the WorldModelBackend protocol.

        Training loop example:
            wm = RSSMWorldModel(RSSMConfig())
            obs_seq, act_seq, rew_seq, cont_seq = buf.sample_sequences(32, 50)
            out = wm.train_step(
                torch.from_numpy(obs_seq),
                torch.from_numpy(act_seq),
                torch.from_numpy(rew_seq),
                torch.from_numpy(cont_seq),
            )
            print(out.loss.item())
        """

        def __init__(self, config: RSSMConfig | None = None) -> None:
            self.cfg = config or RSSMConfig()
            c = self.cfg
            self.device = torch.device(c.device)

            self.encoder = _Encoder(c.obs_dim, c.embed_dim).to(self.device)
            self.seq_model = _SequenceModel(c.embed_dim, c.act_dim, c.hidden_dim, c.z_dim).to(self.device)
            self.prior_net = _CategoricalDistNet(c.hidden_dim, c.n_categoricals, c.latent_dim).to(self.device)
            self.posterior_net = _CategoricalDistNet(c.hidden_dim + c.embed_dim, c.n_categoricals, c.latent_dim).to(self.device)
            self.decoder = _mlp(c.feat_dim, c.obs_dim, n_layers=2, hidden=c.hidden_dim).to(self.device)
            self.reward_head = _mlp(c.feat_dim, 1, n_layers=c.reward_layers, hidden=c.hidden_dim).to(self.device)
            self.cont_head = nn.Sequential(
                *_mlp(c.feat_dim, 1, n_layers=c.cont_layers, hidden=c.hidden_dim),
                nn.Sigmoid(),
            ).to(self.device)

            params = (
                list(self.encoder.parameters())
                + list(self.seq_model.parameters())
                + list(self.prior_net.parameters())
                + list(self.posterior_net.parameters())
                + list(self.decoder.parameters())
                + list(self.reward_head.parameters())
                + list(self.cont_head.parameters())
            )
            self.optimizer = torch.optim.Adam(params, lr=c.learning_rate)

        # --------------------------------------------------------------
        # Internal: unroll one batch through T timesteps
        # --------------------------------------------------------------

        def _unroll(
            self,
            obs_seq: Tensor,   # (B, T, obs_dim)
            act_seq: Tensor,   # (B, T, act_dim)
            cont_seq: Tensor,  # (B, T)
        ) -> tuple[list[Tensor], list[Tensor], list[Tensor], list[Tensor], list[Tensor]]:
            """Unroll RSSM over a sequence, return per-step tensors."""
            B, T, _ = obs_seq.shape
            c = self.cfg
            h = torch.zeros(B, c.hidden_dim, device=self.device)
            z = torch.zeros(B, c.z_dim, device=self.device)
            a_prev = torch.zeros(B, c.act_dim, device=self.device)

            feats, prior_logits_list, post_logits_list, z_list, h_list = [], [], [], [], []

            for t in range(T):
                embed = self.encoder(obs_seq[:, t])
                # Reset hidden state at episode boundaries
                cont = cont_seq[:, t].unsqueeze(-1)  # (B, 1)
                h = h * cont
                z = z * cont

                h = self.seq_model(embed, a_prev, z, h)

                _, prior_logits = self.prior_net(h)
                z_post, post_logits = self.posterior_net(torch.cat([h, embed], dim=-1))

                feat = torch.cat([h, z_post], dim=-1)
                feats.append(feat)
                prior_logits_list.append(prior_logits)
                post_logits_list.append(post_logits)
                z_list.append(z_post)
                h_list.append(h)

                z = z_post
                a_prev = act_seq[:, t]

            return feats, prior_logits_list, post_logits_list, z_list, h_list

        # --------------------------------------------------------------
        # WorldModelBackend interface
        # --------------------------------------------------------------

        def train_step(
            self,
            obs_seq: Tensor,
            act_seq: Tensor,
            rew_seq: Tensor,
            cont_seq: Tensor,
        ) -> WorldModelOutput:
            obs_seq = obs_seq.to(self.device)
            act_seq = act_seq.to(self.device)
            rew_seq = rew_seq.to(self.device)
            cont_seq = cont_seq.to(self.device)

            feats, prior_logits_list, post_logits_list, z_list, h_list = self._unroll(
                obs_seq, act_seq, cont_seq
            )

            T = obs_seq.shape[1]
            feats_t = torch.stack(feats, dim=1)          # (B, T, feat_dim)
            prior_t = torch.stack(prior_logits_list, dim=1)  # (B, T, n_cat, lat)
            post_t = torch.stack(post_logits_list, dim=1)    # (B, T, n_cat, lat)

            obs_pred = self.decoder(feats_t)             # (B, T, obs_dim)
            rew_pred = self.reward_head(feats_t).squeeze(-1)  # (B, T)
            cont_pred = self.cont_head(feats_t).squeeze(-1)   # (B, T)
            latent = feats_t                              # (B, T, feat_dim)

            # Reconstruction loss
            recon_loss = F.mse_loss(obs_pred, obs_seq)

            # KL loss (masked by cont_seq — no penalty at episode boundaries)
            kl = F.kl_div(
                F.log_softmax(prior_t, dim=-1),
                F.softmax(post_t, dim=-1),
                reduction="none",
            ).sum(dim=-1)  # (B, T, n_cat)
            kl = kl.sum(dim=-1)   # (B, T)
            kl_loss = (kl * cont_seq).mean()

            # Reward and continuation losses
            rew_loss = F.mse_loss(rew_pred, rew_seq)
            cont_loss = F.binary_cross_entropy(cont_pred, cont_seq)

            loss = recon_loss + self.cfg.beta_kl * kl_loss + rew_loss + cont_loss

            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            return WorldModelOutput(
                obs_pred=obs_pred.detach(),
                reward_pred=rew_pred.detach(),
                cont_pred=cont_pred.detach(),
                latent=latent.detach(),
                loss=loss.detach(),
            )

        def imagine_rollout(
            self,
            obs_init: Tensor,  # (B, obs_dim)
            act_seq: Tensor,   # (B, H, act_dim)
        ) -> WorldModelOutput:
            obs_init = obs_init.to(self.device)
            act_seq = act_seq.to(self.device)
            B, H, _ = act_seq.shape
            c = self.cfg

            h = torch.zeros(B, c.hidden_dim, device=self.device)
            z = torch.zeros(B, c.z_dim, device=self.device)
            embed = self.encoder(obs_init)
            # Initial posterior from obs_init
            z, _ = self.posterior_net(torch.cat([h, embed], dim=-1))

            feats = []
            for t in range(H):
                h = self.seq_model(embed, act_seq[:, t], z, h)
                z, _ = self.prior_net(h)
                feat = torch.cat([h, z], dim=-1)
                feats.append(feat)
                embed = self.decoder(feat)  # imagine next obs as encoder input

            feats_t = torch.stack(feats, dim=1)
            obs_pred = self.decoder(feats_t)
            rew_pred = self.reward_head(feats_t).squeeze(-1)
            cont_pred = self.cont_head(feats_t).squeeze(-1)

            dummy_loss = torch.tensor(0.0, device=self.device)
            return WorldModelOutput(
                obs_pred=obs_pred,
                reward_pred=rew_pred,
                cont_pred=cont_pred,
                latent=feats_t,
                loss=dummy_loss,
            )

        def encode(self, obs: Tensor) -> Tensor:
            obs = obs.to(self.device)
            return self.encoder(obs)

        def save(self, path: str) -> None:
            torch.save({
                "encoder": self.encoder.state_dict(),
                "seq_model": self.seq_model.state_dict(),
                "prior_net": self.prior_net.state_dict(),
                "posterior_net": self.posterior_net.state_dict(),
                "decoder": self.decoder.state_dict(),
                "reward_head": self.reward_head.state_dict(),
                "cont_head": self.cont_head.state_dict(),
                "config": self.cfg,
            }, path)

        def load(self, path: str) -> None:
            ckpt = torch.load(path, map_location=self.device)
            self.encoder.load_state_dict(ckpt["encoder"])
            self.seq_model.load_state_dict(ckpt["seq_model"])
            self.prior_net.load_state_dict(ckpt["prior_net"])
            self.posterior_net.load_state_dict(ckpt["posterior_net"])
            self.decoder.load_state_dict(ckpt["decoder"])
            self.reward_head.load_state_dict(ckpt["reward_head"])
            self.cont_head.load_state_dict(ckpt["cont_head"])

except ImportError:
    # PyTorch not installed — provide informative placeholder
    class RSSMConfig:  # type: ignore[no-redef]
        """Placeholder: install torch to use RSSMWorldModel."""

    class RSSMWorldModel:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError(
                "RSSMWorldModel requires PyTorch. Install with: pip install torch"
            )

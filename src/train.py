"""HF_Sim training entry point.

Called by the FastAPI training runner as a subprocess::

    python src/train.py [--mlflow-uri URI] [--config-json JSON] [--episodes N]

Per-episode metrics are emitted to **stdout as a single JSON line** so the
parent process (FastAPI TrainingRunner) can pipe them to WebSocket clients.

MLflow is optional — if not installed the training proceeds without it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is importable when run as a standalone script
_SRC = Path(__file__).parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np

from hf_sim.dataset import SequenceBuffer
from hf_sim.ray_runtime import EpisodeCollectionResult, LocalCollector, LocalEnvWorker


# ---------------------------------------------------------------------------
# Optional MLflow
# ---------------------------------------------------------------------------

def _try_mlflow(uri: str | None) -> object | None:
    try:
        import mlflow  # type: ignore[import-untyped]
        if uri:
            mlflow.set_tracking_uri(uri)
        return mlflow
    except ModuleNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Policy (random baseline — replace with learned actor later)
# ---------------------------------------------------------------------------

def _random_policy(obs: np.ndarray) -> np.ndarray:  # noqa: ARG001
    """Random action in [throttle, roll, pitch, yaw, load_factor]."""
    return np.array(
        [np.random.uniform(0.3, 0.8),   # throttle
         np.random.uniform(-0.2, 0.2),  # roll_rate
         np.random.uniform(-0.1, 0.1),  # pitch_rate
         np.random.uniform(-0.05, 0.05),# yaw_rate
         1.0],                           # load_factor
        dtype=np.float32,
    )


# ---------------------------------------------------------------------------
# Training loop helpers
# ---------------------------------------------------------------------------

def _collect_episodes(
    worker: LocalEnvWorker,
    collector: LocalCollector,
    buffer: SequenceBuffer,
    n_episodes: int,
) -> EpisodeCollectionResult:
    return collector.collect_worker_episodes(
        worker, _random_policy, n_episodes=n_episodes, buffer=buffer
    )


def _train_rssm(
    buffer: SequenceBuffer,
    n_steps: int,
    batch: int,
    seq_len: int,
    profile_dir: str | None = None,
) -> float:
    """One round of RSSM gradient updates. Returns mean loss."""
    try:
        import torch  # type: ignore[import-untyped]
        from world_model.rssm import RSSMConfig, RSSMWorldModel
    except ModuleNotFoundError:
        return float("nan")

    if not hasattr(_train_rssm, "_model"):
        _train_rssm._model = RSSMWorldModel(RSSMConfig())  # type: ignore[attr-defined]

    model = _train_rssm._model  # type: ignore[attr-defined]
    losses: list[float] = []

    def _steps() -> None:
        for _ in range(n_steps):
            try:
                obs, act, rew, cont = buffer.sample_sequences(batch, seq_len)
            except ValueError:
                break
            out = model.train_step(*[torch.from_numpy(x) for x in [obs, act, rew, cont]])
            losses.append(float(out.loss))

    if profile_dir is not None:
        import time as _t
        _dir = Path(profile_dir)
        _dir.mkdir(parents=True, exist_ok=True)
        with torch.profiler.profile(  # type: ignore[attr-defined]
            activities=[torch.profiler.ProfilerActivity.CPU],  # type: ignore[attr-defined]
            record_shapes=True,
        ) as prof:
            _steps()
        prof.export_chrome_trace(str(_dir / f"trace_{int(_t.time())}.json"))
    else:
        _steps()

    return float(np.mean(losses)) if losses else float("nan")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--mlflow-uri", default=None)
    p.add_argument("--config-json", default="{}")
    p.add_argument("--episodes", type=int, default=500)
    p.add_argument("--profile-dir", default=None, help="Enable torch profiler; traces saved here")
    p.add_argument("--collect-per-iter", type=int, default=4)
    p.add_argument("--train-steps", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--seq-len", type=int, default=50)
    p.add_argument("--buffer-capacity", type=int, default=50_000)
    p.add_argument("--curriculum-level", type=int, default=0)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def _emit(data: dict) -> None:
    """Print one JSON line to stdout (FastAPI pipe reads this)."""
    print(json.dumps(data), flush=True)


def main() -> None:
    args = _parse_args()
    config: dict = json.loads(args.config_json)

    # Allow config-json overrides
    episodes        = config.get("episodes",          args.episodes)
    collect_per     = config.get("collect_per_iter",  args.collect_per_iter)
    train_steps     = config.get("train_steps",       args.train_steps)
    batch_size      = config.get("batch_size",        args.batch_size)
    seq_len         = config.get("seq_len",           args.seq_len)
    buf_cap         = config.get("buffer_capacity",   args.buffer_capacity)
    curriculum      = config.get("curriculum_level",  args.curriculum_level)
    seed            = config.get("seed",              args.seed)
    profile_dir     = config.get("profile_dir",       args.profile_dir)

    # MLflow (optional)
    mlflow = _try_mlflow(args.mlflow_uri)
    run = None
    if mlflow:
        mlflow.set_experiment("hfsim")
        run = mlflow.start_run()
        mlflow.log_params({
            "episodes": episodes, "collect_per_iter": collect_per,
            "train_steps": train_steps, "batch_size": batch_size,
            "seq_len": seq_len, "curriculum_level": curriculum, "seed": seed,
        })

    # Setup
    np.random.seed(seed)
    buffer    = SequenceBuffer(capacity=buf_cap)
    worker    = LocalEnvWorker({"curriculum_level": curriculum, "seed": seed})
    collector = LocalCollector()

    total_episodes = 0
    total_steps    = 0

    try:
        while total_episodes < episodes:
            # --- Collect ---
            result = _collect_episodes(worker, collector, buffer, n_episodes=collect_per)
            total_episodes += result.episodes
            total_steps    += sum(result.lengths)

            # Reward component breakdown (from last episode info)
            reward_components: dict[str, float] = {}

            # --- Train RSSM ---
            mean_loss = _train_rssm(buffer, train_steps, batch_size, seq_len, profile_dir=profile_dir)

            # --- Emit metric line ---
            metric = {
                "episode":           total_episodes,
                "step_count":        total_steps,
                "mean_return":       result.mean_return,
                "mean_length":       result.mean_length,
                "rssm_loss":         mean_loss,
                "reward_components": reward_components,
                "status":            "TRAINING",
            }
            _emit(metric)

            if mlflow:
                mlflow.log_metric("mean_return", result.mean_return, step=total_steps)
                mlflow.log_metric("mean_length", result.mean_length, step=total_steps)
                if not (mean_loss != mean_loss):  # isfinite check without math import
                    mlflow.log_metric("rssm_loss", mean_loss, step=total_steps)

    except KeyboardInterrupt:
        pass
    finally:
        worker.close()
        if mlflow and run:
            mlflow.end_run()

    _emit({"status": "STOPPED", "total_episodes": total_episodes, "total_steps": total_steps})


if __name__ == "__main__":
    main()

"""Optional Ray orchestration layer for HF_Sim training environments.

This module keeps IF-02 / IF-03 as local deterministic kernels and adds
worker-oriented orchestration around HFSimEnv. Ray is optional:

- LocalEnvWorker / LocalLoggerWorker / LocalCollector work without Ray
- create_ray_actor_classes() wraps those workers when Ray is available
"""

from __future__ import annotations

import copy
import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import numpy as np

from hf_sim.dataset import SequenceBuffer, TransitionBuffer
from hf_sim.env import HFSimEnv
from hf_sim.models import BranchRuntimeResult, EnvironmentCheckpoint
from hf_sim.validation_logging import (
    build_runtime_log_entry,
    export_validation_log_jsonl,
    export_validation_summary_csv,
    flatten_branch_runtime_result,
)

_if03 = importlib.import_module("if.if03_snapshot")
_uf03 = importlib.import_module("uf.if03_snapshot")

if_03_branch_snapshot_rollout = _if03.if_03_branch_snapshot_rollout
capture_environment_checkpoint = _uf03.capture_environment_checkpoint


@dataclass(slots=True)
class ChunkTransition:
    obs: np.ndarray
    action: np.ndarray
    reward: float
    next_obs: np.ndarray
    terminated: bool
    truncated: bool
    info: dict[str, Any]


@dataclass(slots=True)
class ChunkRolloutResult:
    transitions: list[ChunkTransition]
    final_obs: np.ndarray
    final_info: dict[str, Any]
    final_done: bool


@dataclass(slots=True)
class EpisodeCollectionResult:
    episodes: int
    mean_return: float
    mean_length: float
    returns: list[float] = field(default_factory=list)
    lengths: list[int] = field(default_factory=list)


def try_import_ray() -> Any | None:
    """Return the ray module when available, otherwise None."""
    try:
        return importlib.import_module("ray")
    except ModuleNotFoundError:
        return None


class LocalEnvWorker:
    """Long-lived local worker holding one HFSimEnv instance."""

    def __init__(self, env_kwargs: dict[str, Any] | None = None) -> None:
        self._env_kwargs = dict(env_kwargs or {})
        self._env = HFSimEnv(**self._env_kwargs)
        self._last_obs: np.ndarray | None = None
        self._last_info: dict[str, Any] | None = None

    @property
    def env(self) -> HFSimEnv:
        return self._env

    def reset(self, *, seed: int | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        obs, info = self._env.reset(seed=seed)
        self._last_obs = obs
        self._last_info = info
        return obs, info

    def step_chunk(self, actions: Iterable[np.ndarray], *, auto_reset: bool = True) -> ChunkRolloutResult:
        """Run a chunk of actions on one persistent environment."""
        if self._last_obs is None:
            self.reset()

        transitions: list[ChunkTransition] = []
        done = False
        final_info = self._last_info or {}
        for action in actions:
            if done and auto_reset:
                self.reset()
                done = False
            obs = np.array(self._last_obs, copy=True)
            next_obs, reward, terminated, truncated, info = self._env.step(np.asarray(action, dtype=np.float32))
            transition = ChunkTransition(
                obs=obs,
                action=np.asarray(action, dtype=np.float32),
                reward=float(reward),
                next_obs=np.array(next_obs, copy=True),
                terminated=bool(terminated),
                truncated=bool(truncated),
                info=copy.deepcopy(info),
            )
            transitions.append(transition)
            self._last_obs = next_obs
            self._last_info = info
            final_info = info
            done = bool(terminated or truncated)

        return ChunkRolloutResult(
            transitions=transitions,
            final_obs=np.array(self._last_obs, copy=True),
            final_info=copy.deepcopy(final_info),
            final_done=done,
        )

    def capture_checkpoint(self, *, source: str = "current", k: int = 0) -> EnvironmentCheckpoint:
        """Capture a checkpoint from the worker-owned environment runtime."""
        if self._env._runtime is None:
            self.reset()
        request_cls = importlib.import_module("hf_sim.models").BranchRolloutRequest
        request = request_cls(
            runtime=self._env._runtime,
            runtime_source_spec={"source": source, "k": k},
            branch_mode="single_action_set",
            branch_controls=[{"throttle": 0.0, "roll": 0.0, "pitch": 0.0}],
            horizon=1,
        )
        return capture_environment_checkpoint(request)

    def branch_rollout(
        self,
        *,
        runtime_source_spec: dict[str, Any],
        branch_mode: str,
        branch_controls: list[dict[str, Any]],
        horizon: int,
    ) -> BranchRuntimeResult:
        """Execute IF-03 branch rollout from the worker's current runtime."""
        if self._env._runtime is None:
            self.reset()
        request_cls = importlib.import_module("hf_sim.models").BranchRolloutRequest
        request = request_cls(
            runtime=self._env._runtime,
            runtime_source_spec=dict(runtime_source_spec),
            branch_mode=branch_mode,
            branch_controls=copy.deepcopy(branch_controls),
            horizon=int(horizon),
        )
        return if_03_branch_snapshot_rollout(request)

    def collect_episode(
        self,
        policy: Callable[[np.ndarray], np.ndarray],
        *,
        max_steps: int | None = None,
    ) -> ChunkRolloutResult:
        """Collect one episode using the supplied policy."""
        obs, info = self.reset()
        transitions: list[ChunkTransition] = []
        step_limit = max_steps or self._env._max_steps
        for _ in range(step_limit):
            action = np.asarray(policy(obs), dtype=np.float32)
            next_obs, reward, terminated, truncated, info = self._env.step(action)
            transitions.append(
                ChunkTransition(
                    obs=np.array(obs, copy=True),
                    action=action,
                    reward=float(reward),
                    next_obs=np.array(next_obs, copy=True),
                    terminated=bool(terminated),
                    truncated=bool(truncated),
                    info=copy.deepcopy(info),
                )
            )
            obs = next_obs
            if terminated or truncated:
                break
        self._last_obs = obs
        self._last_info = info
        return ChunkRolloutResult(
            transitions=transitions,
            final_obs=np.array(obs, copy=True),
            final_info=copy.deepcopy(info),
            final_done=bool(transitions[-1].terminated or transitions[-1].truncated) if transitions else False,
        )

    def close(self) -> None:
        self._env.close()


class LocalCollector:
    """Collect rollout data from workers into HF_Sim buffers."""

    def __init__(self, buffer: TransitionBuffer | SequenceBuffer) -> None:
        self._buffer = buffer

    def collect_worker_episodes(
        self,
        worker: LocalEnvWorker,
        policy: Callable[[np.ndarray], np.ndarray],
        *,
        n_episodes: int,
    ) -> EpisodeCollectionResult:
        returns: list[float] = []
        lengths: list[int] = []
        for _ in range(n_episodes):
            result = worker.collect_episode(policy)
            episode_return = 0.0
            for transition in result.transitions:
                done = transition.terminated or transition.truncated
                if isinstance(self._buffer, SequenceBuffer):
                    self._buffer.add_transition(
                        obs=transition.obs,
                        action=transition.action,
                        reward=transition.reward,
                        next_obs=transition.next_obs,
                        done=done,
                    )
                else:
                    transition_cls = importlib.import_module("hf_sim.dataset").Transition
                    self._buffer.add(
                        transition_cls(
                            obs=transition.obs,
                            action=transition.action,
                            reward=transition.reward,
                            next_obs=transition.next_obs,
                            terminated=transition.terminated,
                            truncated=transition.truncated,
                        )
                    )
                episode_return += transition.reward
            returns.append(episode_return)
            lengths.append(len(result.transitions))
        return EpisodeCollectionResult(
            episodes=n_episodes,
            mean_return=float(np.mean(returns)) if returns else 0.0,
            mean_length=float(np.mean(lengths)) if lengths else 0.0,
            returns=returns,
            lengths=lengths,
        )


class LocalLoggerWorker:
    """Asynchronous-friendly logging/export worker."""

    def export_runtime_chunk_logs(
        self,
        runtime_entries: Iterable[dict[str, Any]],
        *,
        jsonl_path: str,
        csv_path: str,
    ) -> dict[str, str]:
        jsonl = export_validation_log_jsonl(runtime_entries, jsonl_path)
        csv = export_validation_summary_csv(runtime_entries, csv_path)
        return {"jsonl_path": str(jsonl), "csv_path": str(csv)}

    def export_branch_rollout_logs(
        self,
        branch_runtime_result: BranchRuntimeResult,
        *,
        jsonl_path: str,
    ) -> dict[str, str]:
        rows = flatten_branch_runtime_result(branch_runtime_result)
        jsonl = export_validation_log_jsonl(rows, jsonl_path)
        return {"jsonl_path": str(jsonl), "branch_count": str(branch_runtime_result.branch_count)}

    def build_runtime_entry(
        self,
        worker: LocalEnvWorker,
        control: dict[str, Any],
        *,
        step_index: int,
        branch_id: str = "main",
    ) -> dict[str, Any]:
        if worker.env._runtime is None:
            worker.reset()
        return build_runtime_log_entry(worker.env._runtime, control, step_index=step_index, branch_id=branch_id)


def create_ray_actor_classes(ray_module: Any | None = None) -> dict[str, Any] | None:
    """Wrap local workers as Ray actors when Ray is available."""
    ray_mod = ray_module or try_import_ray()
    if ray_mod is None:
        return None
    return {
        "EnvWorker": ray_mod.remote(LocalEnvWorker),
        "LoggerWorker": ray_mod.remote(LocalLoggerWorker),
        "Collector": ray_mod.remote(LocalCollector),
    }

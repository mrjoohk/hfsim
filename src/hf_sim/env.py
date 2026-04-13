"""Gymnasium-compatible environment wrapper for HF_Sim.

HFSimEnv wraps the existing IF/UF physics layer into a standard
gymnasium.Env interface suitable for world-model (RSSM/Dreamer) training.

Key design decisions:
- agent_count=1 (single ownship). Multi-agent is a Phase-2 extension.
- n_substeps × dt_internal=0.01 controls the RL time step duration.
  Default: n_substeps=5 → 0.05 s per env step → 1000 steps = 50 s sim time.
- history=[] always — RL mode never accumulates EnvironmentCheckpoints.
- _step_with_flags rebuilds DynamicsStepRequest each substep so that
  event_flags (nonfinite) can be surfaced; real non-finite detection
  comes from ValueError raised by _ensure_finite, not event_flags.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
try:
    import gymnasium
except ModuleNotFoundError:  # pragma: no cover - fallback for lightweight test environments
    from hf_sim.gym_compat import GymnasiumCompat as gymnasium

import importlib

from hf_sim.domain_rand import DomainRandConfig, apply_domain_rand, apply_spawn_jitter
from hf_sim.models import (
    AtmosphereState,
    DynamicsControl,
    DynamicsStepRequest,
    EnvironmentRuntime,
    EnvironmentState,
    ExecutionBundle,
    ExecutionRequest,
    ObservationRequest,
    OwnshipState,
    RadarState,
    SensorState,
    TargetState,
    ThreatState,
)
from hf_sim.noise import NoiseConfig, apply_obs_noise, apply_process_noise
from hf_sim.reward import compute_reward
from hf_sim.termination import TerminationResult, check_termination

# 'if' is a Python keyword — use importlib to load the IF layer modules
_if01 = importlib.import_module("if.if01_orchestration")
_if02 = importlib.import_module("if.if02_dynamics")
_if04 = importlib.import_module("if.if04_observation")

if_01_build_execution_bundle = _if01.if_01_build_execution_bundle
if_02_advance_motion_model_stack = _if02.if_02_advance_motion_model_stack
if_04_build_structured_observation = _if04.if_04_build_structured_observation


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _bundle_to_runtime(
    bundle: ExecutionBundle,
    aero_params: dict[str, float],
    atmosphere: AtmosphereState,
    rng_seed: int,
    dr_config: DomainRandConfig | None,
    np_rng: np.random.Generator,
) -> EnvironmentRuntime:
    """Convert an ExecutionBundle into an initial EnvironmentRuntime.

    IF-01 produces a ScenarioInstance with spawn positions but does not
    construct an EnvironmentRuntime. This bridge function fills that gap.
    Velocity is initialised to [200, 0, 0] m/s matching test fixtures.
    history=[] prevents unbounded memory growth in RL rollouts.
    """
    sc = bundle.scenario_instance
    spawn = list(sc.ownship_spawn[0]) if sc.ownship_spawn else [0.0, 0.0, 1000.0]

    if dr_config is not None:
        spawn = apply_spawn_jitter(spawn, dr_config, np_rng, sc.curriculum_level)

    ownship = OwnshipState(
        position_m=spawn,
        velocity_mps=[200.0, 0.0, 0.0],
        quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
        angular_rate_rps=[0.0, 0.0, 0.0],
        mass_kg=9000.0,
        aero_params=dict(aero_params),
    )

    threats = [
        ThreatState(
            identifier=f"th-{i}",
            position_m=list(pos),
            velocity_mps=[-20.0, 0.0, 0.0],
        )
        for i, pos in enumerate(sc.threat_spawn)
    ]
    targets = [
        TargetState(
            identifier=f"tg-{i}",
            position_m=list(pos),
            velocity_mps=[0.0, 0.0, 0.0],
        )
        for i, pos in enumerate(sc.target_spawn)
    ]
    env_state = EnvironmentState(
        sim_time_s=0.0,
        terrain_reference=list(sc.terrain_heights),
        flags={"agent_count": 1},
    )

    return EnvironmentRuntime(
        ownship=ownship,
        threats=threats,
        targets=targets,
        environment=env_state,
        radar=RadarState(),
        sensor=SensorState(),
        atmosphere=atmosphere,
        rng_state={"seed": rng_seed, "step_index": 0},
        mode_flags={"agent_count": 1},
        dt_internal=0.01,
        calibration_config={},
        history=[],
    )


def _step_with_flags(
    runtime: EnvironmentRuntime,
    control: DynamicsControl,
) -> tuple[EnvironmentRuntime, dict[str, Any]]:
    """Execute one physics substep and return (next_runtime, event_flags).

    Builds DynamicsStepRequest from the current runtime, calls IF-02, then
    reconstructs a clean EnvironmentRuntime with history=[].

    ValueError from _ensure_finite is caught by the caller and converted
    to event_flags["nonfinite"] = True.
    """
    req = DynamicsStepRequest(
        ownship=runtime.ownship,
        threats=runtime.threats,
        targets=runtime.targets,
        environment=runtime.environment,
        control=control,
        dt_internal=runtime.dt_internal,
        agent_count=int(runtime.mode_flags.get("agent_count", 1)),
        radar=runtime.radar,
        sensor=runtime.sensor,
        atmosphere=runtime.atmosphere,
        rng_state=dict(runtime.rng_state),
        mode_flags=dict(runtime.mode_flags),
        calibration_config=dict(runtime.calibration_config),
    )

    result = if_02_advance_motion_model_stack(req)

    next_rng = dict(result.rng_state)
    next_rng["step_index"] = int(next_rng.get("step_index", 0)) + 1

    next_runtime = EnvironmentRuntime(
        ownship=result.ownship,
        threats=result.threats,
        targets=result.targets,
        environment=result.environment,
        radar=result.radar,
        sensor=result.sensor,
        atmosphere=result.atmosphere,
        rng_state=next_rng,
        mode_flags=dict(result.mode_flags),
        dt_internal=runtime.dt_internal,
        calibration_config=dict(runtime.calibration_config),
        history=[],
    )
    return next_runtime, result.event_flags


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _nearest_target_distance(runtime: EnvironmentRuntime) -> float:
    pos = runtime.ownship.position_m
    dists = [
        _distance(pos, t.position_m)
        for t in runtime.targets
        if all(math.isfinite(v) for v in t.position_m)
    ]
    return min(dists) if dists else float("inf")


# ---------------------------------------------------------------------------
# Main environment class
# ---------------------------------------------------------------------------

class HFSimEnv(gymnasium.Env):
    """Gymnasium environment wrapping the HF_Sim physics simulator.

    Observation space: Box([-1, 1]^16, float32)
        16-dim normalised feature vector per agent step:
        vehicle(9) = position(3) + velocity(3) + angular_rate(3)
        terrain(3) = alt_rel_mean, alt_rel_max, max_height
        threat(4)  = dx, dy, dz, distance_to_nearest

    Action space: Box([0,-1,-1,-1,-1], [1,1,1,1,1], float32)
        [throttle, roll_rate, pitch_rate, yaw_rate, load_factor]

    Time step: n_substeps × 0.01 s (default 5 × 0.01 = 0.05 s/step)
    Episode length: max_steps env steps (default 1000 → 50 s sim time)
    """

    metadata: dict[str, Any] = {"render_modes": []}

    def __init__(
        self,
        curriculum_level: int = 0,
        max_steps: int = 1000,
        n_substeps: int = 5,
        seed: int = 0,
        domain_rand_config: DomainRandConfig | None = None,
        noise_config: NoiseConfig | None = None,
        scenario_id: str = "default",
    ) -> None:
        super().__init__()
        self._curriculum_level = int(np.clip(curriculum_level, 0, 10))
        self._max_steps = max_steps
        self._n_substeps = n_substeps
        self._base_seed = seed
        self._dr_config = domain_rand_config
        self._noise_config = noise_config or NoiseConfig()
        self._scenario_id = scenario_id

        self._np_rng = np.random.default_rng(seed)
        self._py_seed = seed
        self._episode_count = 0
        self._step_count = 0
        self._runtime: EnvironmentRuntime | None = None
        self._bundle: ExecutionBundle | None = None
        self._prev_target_dist: float = float("inf")

        low_act = np.array([0.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float32)
        high_act = np.array([1.0,  1.0,  1.0,  1.0,  1.0], dtype=np.float32)
        self.observation_space = gymnasium.spaces.Box(
            low=-1.0, high=1.0, shape=(16,), dtype=np.float32
        )
        self.action_space = gymnasium.spaces.Box(
            low=low_act, high=high_act, dtype=np.float32
        )

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        if seed is not None:
            self._py_seed = seed
            self._np_rng = np.random.default_rng(seed)

        self._episode_count += 1
        self._step_count = 0

        bundle = if_01_build_execution_bundle(
            ExecutionRequest(
                scenario_id=self._scenario_id,
                run_id=f"run-{self._py_seed}-ep{self._episode_count}",
                agent_count=1,
                curriculum_level=self._curriculum_level,
                seed=self._py_seed,
                target_time_acceleration=60.0,
                control_hz=max(1.0, 100.0 / self._n_substeps),
            )
        )
        self._bundle = bundle

        if self._dr_config is not None:
            aero_params, atmosphere = apply_domain_rand(
                bundle, self._dr_config, self._np_rng
            )
        else:
            aero_params = {"drag_coeff": 0.02, "max_thrust_n": 20000.0, "lift_gain": 9.0}
            atmosphere = AtmosphereState()

        self._runtime = _bundle_to_runtime(
            bundle, aero_params, atmosphere, self._py_seed,
            self._dr_config, self._np_rng,
        )
        self._prev_target_dist = _nearest_target_distance(self._runtime)

        obs = self._get_obs()
        info = self._get_info(
            event_flags={"nonfinite": False, "calibration_notes": []},
            reward_components={},
            termination_reason="none",
        )
        return obs, info

    def step(
        self,
        action: np.ndarray,
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._runtime is None or self._bundle is None:
            raise RuntimeError("Call reset() before step()")

        action = np.clip(action, self.action_space.low, self.action_space.high)
        control = DynamicsControl(
            throttle=float(action[0]),
            body_rate_cmd_rps=[float(action[1]), float(action[2]), float(action[3])],
            load_factor_cmd=float(action[4]),
        )

        accum_flags: dict[str, Any] = {"nonfinite": False, "calibration_notes": []}

        for _ in range(self._n_substeps):
            try:
                self._runtime, flags = _step_with_flags(self._runtime, control)
                if self._noise_config.process_noise_scale > 0.0:
                    self._runtime = apply_process_noise(
                        self._runtime, self._noise_config, self._np_rng
                    )
                if flags.get("nonfinite", False):
                    accum_flags["nonfinite"] = True
                    break
                accum_flags["calibration_notes"].extend(
                    flags.get("calibration_notes", [])
                )
            except ValueError:
                accum_flags["nonfinite"] = True
                break

        self._step_count += 1

        obs_raw = self._get_obs()
        if self._noise_config.obs_noise_scale > 0.0:
            obs = apply_obs_noise(obs_raw, self._noise_config, self._np_rng)
        else:
            obs = obs_raw

        term_result: TerminationResult = check_termination(
            self._runtime,
            self._bundle,
            self._step_count,
            self._max_steps,
            accum_flags,
        )
        terminated = term_result.terminated
        truncated = term_result.truncated

        reward, reward_components = compute_reward(
            self._runtime,
            self._bundle,
            terminated,
            truncated,
            term_result.reason,
            self._prev_target_dist,
        )
        self._prev_target_dist = _nearest_target_distance(self._runtime)

        info = self._get_info(accum_flags, reward_components, term_result.reason)
        return obs, reward, terminated, truncated, info

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_obs(self) -> np.ndarray:
        """Build normalised 16-dim observation from current runtime."""
        obs_req = ObservationRequest(
            ownships=[self._runtime.ownship],
            threats=self._runtime.threats,
            environment=self._runtime.environment,
        )
        batch = if_04_build_structured_observation(obs_req)
        arr = np.array(batch.features, dtype=np.float32)  # (1, 16)
        return arr[0]  # (16,) single agent

    def _get_info(
        self,
        event_flags: dict[str, Any],
        reward_components: dict[str, float],
        termination_reason: str,
    ) -> dict[str, Any]:
        rt = self._runtime
        pos = list(rt.ownship.position_m)
        vel = list(rt.ownship.velocity_mps)
        speed = math.sqrt(sum(v * v for v in vel))

        threat_info = []
        for t in rt.threats:
            d = _distance(pos, list(t.position_m)) if all(
                math.isfinite(v) for v in t.position_m
            ) else float("inf")
            threat_info.append({
                "identifier": t.identifier,
                "position_m": list(t.position_m),
                "distance_m": d,
            })

        target_info = []
        for t in rt.targets:
            d = _distance(pos, list(t.position_m)) if all(
                math.isfinite(v) for v in t.position_m
            ) else float("inf")
            target_info.append({
                "identifier": t.identifier,
                "position_m": list(t.position_m),
                "distance_m": d,
            })

        is_done = event_flags.get("nonfinite", False)
        return {
            "sim_time_s": rt.environment.sim_time_s,
            "step_count": self._step_count,
            "episode_count": self._episode_count,
            "curriculum_level": self._curriculum_level,
            "termination_reason": termination_reason,
            # RSSM / Dreamer required field
            "continuation": 0.0 if is_done else 1.0,
            "event_flags": dict(event_flags),
            "reward_components": dict(reward_components),
            "ownship": {
                "position_m": pos,
                "velocity_mps": vel,
                "speed_mps": speed,
            },
            "threats": threat_info,
            "targets": target_info,
            # World-model metadata
            "wm_metadata": {
                "sensor_quality": rt.sensor.quality,
                "step_dt_s": self._n_substeps * rt.dt_internal,
                "threat_distances": [t["distance_m"] for t in threat_info],
            },
        }

    def render(self) -> None:  # type: ignore[override]
        pass

    def close(self) -> None:
        self._runtime = None
        self._bundle = None


# ---------------------------------------------------------------------------
# Convenience wrapper: auto-collects transitions into a SequenceBuffer
# ---------------------------------------------------------------------------

class WorldModelEnvWrapper(gymnasium.Wrapper):
    """Adds RSSM-compatible auto-collection to HFSimEnv.

    On every step(), automatically calls seq_buffer.add_transition() if
    auto_collect=True. The continuation flag (1 - done) is injected into
    info["continuation"] for use by RSSM training loops.
    """

    def __init__(
        self,
        env: HFSimEnv,
        seq_buffer: Any,  # SequenceBuffer — imported lazily to avoid circular dep
        auto_collect: bool = True,
    ) -> None:
        super().__init__(env)
        self._seq_buf = seq_buffer
        self._auto_collect = auto_collect
        self._current_obs: np.ndarray | None = None

    def reset(self, **kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        obs, info = self.env.reset(**kwargs)
        self._current_obs = obs
        return obs, info

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        if self._auto_collect and self._current_obs is not None:
            self._seq_buf.add_transition(
                obs=self._current_obs,
                action=action,
                reward=reward,
                next_obs=obs,
                done=terminated or truncated,
            )
        self._current_obs = obs
        info["continuation"] = 0.0 if (terminated or truncated) else 1.0
        return obs, reward, terminated, truncated, info

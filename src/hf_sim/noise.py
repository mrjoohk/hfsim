"""Stochastic transition and observation noise for world-model training.

Noise is injected externally after step_environment_runtime returns,
before IF-04 builds the observation. This preserves the deterministic
physics kernel (and its _ensure_finite guards) while enabling stochastic
environment semantics for RSSM training.

OwnshipState uses slots=True — always construct new instances.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hf_sim.models import AtmosphereState, EnvironmentRuntime, OwnshipState, RadarState, SensorState


@dataclass
class NoiseConfig:
    """Configuration for process and observation noise.

    Attributes:
        process_noise_scale: Gaussian std dev added to velocity [m/s]
                             and angular rate [rad/s] after each substep.
        obs_noise_scale:     Gaussian std dev added to normalized
                             observation features (space [-1, 1]) before
                             returning obs from step().
    """
    process_noise_scale: float = 0.0
    obs_noise_scale: float = 0.0

    def __post_init__(self) -> None:
        if self.process_noise_scale < 0.0:
            raise ValueError("process_noise_scale must be >= 0")
        if self.process_noise_scale > 5.0:
            raise ValueError(
                "process_noise_scale > 5.0 m/s risks _ensure_finite violation"
            )
        if self.obs_noise_scale < 0.0:
            raise ValueError("obs_noise_scale must be >= 0")


def apply_process_noise(
    runtime: EnvironmentRuntime,
    config: NoiseConfig,
    rng: np.random.Generator,
) -> EnvironmentRuntime:
    """Apply Gaussian process noise to ownship velocity and angular rate.

    Creates a new EnvironmentRuntime (slots=True prevents in-place mutation).
    Angular rate noise is scaled down by 0.1 relative to velocity noise to
    avoid destabilising the quaternion propagation on the next substep.
    """
    if config.process_noise_scale == 0.0:
        return runtime

    vel_noise = rng.normal(0.0, config.process_noise_scale, size=3).tolist()
    ang_noise = (
        rng.normal(0.0, config.process_noise_scale * 0.1, size=3).tolist()
    )

    noisy_ownship = OwnshipState(
        position_m=list(runtime.ownship.position_m),
        velocity_mps=[v + n for v, n in zip(runtime.ownship.velocity_mps, vel_noise)],
        quaternion_wxyz=list(runtime.ownship.quaternion_wxyz),
        angular_rate_rps=[r + n for r, n in zip(runtime.ownship.angular_rate_rps, ang_noise)],
        mass_kg=runtime.ownship.mass_kg,
        aero_params=dict(runtime.ownship.aero_params),
    )

    return EnvironmentRuntime(
        ownship=noisy_ownship,
        threats=runtime.threats,
        targets=runtime.targets,
        environment=runtime.environment,
        radar=runtime.radar,
        sensor=runtime.sensor,
        atmosphere=runtime.atmosphere,
        rng_state=runtime.rng_state,
        mode_flags=runtime.mode_flags,
        dt_internal=runtime.dt_internal,
        calibration_config=runtime.calibration_config,
        history=[],  # never accumulate history in RL mode
    )


def apply_obs_noise(
    obs: np.ndarray,
    config: NoiseConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    """Add Gaussian noise to normalized observation and clip to [-1, 1].

    Operates in normalized observation space (already in [-1, 1]).
    """
    if config.obs_noise_scale == 0.0:
        return obs
    noise = rng.normal(0.0, config.obs_noise_scale, size=obs.shape).astype(np.float32)
    return np.clip(obs + noise, -1.0, 1.0)

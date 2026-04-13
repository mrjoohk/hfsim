"""Domain randomization for HFSimEnv.

Applied at reset() time to aero_params and AtmosphereState.
All variations are curriculum-scaled: at curriculum_level=10 the
full rand_frac is applied; at level 0 no randomization occurs
(unless curriculum_scale != 1.0 overrides this).

Recommended presets by curriculum level:
  Level 0-2  (easy):   DomainRandConfig()  — no randomization
  Level 3-5  (medium): DomainRandConfig(drag_coeff_rand_frac=0.10,
                                         max_thrust_rand_frac=0.10,
                                         lift_gain_rand_frac=0.05,
                                         density_rand_frac=0.05,
                                         wind_max_mps=5.0,
                                         turbulence_max=0.2,
                                         spawn_jitter_m=100.0)
  Level 6-8  (hard):   max_thrust_rand_frac=0.15, density_rand_frac=0.10, …
  Level 9-10 (expert): max values per table in plan
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hf_sim.models import AtmosphereState, ExecutionBundle


@dataclass
class DomainRandConfig:
    """Per-episode randomization configuration.

    All *_rand_frac values express the maximum fractional variation
    (±frac) relative to the nominal value, scaled by curriculum level.

    Example: drag_coeff_rand_frac=0.20 at curriculum_level=5 applies
    ±10% variation (0.20 * 5/10 = 0.10).
    """
    drag_coeff_rand_frac: float = 0.0
    max_thrust_rand_frac: float = 0.0
    lift_gain_rand_frac: float = 0.0
    density_rand_frac: float = 0.0       # ±frac of 1.225 kg/m³
    wind_max_mps: float = 0.0            # uniform [-wind_max, +wind_max] per axis
    turbulence_max: float = 0.0          # uniform [0, turbulence_max]
    spawn_jitter_m: float = 0.0          # uniform [-jitter, +jitter] per axis
    curriculum_scale: float = 1.0        # multiplier on top of level/10 scaling

    def __post_init__(self) -> None:
        for frac_field in (
            self.drag_coeff_rand_frac,
            self.max_thrust_rand_frac,
            self.lift_gain_rand_frac,
            self.density_rand_frac,
        ):
            if frac_field < 0.0:
                raise ValueError("rand_frac values must be >= 0")


# Default nominal aero params (must match synthesize_scenario defaults)
_DEFAULT_AERO = {
    "drag_coeff": 0.02,
    "max_thrust_n": 20000.0,
    "lift_gain": 9.0,
}


def apply_domain_rand(
    bundle: ExecutionBundle,
    config: DomainRandConfig,
    rng: np.random.Generator,
) -> tuple[dict[str, float], AtmosphereState]:
    """Return (aero_params, AtmosphereState) randomized for one episode.

    The curriculum_level from the bundle's scenario_instance is used to
    scale the randomization magnitude: level 0 → no variation,
    level 10 → full variation.

    Returns the nominal values unchanged if config has all zeros.
    """
    lvl = bundle.scenario_instance.curriculum_level
    lvl_scale = (lvl / 10.0) * config.curriculum_scale

    def _rand_frac(base: float, frac: float) -> float:
        if frac == 0.0 or lvl_scale == 0.0:
            return base
        delta = rng.uniform(-frac * lvl_scale, frac * lvl_scale)
        return base * (1.0 + float(delta))

    aero = {
        "drag_coeff": _rand_frac(_DEFAULT_AERO["drag_coeff"], config.drag_coeff_rand_frac),
        "max_thrust_n": _rand_frac(_DEFAULT_AERO["max_thrust_n"], config.max_thrust_rand_frac),
        "lift_gain": _rand_frac(_DEFAULT_AERO["lift_gain"], config.lift_gain_rand_frac),
    }

    # Density: clamp to [0.7, 1.5] to stay within UF density_scale guard
    density = _rand_frac(1.225, config.density_rand_frac)
    density = float(np.clip(density, 0.7, 1.5))

    wind_scale = config.wind_max_mps * lvl_scale
    if wind_scale > 0.0:
        wind = rng.uniform(-wind_scale, wind_scale, size=3).tolist()
    else:
        wind = [0.0, 0.0, 0.0]

    turb_max = config.turbulence_max * lvl_scale
    turbulence = float(rng.uniform(0.0, turb_max)) if turb_max > 0.0 else 0.0

    atmosphere = AtmosphereState(
        density_kgpm3=density,
        wind_vector_mps=wind,
        turbulence_level=turbulence,
    )
    return aero, atmosphere


def apply_spawn_jitter(
    spawn: list[float],
    config: DomainRandConfig,
    rng: np.random.Generator,
    curriculum_level: int,
) -> list[float]:
    """Add uniform jitter to a 3-D spawn position.

    Used inside _bundle_to_runtime for ownship position jitter.
    """
    if config.spawn_jitter_m == 0.0:
        return list(spawn)
    lvl_scale = (curriculum_level / 10.0) * config.curriculum_scale
    jitter_m = config.spawn_jitter_m * lvl_scale
    if jitter_m == 0.0:
        return list(spawn)
    jitter = rng.uniform(-jitter_m, jitter_m, size=3).tolist()
    return [s + j for s, j in zip(spawn, jitter)]

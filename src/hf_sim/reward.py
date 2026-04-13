"""Reward function for HFSimEnv world-model training.

Design goals:
- Dense signal at every timestep (MBRL reward prediction head)
- Decomposed components (analysable per-head)
- Bounded output in [-10.0, +10.22] for stable reward-head training
- Potential-based target shaping (policy-invariant)
"""

from __future__ import annotations

import math

from hf_sim.models import EnvironmentRuntime, ExecutionBundle


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _nearest_threat_distance(runtime: EnvironmentRuntime) -> float:
    """Return distance to nearest threat, or +inf if none."""
    pos = runtime.ownship.position_m
    dists = [
        _distance(pos, t.position_m)
        for t in runtime.threats
        if all(math.isfinite(v) for v in t.position_m)
    ]
    return min(dists) if dists else float("inf")


def _nearest_target_distance(runtime: EnvironmentRuntime) -> float:
    """Return distance to nearest target, or +inf if none."""
    pos = runtime.ownship.position_m
    dists = [
        _distance(pos, t.position_m)
        for t in runtime.targets
        if all(math.isfinite(v) for v in t.position_m)
    ]
    return min(dists) if dists else float("inf")


def compute_reward(
    runtime: EnvironmentRuntime,
    bundle: ExecutionBundle,
    terminated: bool,
    truncated: bool,
    termination_reason: str,
    prev_target_dist: float,
    *,
    w_survival: float = 0.02,
    w_threat: float = 0.05,
    w_target: float = 0.10,
    w_altitude: float = 0.03,
    terminal_penalty: float = -10.0,
    terminal_success: float = 10.0,
    gamma: float = 0.99,
    max_range_m: float = 8000.0,
    safe_altitude_m: float = 500.0,
    terrain_mean_fallback: float = 100.0,
) -> tuple[float, dict[str, float]]:
    """Compute shaped reward with decomposed components.

    Returns (total_reward, components_dict).

    Component breakdown:
    - survival:       +w_survival each alive step
    - threat_shaping: +w_threat * (threat_dist / 6000)  dense avoidance
    - target_shaping: potential-based approach reward (gamma-discounted)
    - altitude:       +w_altitude * clip(alt_agl / safe_altitude_m, 0, 1)
    - terminal:       -10.0 crash/kill  OR  +10.0 success
    """
    components: dict[str, float] = {
        "survival": 0.0,
        "threat_shaping": 0.0,
        "target_shaping": 0.0,
        "altitude_shaping": 0.0,
        "terminal": 0.0,
    }

    # Survival bonus (only on non-terminal steps; terminal step gets penalty instead)
    if not terminated:
        components["survival"] = w_survival

    # Threat distance shaping (dense, non-zero at all distances)
    threat_dist = _nearest_threat_distance(runtime)
    max_detection_m = 6000.0
    if math.isfinite(threat_dist):
        components["threat_shaping"] = w_threat * min(1.0, threat_dist / max_detection_m)

    # Target approach shaping (potential-based: gamma*Phi(s') - Phi(s))
    curr_target_dist = _nearest_target_distance(runtime)
    if math.isfinite(curr_target_dist) and math.isfinite(prev_target_dist):
        phi_prev = -prev_target_dist / max_range_m
        phi_curr = -curr_target_dist / max_range_m
        components["target_shaping"] = w_target * (gamma * phi_curr - phi_prev)

    # Altitude safety shaping
    pos = runtime.ownship.position_m
    terrain = runtime.environment.terrain_reference
    mean_terrain = (
        sum(terrain) / len(terrain) if terrain else terrain_mean_fallback
    )
    alt_agl = pos[2] - mean_terrain
    floor_m = 100.0  # AGL threshold below which shaping = 0
    if alt_agl > floor_m:
        components["altitude_shaping"] = w_altitude * min(
            1.0, (alt_agl - floor_m) / safe_altitude_m
        )

    # Terminal events (applied once, overrides survival)
    if terminated:
        if termination_reason == "success":
            components["terminal"] = terminal_success
            components["survival"] = 0.0  # success replaces survival
        else:
            # crash / kill / nonfinite / ground
            components["terminal"] = terminal_penalty
    # truncated → no terminal signal (value bootstrap handles this)

    total = sum(components.values())
    return total, components

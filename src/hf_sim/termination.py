"""Episode termination logic for HFSimEnv."""

from __future__ import annotations

import math
from dataclasses import dataclass

from hf_sim.models import EnvironmentRuntime, ExecutionBundle


@dataclass
class TerminationResult:
    terminated: bool
    truncated: bool
    reason: str  # "none"|"nonfinite"|"ground"|"threat_kill"|"success"|"max_steps"


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def check_termination(
    runtime: EnvironmentRuntime,
    bundle: ExecutionBundle,
    step_count: int,
    max_steps: int,
    event_flags: dict,
    *,
    kill_radius_m: float = 300.0,
    success_radius_m: float = 200.0,
) -> TerminationResult:
    """Check all termination conditions in priority order.

    Priority: nonfinite → ground → threat_kill → success → max_steps
    Only threat_kill/ground/nonfinite set terminated=True.
    max_steps sets truncated=True (bootstrap with value function in MBRL).
    """
    # 1. Numerical failure (highest priority)
    if event_flags.get("nonfinite", False):
        return TerminationResult(terminated=True, truncated=False, reason="nonfinite")

    pos = runtime.ownship.position_m

    # Guard: if position contains non-finite values, treat as nonfinite
    if not all(math.isfinite(v) for v in pos):
        return TerminationResult(terminated=True, truncated=False, reason="nonfinite")

    # 2. Ground collision
    terrain = runtime.environment.terrain_reference
    if terrain:
        terrain_floor_m = max(terrain) - 50.0
        if pos[2] < terrain_floor_m:
            return TerminationResult(terminated=True, truncated=False, reason="ground")

    # 3. Threat kill zone
    for threat in runtime.threats:
        if all(math.isfinite(v) for v in threat.position_m):
            if _distance(pos, threat.position_m) < kill_radius_m:
                return TerminationResult(terminated=True, truncated=False, reason="threat_kill")

    # 4. Mission success
    for target in runtime.targets:
        if all(math.isfinite(v) for v in target.position_m):
            if _distance(pos, target.position_m) < success_radius_m:
                return TerminationResult(terminated=True, truncated=False, reason="success")

    # 5. Max steps exceeded → truncated (not terminated)
    if step_count >= max_steps:
        return TerminationResult(terminated=False, truncated=True, reason="max_steps")

    return TerminationResult(terminated=False, truncated=False, reason="none")

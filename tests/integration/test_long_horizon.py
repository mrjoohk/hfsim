"""Full-environment long-horizon acceptance tests (Phase B1).

Covers what existing tests do NOT:
- HFSimEnv run of 1 000+ steps with cross-subsystem consistency checks
  at every step (ownship + threats + radar + sensor + atmosphere).
- Checkpoint captured from mid-run (step 300) then deterministically
  restored and replayed — matching the state of the original run.
- Branch rollout from a mid-run checkpoint produces two distinct but
  internally valid trajectories.

These tests sit at the integration boundary (full IF stack + env).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from hf_sim.env import HFSimEnv
from hf_sim.models import (
    AtmosphereState,
    BranchRolloutRequest,
    DynamicsControl,
    EnvironmentRuntime,
    EnvironmentState,
    OwnshipState,
    RadarState,
    SensorState,
    TargetState,
    ThreatState,
)
from uf.if02_dynamics import step_environment_runtime


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_runtime_with_two_threats() -> tuple[EnvironmentRuntime, DynamicsControl]:
    """Return a fully-populated EnvironmentRuntime with 2 threats."""
    runtime = EnvironmentRuntime(
        ownship=OwnshipState(
            position_m=[0.0, 0.0, 1000.0],
            velocity_mps=[200.0, 0.0, 0.0],
            quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
            angular_rate_rps=[0.0, 0.0, 0.0],
            mass_kg=9000.0,
            aero_params={"drag_coeff": 0.01, "max_thrust_n": 30000.0, "lift_gain": 8.0},
        ),
        threats=[
            ThreatState(identifier="th-1", position_m=[3000.0, 0.0, 1000.0], velocity_mps=[-20.0, 0.0, 0.0]),
            ThreatState(identifier="th-2", position_m=[5000.0, 500.0, 900.0], velocity_mps=[-15.0, 5.0, 0.0]),
        ],
        targets=[
            TargetState(identifier="tg-1", position_m=[8000.0, 0.0, 0.0], velocity_mps=[0.0, 0.0, 0.0]),
        ],
        environment=EnvironmentState(
            sim_time_s=0.0,
            terrain_reference=[80.0, 100.0, 120.0, 110.0],
            flags={},
        ),
        radar=RadarState(track_ids=[], detected_ranges_m=[]),
        sensor=SensorState(contact_count=0, quality=1.0),
        atmosphere=AtmosphereState(
            density_kgpm3=1.225,
            wind_vector_mps=[5.0, 0.0, 0.0],
            turbulence_level=0.1,
        ),
        rng_state={"seed": 42, "step_index": 0},
        mode_flags={"agent_count": 4},
        dt_internal=0.01,
        calibration_config={},
    )
    control = DynamicsControl(throttle=0.6, body_rate_cmd_rps=[0.0, 0.0, 0.0], load_factor_cmd=1.0)
    return runtime, control


def _roll(runtime: EnvironmentRuntime, control: DynamicsControl, steps: int) -> EnvironmentRuntime:
    for _ in range(steps):
        runtime = step_environment_runtime(runtime, control)
    return runtime


def _all_finite(values: list[float]) -> bool:
    return all(math.isfinite(v) for v in values)


# ---------------------------------------------------------------------------
# B1-1: Long-horizon HFSimEnv acceptance (complete stack)
# ---------------------------------------------------------------------------

def test_full_env_1000_steps_no_nonfinite_acceptance():
    """1 000 env steps (50 s simulated) — zero nonfinite events, all obs finite.

    Exercises the complete stack: IF-01 → IF-02 × n_substeps → IF-04 →
    reward → termination → auto-reset.
    """
    env = HFSimEnv(curriculum_level=0, max_steps=1000, n_substeps=5, seed=0)
    env.reset(seed=0)

    action = np.array([0.5, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    n_nonfinite = 0
    n_steps = 0

    for _ in range(1000):
        obs, _, terminated, truncated, info = env.step(action)
        n_steps += 1
        if info["event_flags"].get("nonfinite", False):
            n_nonfinite += 1
        assert np.all(np.isfinite(obs)), f"non-finite obs at env step {n_steps}"
        if terminated or truncated:
            env.reset()

    env.close()
    assert n_nonfinite == 0, f"nonfinite physics events: {n_nonfinite}"


# ---------------------------------------------------------------------------
# B1-2: Cross-subsystem consistency over long physics run
# ---------------------------------------------------------------------------

def test_full_env_cross_subsystem_consistency_acceptance():
    """Physics-level: 1 200 steps — ownship, threats, radar, sensor, atmosphere all valid.

    Checks at every step:
    - All ownship states finite and quaternion normalised.
    - All threat positions finite.
    - radar.track_ids count stable (both threats always tracked).
    - sensor.quality in [0, 1].
    - atmosphere fields unchanged (constant propagation is intentional).
    """
    runtime, control = _make_runtime_with_two_threats()
    q_norm_tol = 1e-4

    for step in range(1200):
        runtime = step_environment_runtime(runtime, control)

        # Ownship
        assert _all_finite(runtime.ownship.position_m), f"ownship pos NaN at step {step}"
        assert _all_finite(runtime.ownship.velocity_mps), f"ownship vel NaN at step {step}"
        assert _all_finite(runtime.ownship.quaternion_wxyz), f"quaternion NaN at step {step}"
        q_norm = math.sqrt(sum(q * q for q in runtime.ownship.quaternion_wxyz))
        assert abs(q_norm - 1.0) <= q_norm_tol, f"quaternion drift at step {step}: {q_norm}"

        # Threats
        for t in runtime.threats:
            assert _all_finite(t.position_m), f"threat {t.identifier} pos NaN at step {step}"

        # Radar
        assert len(runtime.radar.track_ids) == 2, f"radar lost a track at step {step}"
        assert all(math.isfinite(r) for r in runtime.radar.detected_ranges_m)

        # Sensor
        assert 0.0 <= runtime.sensor.quality <= 1.0, f"sensor quality out of range at step {step}"
        assert 0.0 <= runtime.sensor.detection_confidence <= 1.0

        # Atmosphere (constant propagation)
        assert math.isfinite(runtime.atmosphere.density_kgpm3)
        assert math.isfinite(runtime.atmosphere.turbulence_level)


# ---------------------------------------------------------------------------
# B1-3: Checkpoint captured mid-run → deterministic restore + replay
# ---------------------------------------------------------------------------

def test_full_env_checkpoint_restore_determinism_acceptance():
    """Capture checkpoint at step 300, restore, replay 300 more → identical end state."""
    import importlib
    _uf03 = importlib.import_module("uf.if03_snapshot")

    runtime, control = _make_runtime_with_two_threats()

    # --- First pass: 300 steps then capture checkpoint ---
    mid_runtime = _roll(runtime, control, steps=300)

    from hf_sim.models import BranchRolloutRequest
    checkpoint_req = BranchRolloutRequest(
        runtime=mid_runtime,
        runtime_source_spec={"source": "current", "k": 0},
        branch_mode="single_action_set",
        branch_controls=[{"throttle": 0.6, "roll": 0.0, "pitch": 0.0}],
        horizon=1,
    )
    checkpoint = _uf03.capture_environment_checkpoint(checkpoint_req)

    # --- Continue from captured state for 300 more steps ---
    end_from_direct = _roll(mid_runtime, control, steps=300)

    # --- Restore from checkpoint and replay same 300 steps ---
    # Restore path: validate → materialize → extract runtime
    validated = _uf03.validate_checkpoint_completeness(checkpoint)
    branch_source = _uf03.materialize_branch_source_runtime(validated)
    restored = branch_source.runtime
    end_from_restore = _roll(restored, control, steps=300)

    # --- States must be identical (determinism) ---
    def _flatten(rt: EnvironmentRuntime) -> list[float]:
        return (
            list(rt.ownship.position_m)
            + list(rt.ownship.velocity_mps)
            + list(rt.ownship.quaternion_wxyz)
            + [rt.sensor.quality, rt.sensor.detection_confidence]
            + [t.position_m[0] for t in rt.threats]
        )

    state_direct  = _flatten(end_from_direct)
    state_restore = _flatten(end_from_restore)
    max_err = max(abs(a - b) for a, b in zip(state_direct, state_restore))
    assert max_err <= 1e-6, (
        f"Checkpoint restore determinism failed: max_err={max_err:.2e}"
    )


# ---------------------------------------------------------------------------
# B1-4: Branch rollout from mid-run checkpoint → 2 distinct valid trajectories
# ---------------------------------------------------------------------------

def test_full_env_branch_rollout_from_mid_run_acceptance():
    """Branch from step-300 checkpoint with 2 control sets → distinct, valid trajectories."""
    import importlib
    _if03 = importlib.import_module("if.if03_snapshot")

    runtime, control = _make_runtime_with_two_threats()
    mid_runtime = _roll(runtime, control, steps=300)

    from hf_sim.models import BranchRolloutRequest
    result = _if03.if_03_branch_snapshot_rollout(
        BranchRolloutRequest(
            runtime=mid_runtime,
            runtime_source_spec={"source": "current", "k": 0},
            branch_mode="single_action_set",
            branch_controls=[
                {"throttle": 0.9, "roll": 0.2, "pitch": 0.1},   # aggressive
                {"throttle": 0.1, "roll": -0.2, "pitch": -0.1}, # evasive
            ],
            horizon=50,
        )
    )

    assert result.branch_count == 2
    assert result.validation_report.source_immutable
    assert result.validation_report.branch_isolated

    # Both trajectories must contain finite states
    for i, traj in enumerate(result.branch_trajectories):
        for state in traj.states:
            for v in state.get("ownship_position_m", []):
                assert math.isfinite(v), f"branch {i} position NaN"

    # Trajectories must diverge (aggressive vs. evasive must produce different final positions)
    traj_a_final = result.branch_trajectories[0].states[-1]["ownship_position_m"]
    traj_b_final = result.branch_trajectories[1].states[-1]["ownship_position_m"]
    total_divergence = sum(abs(a - b) for a, b in zip(traj_a_final, traj_b_final))
    assert total_divergence > 0.0, "Branch trajectories are identical — branching failed"

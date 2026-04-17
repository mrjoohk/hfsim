"""Ownship fidelity gate helpers for deterministic control-response validation."""

from __future__ import annotations

import math

from hf_sim.models import (
    ControlResponseMetrics,
    DynamicsControl,
    EnvironmentRuntime,
    ManeuverDefinition,
)
from uf.if02_dynamics import step_environment_runtime


def _control(
    throttle: float = 0.5,
    roll: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0,
    load_factor: float = 1.0,
) -> DynamicsControl:
    return DynamicsControl(
        throttle=float(throttle),
        body_rate_cmd_rps=[float(roll), float(pitch), float(yaw)],
        load_factor_cmd=float(load_factor),
    )


def _repeated(control: DynamicsControl, steps: int) -> list[DynamicsControl]:
    return [
        DynamicsControl(
            throttle=control.throttle,
            body_rate_cmd_rps=list(control.body_rate_cmd_rps),
            load_factor_cmd=control.load_factor_cmd,
        )
        for _ in range(int(steps))
    ]


def build_standard_maneuver_library() -> list[ManeuverDefinition]:
    """Return deterministic ownship maneuvers used by the fidelity gate."""
    return [
        ManeuverDefinition(
            name="straight_hold",
            description="Baseline hold for finite-state and monotonic-time checks.",
            controls=_repeated(_control(throttle=0.55), 240),
            expected_signal="stability",
        ),
        ManeuverDefinition(
            name="throttle_step",
            description="Throttle step should raise forward speed with bounded drift.",
            controls=_repeated(_control(throttle=0.2), 60) + _repeated(_control(throttle=0.85), 180),
            expected_signal="speed",
        ),
        ManeuverDefinition(
            name="pitch_doublet",
            description="Positive then negative pitch command should excite pitch rate response.",
            controls=(
                _repeated(_control(throttle=0.55), 40)
                + _repeated(_control(throttle=0.55, pitch=0.25), 40)
                + _repeated(_control(throttle=0.55, pitch=-0.25), 40)
                + _repeated(_control(throttle=0.55), 80)
            ),
            expected_signal="pitch_rate",
        ),
        ManeuverDefinition(
            name="roll_doublet",
            description="Positive then negative roll command should excite roll rate response.",
            controls=(
                _repeated(_control(throttle=0.55), 40)
                + _repeated(_control(throttle=0.55, roll=0.25), 40)
                + _repeated(_control(throttle=0.55, roll=-0.25), 40)
                + _repeated(_control(throttle=0.55), 80)
            ),
            expected_signal="roll_rate",
        ),
        ManeuverDefinition(
            name="yaw_pulse",
            description="Short yaw pulse should register in angular-rate channels.",
            controls=(
                _repeated(_control(throttle=0.55), 50)
                + _repeated(_control(throttle=0.55, yaw=0.20), 25)
                + _repeated(_control(throttle=0.55), 125)
            ),
            expected_signal="yaw_rate",
        ),
        ManeuverDefinition(
            name="load_factor_hold",
            description="Sustained load-factor command should move vertical state.",
            controls=(
                _repeated(_control(throttle=0.55), 40)
                + _repeated(_control(throttle=0.55, load_factor=1.8), 100)
                + _repeated(_control(throttle=0.55), 100)
            ),
            expected_signal="altitude",
        ),
        ManeuverDefinition(
            name="coordinated_turn_like",
            description="Combined throttle, roll, pitch, yaw input for multi-axis response.",
            controls=(
                _repeated(_control(throttle=0.60), 30)
                + _repeated(_control(throttle=0.65, roll=0.18, pitch=0.10, yaw=0.08), 120)
                + _repeated(_control(throttle=0.60), 90)
            ),
            expected_signal="multi_axis",
        ),
    ]


def rollout_control_response(
    runtime: EnvironmentRuntime,
    controls: list[DynamicsControl],
) -> list[EnvironmentRuntime]:
    """Roll the runtime forward for a deterministic control schedule."""
    states: list[EnvironmentRuntime] = [runtime]
    current = runtime
    for control in controls:
        current = step_environment_runtime(current, control)
        states.append(current)
    return states


def _vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _all_finite(values: list[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def _extract_signal(runtime: EnvironmentRuntime, expected_signal: str) -> float:
    if expected_signal == "speed":
        return _vector_norm(list(runtime.ownship.velocity_mps))
    if expected_signal == "pitch_rate":
        return float(runtime.ownship.angular_rate_rps[1])
    if expected_signal == "roll_rate":
        return float(runtime.ownship.angular_rate_rps[0])
    if expected_signal == "yaw_rate":
        return float(runtime.ownship.angular_rate_rps[2])
    if expected_signal == "altitude":
        return float(runtime.ownship.position_m[2])
    if expected_signal == "multi_axis":
        return _vector_norm(list(runtime.ownship.angular_rate_rps)) + abs(float(runtime.ownship.position_m[2]))
    return _vector_norm(list(runtime.ownship.velocity_mps))


def summarize_control_response(
    scenario_name: str,
    states: list[EnvironmentRuntime],
    expected_signal: str,
) -> ControlResponseMetrics:
    """Build a compact response summary from a deterministic ownship rollout."""
    if len(states) < 2:
        raise ValueError("at least one propagated state required")

    initial = states[0]
    final = states[-1]
    initial_position = list(initial.ownship.position_m)
    initial_speed = _vector_norm(list(initial.ownship.velocity_mps))
    final_speed = _vector_norm(list(final.ownship.velocity_mps))

    finite_state = True
    monotonic_sim_time = True
    quaternion_norm_error_max = 0.0
    max_position_delta_m = 0.0
    max_speed_mps = initial_speed
    max_abs_angular_rate_rps = 0.0
    signals: list[float] = []
    sim_times: list[float] = []
    energy_like_values: list[float] = []

    for runtime in states:
        ownship_values = (
            list(runtime.ownship.position_m)
            + list(runtime.ownship.velocity_mps)
            + list(runtime.ownship.quaternion_wxyz)
            + list(runtime.ownship.angular_rate_rps)
        )
        finite_state = finite_state and _all_finite(ownship_values)
        speed = _vector_norm(list(runtime.ownship.velocity_mps))
        max_speed_mps = max(max_speed_mps, speed)
        max_abs_angular_rate_rps = max(
            max_abs_angular_rate_rps,
            max(abs(value) for value in runtime.ownship.angular_rate_rps),
        )
        q_norm = _vector_norm(list(runtime.ownship.quaternion_wxyz))
        quaternion_norm_error_max = max(quaternion_norm_error_max, abs(q_norm - 1.0))
        max_position_delta_m = max(
            max_position_delta_m,
            _vector_norm(
                [
                    runtime.ownship.position_m[index] - initial_position[index]
                    for index in range(3)
                ]
            ),
        )
        signals.append(_extract_signal(runtime, expected_signal))
        sim_times.append(float(runtime.environment.sim_time_s))
        energy_like_values.append(0.5 * runtime.ownship.mass_kg * speed * speed)

    monotonic_sim_time = all(
        later >= earlier for earlier, later in zip(sim_times, sim_times[1:])
    )

    baseline_signal = signals[0]
    peak_signal = max(signals)
    response_signal = abs(peak_signal - baseline_signal)
    response_latency_steps = next(
        (index for index, value in enumerate(signals[1:], start=1) if abs(value - baseline_signal) > 1e-6),
        len(signals) - 1,
    )
    overshoot = max(0.0, peak_signal - signals[-1])
    tail = signals[max(1, len(signals) // 5 * 4):]
    steady_state_drift = max(abs(value - tail[0]) for value in tail) if len(tail) > 1 else 0.0
    energy_like_drift = energy_like_values[-1] - energy_like_values[0]

    return ControlResponseMetrics(
        scenario_name=scenario_name,
        n_steps=len(states) - 1,
        response_signal=expected_signal,
        initial_speed_mps=initial_speed,
        final_speed_mps=final_speed,
        max_speed_mps=max_speed_mps,
        max_abs_angular_rate_rps=max_abs_angular_rate_rps,
        max_position_delta_m=max_position_delta_m,
        quaternion_norm_error_max=quaternion_norm_error_max,
        energy_like_drift=energy_like_drift,
        response_latency_steps=response_latency_steps,
        overshoot=overshoot,
        steady_state_drift=steady_state_drift,
        finite_state=finite_state,
        monotonic_sim_time=monotonic_sim_time,
    )


def run_ownship_fidelity_gate(
    runtime: EnvironmentRuntime,
    maneuvers: list[ManeuverDefinition] | None = None,
) -> list[ControlResponseMetrics]:
    """Run the standard control-response pack starting from the same baseline runtime."""
    scenarios = maneuvers or build_standard_maneuver_library()
    reports: list[ControlResponseMetrics] = []
    for maneuver in scenarios:
        trajectory = rollout_control_response(runtime, maneuver.controls)
        reports.append(
            summarize_control_response(
                scenario_name=maneuver.name,
                states=trajectory,
                expected_signal=maneuver.expected_signal,
            )
        )
    return reports

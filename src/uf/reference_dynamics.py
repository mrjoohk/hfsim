"""RK4 reference dynamics model for secondary 6-DoF validation (Phase C1).

Implements the same aerodynamic physics as ``uf.if02_dynamics.propagate_ownship_6dof``
but uses 4th-order Runge-Kutta (RK4) integration instead of Euler 1st-order.

Used as an open-model reference for:
- C1: Secondary validation — Euler vs RK4 position/velocity error metrics
- C3: Calibration case runner — reference trajectory for error reporting

The rotational kinematics (quaternion update) uses the same Euler scheme as the
production code; at dt=0.01 s the quaternion drift is < 1e-6 per step so RK4
would provide no measurable benefit there.
"""

from __future__ import annotations

import math
from typing import Any

from hf_sim.models import (
    AtmosphereState,
    DynamicsControl,
    ManeuverDefinition,
    ManeuverRegressionResult,
    OwnshipState,
    SixDofComparisonResult,
    SixDofRegressionReport,
)


# ---------------------------------------------------------------------------
# Internal helpers — mirror physics from uf.if02_dynamics exactly
# ---------------------------------------------------------------------------

def _normalize_quaternion(q: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in q))
    if norm <= 1e-9:
        raise RuntimeError("quaternion norm collapsed")
    return [v / norm for v in q]


def _vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values))


def _control(
    throttle: float = 0.6,
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


def _compute_accel(
    vel: list[float],
    mass_kg: float,
    aero: dict[str, Any],
    atmosphere: AtmosphereState,
    throttle: float,
    body_rate_cmd: list[float],
    load_factor_cmd: float,
) -> list[float]:
    """Compute translational acceleration from current body velocity.

    Mirrors the physics in ``propagate_ownship_6dof`` exactly so that
    Euler/RK4 differences are purely due to integration order.
    """
    wind = list(atmosphere.wind_vector_mps)
    relative_vel = [vel[i] - wind[i] for i in range(3)]
    airspeed = max(1e-6, _vector_norm(relative_vel))
    density_scale = min(1.5, max(0.5, atmosphere.density_kgpm3 / 1.225))
    turbulence_penalty = max(0.0, atmosphere.turbulence_level) * 0.25

    drag_coeff = float(aero.get("drag_coeff", 0.02))
    max_thrust = float(aero.get("max_thrust_n", 20000.0))
    lift_gain = float(aero.get("lift_gain", 9.0))

    drag_mag = drag_coeff * density_scale * airspeed * airspeed
    ax = (throttle * max_thrust * density_scale - drag_mag) / mass_kg
    ay = body_rate_cmd[0] * lift_gain + 0.02 * wind[1]
    az = (
        -9.81
        + body_rate_cmd[1] * lift_gain * density_scale
        + load_factor_cmd
        - turbulence_penalty
        + 0.02 * wind[2]
    )
    return [ax, ay, az]


def _propagate_quaternion(
    q: list[float],
    angular_rate: list[float],
    body_rate_cmd: list[float],
    dt: float,
) -> list[float]:
    """Euler quaternion kinematics — identical to production code."""
    omega = [0.5 * (angular_rate[i] + body_rate_cmd[i]) for i in range(3)]
    q_dot = [
        -0.5 * (q[1] * omega[0] + q[2] * omega[1] + q[3] * omega[2]),
        0.5 * (q[0] * omega[0] + q[2] * omega[2] - q[3] * omega[1]),
        0.5 * (q[0] * omega[1] - q[1] * omega[2] + q[3] * omega[0]),
        0.5 * (q[0] * omega[2] + q[1] * omega[1] - q[2] * omega[0]),
    ]
    return _normalize_quaternion([q[i] + q_dot[i] * dt for i in range(4)])


# ---------------------------------------------------------------------------
# Euler reference (mirrors production propagate_ownship_6dof)
# ---------------------------------------------------------------------------

def propagate_ownship_euler(
    ownship: OwnshipState,
    control: DynamicsControl,
    atmosphere: AtmosphereState,
    dt: float,
) -> OwnshipState:
    """1st-order Euler propagation — mirrors ``propagate_ownship_6dof`` exactly.

    Provided so the calibration workflow can run both methods through the same
    interface without importing the production UF layer.
    """
    throttle = min(1.0, max(0.0, control.throttle))
    body_rate_cmd = [min(1.0, max(-1.0, v)) for v in control.body_rate_cmd_rps]

    accel = _compute_accel(
        ownship.velocity_mps,
        ownship.mass_kg,
        ownship.aero_params,
        atmosphere,
        throttle,
        body_rate_cmd,
        control.load_factor_cmd,
    )
    wind = list(atmosphere.wind_vector_mps)

    vel_next = [ownship.velocity_mps[i] + accel[i] * dt for i in range(3)]
    ground_vel = [vel_next[i] + wind[i] for i in range(3)]
    pos_next = [ownship.position_m[i] + ground_vel[i] * dt for i in range(3)]
    quat_next = _propagate_quaternion(
        list(ownship.quaternion_wxyz),
        list(ownship.angular_rate_rps),
        body_rate_cmd,
        dt,
    )
    omega_next = [0.5 * (ownship.angular_rate_rps[i] + body_rate_cmd[i]) for i in range(3)]

    return OwnshipState(
        position_m=pos_next,
        velocity_mps=vel_next,
        quaternion_wxyz=quat_next,
        angular_rate_rps=omega_next,
        mass_kg=ownship.mass_kg,
        aero_params=dict(ownship.aero_params),
    )


# ---------------------------------------------------------------------------
# RK4 reference
# ---------------------------------------------------------------------------

def propagate_ownship_rk4(
    ownship: OwnshipState,
    control: DynamicsControl,
    atmosphere: AtmosphereState,
    dt: float,
) -> OwnshipState:
    """4th-order Runge-Kutta translational propagation.

    Translational state (position, body velocity) is integrated with RK4.
    Rotational kinematics (quaternion) use the same Euler scheme as production
    — at dt ≤ 0.01 s, quaternion drift difference between Euler/RK4 is < 1e-6.

    Args:
        ownship:    Current ownship state.
        control:    Control input for this step.
        atmosphere: Atmosphere state (treated as constant over the step).
        dt:         Integration time step in seconds.

    Returns:
        Next OwnshipState with RK4-integrated position and velocity.
    """
    throttle = min(1.0, max(0.0, control.throttle))
    body_rate_cmd = [min(1.0, max(-1.0, v)) for v in control.body_rate_cmd_rps]
    wind = list(atmosphere.wind_vector_mps)
    vel = list(ownship.velocity_mps)
    pos = list(ownship.position_m)

    def accel(v: list[float]) -> list[float]:
        return _compute_accel(
            v,
            ownship.mass_kg,
            ownship.aero_params,
            atmosphere,
            throttle,
            body_rate_cmd,
            control.load_factor_cmd,
        )

    # RK4 stages  (state = (pos, body_vel);  d(pos)/dt = body_vel + wind)
    k1_acc = accel(vel)
    k1_vel = vel

    k2_v = [vel[i] + 0.5 * dt * k1_acc[i] for i in range(3)]
    k2_acc = accel(k2_v)
    k2_vel = k2_v

    k3_v = [vel[i] + 0.5 * dt * k2_acc[i] for i in range(3)]
    k3_acc = accel(k3_v)
    k3_vel = k3_v

    k4_v = [vel[i] + dt * k3_acc[i] for i in range(3)]
    k4_acc = accel(k4_v)
    k4_vel = k4_v

    vel_next = [
        vel[i] + (dt / 6.0) * (k1_acc[i] + 2 * k2_acc[i] + 2 * k3_acc[i] + k4_acc[i])
        for i in range(3)
    ]
    # Ground velocity: body_velocity + wind (averaged via RK4 stages)
    pos_next = [
        pos[i] + (dt / 6.0) * (
            (k1_vel[i] + wind[i])
            + 2 * (k2_vel[i] + wind[i])
            + 2 * (k3_vel[i] + wind[i])
            + (k4_vel[i] + wind[i])
        )
        for i in range(3)
    ]

    quat_next = _propagate_quaternion(
        list(ownship.quaternion_wxyz),
        list(ownship.angular_rate_rps),
        body_rate_cmd,
        dt,
    )
    omega_next = [0.5 * (ownship.angular_rate_rps[i] + body_rate_cmd[i]) for i in range(3)]

    return OwnshipState(
        position_m=pos_next,
        velocity_mps=vel_next,
        quaternion_wxyz=quat_next,
        angular_rate_rps=omega_next,
        mass_kg=ownship.mass_kg,
        aero_params=dict(ownship.aero_params),
    )


# ---------------------------------------------------------------------------
# Comparison functions
# ---------------------------------------------------------------------------

def compare_6dof_euler_vs_rk4(
    ownship: OwnshipState,
    control: DynamicsControl,
    atmosphere: AtmosphereState,
    dt: float,
    step: int = 0,
) -> SixDofComparisonResult:
    """Single-step Euler vs RK4 comparison returning position/velocity errors.

    Args:
        ownship:    Initial ownship state for this step.
        control:    Control input applied for both methods.
        atmosphere: Atmosphere state.
        dt:         Integration time step.
        step:       Step index label embedded in result.

    Returns:
        :class:`SixDofComparisonResult` with position_error_m and velocity_error_mps.
    """
    euler_state = propagate_ownship_euler(ownship, control, atmosphere, dt)
    rk4_state = propagate_ownship_rk4(ownship, control, atmosphere, dt)

    pos_err = _vector_norm([
        euler_state.position_m[i] - rk4_state.position_m[i] for i in range(3)
    ])
    vel_err = _vector_norm([
        euler_state.velocity_mps[i] - rk4_state.velocity_mps[i] for i in range(3)
    ])

    return SixDofComparisonResult(
        step=step,
        position_error_m=pos_err,
        velocity_error_mps=vel_err,
        euler_position_m=list(euler_state.position_m),
        rk4_position_m=list(rk4_state.position_m),
    )


def build_standard_maneuver_library() -> list[ManeuverDefinition]:
    """Return deterministic control schedules used for trajectory regression."""
    return [
        ManeuverDefinition(
            name="straight_hold",
            description="Steady throttle hold for baseline drift checks.",
            controls=_repeated(_control(throttle=0.6), 240),
            expected_signal="stability",
        ),
        ManeuverDefinition(
            name="throttle_step",
            description="Low-to-high throttle transition for forward-axis response.",
            controls=_repeated(_control(throttle=0.2), 60) + _repeated(_control(throttle=0.85), 180),
            expected_signal="speed",
        ),
        ManeuverDefinition(
            name="pitch_doublet",
            description="Positive then negative pitch command.",
            controls=(
                _repeated(_control(throttle=0.6), 40)
                + _repeated(_control(throttle=0.6, pitch=0.25), 40)
                + _repeated(_control(throttle=0.6, pitch=-0.25), 40)
                + _repeated(_control(throttle=0.6), 80)
            ),
            expected_signal="pitch_rate",
        ),
        ManeuverDefinition(
            name="roll_doublet",
            description="Positive then negative roll command.",
            controls=(
                _repeated(_control(throttle=0.6), 40)
                + _repeated(_control(throttle=0.6, roll=0.25), 40)
                + _repeated(_control(throttle=0.6, roll=-0.25), 40)
                + _repeated(_control(throttle=0.6), 80)
            ),
            expected_signal="roll_rate",
        ),
        ManeuverDefinition(
            name="coordinated_turn_like",
            description="Coupled roll, pitch, yaw, and throttle input.",
            controls=(
                _repeated(_control(throttle=0.6), 30)
                + _repeated(_control(throttle=0.65, roll=0.18, pitch=0.10, yaw=0.08), 120)
                + _repeated(_control(throttle=0.6), 90)
            ),
            expected_signal="multi_axis",
        ),
    ]


def run_6dof_comparison_trajectory(
    initial_ownship: OwnshipState,
    controls: list[DynamicsControl],
    atmosphere: AtmosphereState,
    dt: float,
) -> list[SixDofComparisonResult]:
    """Run N-step trajectory comparison between Euler and RK4.

    Both methods start from the same initial state and each step uses the
    same control input.  The returned list has one entry per control step.

    Args:
        initial_ownship: Starting ownship state.
        controls:        List of per-step control inputs (length = N).
        atmosphere:      Atmosphere state (constant over the trajectory).
        dt:              Integration time step in seconds.

    Returns:
        List of :class:`SixDofComparisonResult` of length ``len(controls)``.
    """
    results: list[SixDofComparisonResult] = []
    euler_state = initial_ownship
    rk4_state = initial_ownship

    for step_idx, control in enumerate(controls):
        euler_next = propagate_ownship_euler(euler_state, control, atmosphere, dt)
        rk4_next = propagate_ownship_rk4(rk4_state, control, atmosphere, dt)

        pos_err = _vector_norm([
            euler_next.position_m[i] - rk4_next.position_m[i] for i in range(3)
        ])
        vel_err = _vector_norm([
            euler_next.velocity_mps[i] - rk4_next.velocity_mps[i] for i in range(3)
        ])

        results.append(SixDofComparisonResult(
            step=step_idx,
            position_error_m=pos_err,
            velocity_error_mps=vel_err,
            euler_position_m=list(euler_next.position_m),
            rk4_position_m=list(rk4_next.position_m),
        ))

        euler_state = euler_next
        rk4_state = rk4_next

    return results


def summarize_maneuver_regression(
    maneuver_name: str,
    results: list[SixDofComparisonResult],
) -> ManeuverRegressionResult:
    """Summarize one trajectory regression into bounded mean/peak metrics."""
    if not results:
        raise ValueError("comparison results required")

    mean_position_error = sum(result.position_error_m for result in results) / len(results)
    mean_velocity_error = sum(result.velocity_error_mps for result in results) / len(results)
    peak_position_error = max(result.position_error_m for result in results)
    peak_velocity_error = max(result.velocity_error_mps for result in results)
    final_result = results[-1]

    return ManeuverRegressionResult(
        maneuver_name=maneuver_name,
        mean_position_error_m=mean_position_error,
        peak_position_error_m=peak_position_error,
        mean_velocity_error_mps=mean_velocity_error,
        peak_velocity_error_mps=peak_velocity_error,
        final_position_error_m=final_result.position_error_m,
        final_velocity_error_mps=final_result.velocity_error_mps,
    )


def run_maneuver_regression_suite(
    initial_ownship: OwnshipState,
    atmosphere: AtmosphereState,
    dt: float,
    maneuvers: list[ManeuverDefinition] | None = None,
) -> SixDofRegressionReport:
    """Run the standard Euler-vs-RK4 regression suite over named maneuvers."""
    scenario_library = maneuvers or build_standard_maneuver_library()
    scenario_results = [
        summarize_maneuver_regression(
            maneuver.name,
            run_6dof_comparison_trajectory(initial_ownship, maneuver.controls, atmosphere, dt),
        )
        for maneuver in scenario_library
    ]
    return SixDofRegressionReport(
        dt=float(dt),
        scenario_count=len(scenario_results),
        scenario_results=scenario_results,
    )

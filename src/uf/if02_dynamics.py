"""UF implementations for IF-02 dynamics."""

from __future__ import annotations

import math

from hf_sim.models import (
    AeroCalibrationContext,
    AtmosphereState,
    DynamicsControl,
    DynamicsStepRequest,
    DynamicsStepResult,
    EntityStateSet,
    EnvironmentRuntime,
    EnvironmentPropagationContext,
    EnvironmentState,
    OwnshipPropagationContext,
    OwnshipState,
    RadarState,
    SensorState,
    TargetState,
    ThreatPropagationContext,
    ThreatState,
)


def _ensure_finite(values: list[float], label: str) -> None:
    if any((not math.isfinite(v)) for v in values):
        raise ValueError(f"non-finite {label} detected")


def _normalize_quaternion(quaternion: list[float]) -> list[float]:
    norm = math.sqrt(sum(q * q for q in quaternion))
    if norm <= 1e-9:
        raise RuntimeError("quaternion norm collapsed")
    return [q / norm for q in quaternion]


def _vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def compute_atmosphere_adjustment(ownship: OwnshipState, atmosphere: AtmosphereState) -> dict[str, float | list[float]]:
    """Compute deterministic atmosphere adjustments for flight and sensing."""
    wind_vector = list(atmosphere.wind_vector_mps)
    relative_air_velocity = [ownship.velocity_mps[idx] - wind_vector[idx] for idx in range(3)]
    density_scale = min(1.5, max(0.5, atmosphere.density_kgpm3 / 1.225))
    return {
        "density_scale": density_scale,
        "relative_air_velocity": relative_air_velocity,
        "airspeed_mps": max(1e-6, _vector_norm(relative_air_velocity)),
        "wind_speed_mps": _vector_norm(wind_vector),
        "turbulence_penalty": max(0.0, atmosphere.turbulence_level) * 0.25,
    }


def update_sensor_state(
    ownship: OwnshipState,
    threats: list[ThreatState],
    atmosphere: AtmosphereState,
    radar: RadarState,
    previous_sensor: SensorState,
) -> SensorState:
    """Update lightweight sensor quality using geometry and atmosphere."""
    adjustment = compute_atmosphere_adjustment(ownship, atmosphere)
    quality = 1.0
    quality -= 0.15 * atmosphere.turbulence_level
    quality -= 0.01 * float(adjustment["wind_speed_mps"])
    quality -= 0.25 * abs(float(adjustment["density_scale"]) - 1.0)
    quality = min(1.0, max(0.0, quality))

    detection_range_m = 6000.0 * (0.5 + 0.5 * quality)
    max_confidence = 0.0
    contact_count = 0
    for threat in threats:
        distance = math.sqrt(sum((threat.position_m[idx] - ownship.position_m[idx]) ** 2 for idx in range(3)))
        confidence = quality * max(0.0, 1.0 - distance / max(1.0, detection_range_m))
        max_confidence = max(max_confidence, confidence)
        if confidence >= 0.1:
            contact_count += 1

    return SensorState(
        contact_count=contact_count,
        quality=quality,
        mode=previous_sensor.mode,
        detection_confidence=max_confidence,
    )


def decode_state_bundle(dynamics_step_request: DynamicsStepRequest) -> EntityStateSet:
    """Decode a step request into typed entity states."""
    if dynamics_step_request is None:
        raise ValueError("dynamics_step_request cannot be None")
    if not (0.0005 < dynamics_step_request.dt_internal <= 0.02):
        raise ValueError(f"invalid dt_internal: {dynamics_step_request.dt_internal}")

    _ensure_finite(dynamics_step_request.ownship.position_m, "ownship position")
    _ensure_finite(dynamics_step_request.ownship.velocity_mps, "ownship velocity")

    return EntityStateSet(
        ownship=dynamics_step_request.ownship,
        threats=dynamics_step_request.threats,
        targets=dynamics_step_request.targets,
        environment=dynamics_step_request.environment,
        radar=dynamics_step_request.radar,
        sensor=dynamics_step_request.sensor,
        atmosphere=dynamics_step_request.atmosphere,
        control=dynamics_step_request.control,
        dt_internal=dynamics_step_request.dt_internal,
        agent_count=dynamics_step_request.agent_count,
        rng_state=dict(dynamics_step_request.rng_state),
        mode_flags=dict(dynamics_step_request.mode_flags),
        calibration_config=dynamics_step_request.calibration_config,
    )


def propagate_ownship_6dof(entity_states: EntityStateSet) -> OwnshipPropagationContext:
    """Propagate a simplified 6-DoF ownship state."""
    aero = entity_states.ownship.aero_params
    if not aero:
        raise ValueError("aero parameters required")

    control = entity_states.control
    throttle = min(1.0, max(0.0, control.throttle))
    body_rate_cmd = [min(1.0, max(-1.0, value)) for value in control.body_rate_cmd_rps]
    dt = entity_states.dt_internal
    ownship = entity_states.ownship

    vx, vy, vz = ownship.velocity_mps
    adjustment = compute_atmosphere_adjustment(ownship, entity_states.atmosphere)
    airspeed = float(adjustment["airspeed_mps"])
    density_scale = float(adjustment["density_scale"])
    wind_vector = list(adjustment["relative_air_velocity"])
    ambient_wind = list(entity_states.atmosphere.wind_vector_mps)
    drag_coeff = aero.get("drag_coeff", 0.02)
    max_thrust = aero.get("max_thrust_n", 20000.0)
    lift_gain = aero.get("lift_gain", 9.0)

    drag_mag = drag_coeff * density_scale * airspeed * airspeed
    thrust_ax = (throttle * max_thrust * density_scale - drag_mag) / ownship.mass_kg
    ay = body_rate_cmd[0] * lift_gain + 0.02 * ambient_wind[1]
    az = -9.81 + body_rate_cmd[1] * lift_gain * density_scale + control.load_factor_cmd - float(adjustment["turbulence_penalty"]) + 0.02 * ambient_wind[2]

    velocity_next = [
        vx + thrust_ax * dt,
        vy + ay * dt,
        vz + az * dt,
    ]
    ground_velocity = [
        velocity_next[0] + ambient_wind[0],
        velocity_next[1] + ambient_wind[1],
        velocity_next[2] + ambient_wind[2],
    ]
    position_next = [
        ownship.position_m[0] + ground_velocity[0] * dt,
        ownship.position_m[1] + ground_velocity[1] * dt,
        ownship.position_m[2] + ground_velocity[2] * dt,
    ]

    omega = [0.5 * (ownship.angular_rate_rps[idx] + body_rate_cmd[idx]) for idx in range(3)]
    q = ownship.quaternion_wxyz
    q_dot = [
        -0.5 * (q[1] * omega[0] + q[2] * omega[1] + q[3] * omega[2]),
        0.5 * (q[0] * omega[0] + q[2] * omega[2] - q[3] * omega[1]),
        0.5 * (q[0] * omega[1] - q[1] * omega[2] + q[3] * omega[0]),
        0.5 * (q[0] * omega[2] + q[1] * omega[1] - q[2] * omega[0]),
    ]
    quaternion_next = _normalize_quaternion([q[idx] + q_dot[idx] * dt for idx in range(4)])

    ownship_next = OwnshipState(
        position_m=position_next,
        velocity_mps=velocity_next,
        quaternion_wxyz=quaternion_next,
        angular_rate_rps=omega,
        mass_kg=ownship.mass_kg,
        aero_params=dict(ownship.aero_params),
    )

    return OwnshipPropagationContext(
        ownship_next=ownship_next,
        threats=entity_states.threats,
        targets=entity_states.targets,
        environment=entity_states.environment,
        radar=entity_states.radar,
        sensor=entity_states.sensor,
        atmosphere=entity_states.atmosphere,
        dt_internal=dt,
        rng_state=dict(entity_states.rng_state),
        mode_flags=dict(entity_states.mode_flags),
        calibration_config=entity_states.calibration_config,
    )


def propagate_threat_kinematics(ownship_propagation_context: OwnshipPropagationContext) -> ThreatPropagationContext:
    """Propagate active threat kinematics."""
    threats_next: list[ThreatState] = []
    for threat in ownship_propagation_context.threats:
        if threat.model_id != "constant_velocity":
            raise NotImplementedError("unsupported threat model")
        speed_components = [max(0.0, v) if idx == 0 and v < 0 else v for idx, v in enumerate(threat.velocity_mps)]
        threats_next.append(
            ThreatState(
                identifier=threat.identifier,
                position_m=[threat.position_m[idx] + speed_components[idx] * ownship_propagation_context.dt_internal for idx in range(3)],
                velocity_mps=speed_components,
                model_id=threat.model_id,
            )
        )

    return ThreatPropagationContext(
        ownship_next=ownship_propagation_context.ownship_next,
        threats_next=threats_next,
        targets=ownship_propagation_context.targets,
        environment=ownship_propagation_context.environment,
        radar=ownship_propagation_context.radar,
        sensor=ownship_propagation_context.sensor,
        atmosphere=ownship_propagation_context.atmosphere,
        dt_internal=ownship_propagation_context.dt_internal,
        rng_state=dict(ownship_propagation_context.rng_state),
        mode_flags=dict(ownship_propagation_context.mode_flags),
        calibration_config=ownship_propagation_context.calibration_config,
    )


def propagate_target_environment(threat_propagation_context: ThreatPropagationContext) -> EnvironmentPropagationContext:
    """Propagate target and environment state."""
    environment = threat_propagation_context.environment
    if not environment.terrain_reference:
        raise ValueError("terrain reference required")

    targets_next = [
        TargetState(
            identifier=target.identifier,
            position_m=[target.position_m[idx] + target.velocity_mps[idx] * threat_propagation_context.dt_internal for idx in range(3)],
            velocity_mps=list(target.velocity_mps),
        )
        for target in threat_propagation_context.targets
    ]
    environment_next = EnvironmentState(
        sim_time_s=environment.sim_time_s + threat_propagation_context.dt_internal,
        terrain_reference=list(environment.terrain_reference),
        flags=dict(environment.flags),
    )
    environment_next.flags["agent_count"] = len(threat_propagation_context.threats_next) + 1
    radar_next = RadarState(
        track_ids=[threat.identifier for threat in threat_propagation_context.threats_next],
        detected_ranges_m=[
            math.sqrt(
                sum(
                    (threat.position_m[idx] - threat_propagation_context.ownship_next.position_m[idx]) ** 2
                    for idx in range(3)
                )
            )
            for threat in threat_propagation_context.threats_next
        ],
        mode=threat_propagation_context.radar.mode,
    )
    sensor_next = update_sensor_state(
        threat_propagation_context.ownship_next,
        threat_propagation_context.threats_next,
        threat_propagation_context.atmosphere,
        radar_next,
        threat_propagation_context.sensor,
    )
    atmosphere_next = AtmosphereState(
        density_kgpm3=threat_propagation_context.atmosphere.density_kgpm3,
        wind_vector_mps=list(threat_propagation_context.atmosphere.wind_vector_mps),
        turbulence_level=threat_propagation_context.atmosphere.turbulence_level,
    )

    return EnvironmentPropagationContext(
        ownship_next=threat_propagation_context.ownship_next,
        threats_next=threat_propagation_context.threats_next,
        targets_next=targets_next,
        environment_next=environment_next,
        radar_next=radar_next,
        sensor_next=sensor_next,
        atmosphere_next=atmosphere_next,
        dt_internal=threat_propagation_context.dt_internal,
        rng_state=dict(threat_propagation_context.rng_state),
        mode_flags=dict(threat_propagation_context.mode_flags),
        calibration_config=threat_propagation_context.calibration_config,
    )


def apply_aero_calibration(environment_propagation_context: EnvironmentPropagationContext) -> AeroCalibrationContext:
    """Apply aerodynamic calibration overrides."""
    ownship = environment_propagation_context.ownship_next
    calibration = environment_propagation_context.calibration_config
    notes: list[str] = []
    if not calibration:
        notes.append("calibration_passthrough")
        return AeroCalibrationContext(
            ownship_next=ownship,
            threats_next=environment_propagation_context.threats_next,
            targets_next=environment_propagation_context.targets_next,
            environment_next=environment_propagation_context.environment_next,
            radar_next=environment_propagation_context.radar_next,
            sensor_next=environment_propagation_context.sensor_next,
            atmosphere_next=environment_propagation_context.atmosphere_next,
            rng_state=dict(environment_propagation_context.rng_state),
            mode_flags=dict(environment_propagation_context.mode_flags),
            calibration_notes=notes,
        )

    speed_scale = float(calibration.get("velocity_scale", 1.0))
    ownship_next = OwnshipState(
        position_m=list(ownship.position_m),
        velocity_mps=[component * speed_scale for component in ownship.velocity_mps],
        quaternion_wxyz=_normalize_quaternion(list(ownship.quaternion_wxyz)),
        angular_rate_rps=list(ownship.angular_rate_rps),
        mass_kg=ownship.mass_kg,
        aero_params={**ownship.aero_params, **calibration.get("coefficient_overrides", {})},
    )
    _ensure_finite(ownship_next.velocity_mps, "calibrated ownship")
    notes.append("calibration_applied")

    return AeroCalibrationContext(
        ownship_next=ownship_next,
        threats_next=environment_propagation_context.threats_next,
        targets_next=environment_propagation_context.targets_next,
        environment_next=environment_propagation_context.environment_next,
        radar_next=environment_propagation_context.radar_next,
        sensor_next=environment_propagation_context.sensor_next,
        atmosphere_next=environment_propagation_context.atmosphere_next,
        rng_state=dict(environment_propagation_context.rng_state),
        mode_flags=dict(environment_propagation_context.mode_flags),
        calibration_notes=notes,
    )


def compose_step_result(aero_calibration_context: AeroCalibrationContext) -> DynamicsStepResult:
    """Compose the next-step dynamics result."""
    if aero_calibration_context.threats_next is None:
        raise RuntimeError("threat_state_next missing")
    if aero_calibration_context.environment_next is None:
        raise RuntimeError("environment_state_next missing")

    return DynamicsStepResult(
        ownship=aero_calibration_context.ownship_next,
        threats=aero_calibration_context.threats_next,
        targets=aero_calibration_context.targets_next,
        environment=aero_calibration_context.environment_next,
        radar=aero_calibration_context.radar_next,
        sensor=aero_calibration_context.sensor_next,
        atmosphere=aero_calibration_context.atmosphere_next,
        rng_state=dict(aero_calibration_context.rng_state),
        mode_flags=dict(aero_calibration_context.mode_flags),
        event_flags={
            "calibration_notes": list(aero_calibration_context.calibration_notes),
            "nonfinite": False,
        },
    )


def step_environment_runtime(runtime: EnvironmentRuntime, control: DynamicsControl) -> EnvironmentRuntime:
    """Advance the full environment runtime by one internal step."""
    result = compose_step_result(
        apply_aero_calibration(
            propagate_target_environment(
                propagate_threat_kinematics(
                    propagate_ownship_6dof(
                        decode_state_bundle(
                            DynamicsStepRequest(
                                ownship=runtime.ownship,
                                threats=runtime.threats,
                                targets=runtime.targets,
                                environment=runtime.environment,
                                radar=runtime.radar,
                                sensor=runtime.sensor,
                                atmosphere=runtime.atmosphere,
                                control=control,
                                dt_internal=runtime.dt_internal,
                                agent_count=max(1, runtime.mode_flags.get("agent_count", len(runtime.threats) + 1)),
                                rng_state=runtime.rng_state,
                                mode_flags=runtime.mode_flags,
                                calibration_config=runtime.calibration_config,
                            )
                        )
                    )
                )
            )
        )
    )
    next_rng_state = dict(result.rng_state)
    next_rng_state["step_index"] = int(next_rng_state.get("step_index", runtime.rng_state.get("step_index", 0))) + 1
    next_mode_flags = dict(result.mode_flags)
    next_mode_flags["agent_count"] = max(1, runtime.mode_flags.get("agent_count", len(runtime.threats) + 1))
    return EnvironmentRuntime(
        ownship=result.ownship,
        threats=result.threats,
        targets=result.targets,
        environment=result.environment,
        radar=result.radar,
        sensor=result.sensor,
        atmosphere=result.atmosphere,
        rng_state=next_rng_state,
        mode_flags=next_mode_flags,
        dt_internal=runtime.dt_internal,
        calibration_config=dict(runtime.calibration_config),
        history=list(runtime.history),
    )

"""IF-02 integration module."""

from __future__ import annotations

from hf_sim.models import DynamicsStepRequest, DynamicsStepResult
from uf.if02_dynamics import (
    apply_aero_calibration,
    compose_step_result,
    decode_state_bundle,
    propagate_ownship_6dof,
    propagate_target_environment,
    propagate_threat_kinematics,
)


def if_02_advance_motion_model_stack(dynamics_step_request: DynamicsStepRequest) -> DynamicsStepResult:
    """Advance the full active motion-model stack for the mission environment."""
    entity_states = decode_state_bundle(dynamics_step_request)
    ownship_context = propagate_ownship_6dof(entity_states)
    threat_context = propagate_threat_kinematics(ownship_context)
    environment_context = propagate_target_environment(threat_context)
    calibration_context = apply_aero_calibration(environment_context)
    return compose_step_result(calibration_context)


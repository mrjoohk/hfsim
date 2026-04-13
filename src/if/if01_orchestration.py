"""IF-01 integration module."""

from __future__ import annotations

from hf_sim.errors import IntegrationError
from hf_sim.models import ExecutionBundle, ExecutionRequest
from uf.if01_orchestration import (
    assemble_execution_bundle,
    finalize_execution_bundle,
    inspect_hardware_profile,
    parse_execution_config,
    size_rollout_batch,
    synthesize_scenario,
)


def if_01_build_execution_bundle(execution_request: ExecutionRequest) -> ExecutionBundle:
    """Build learnability-first scenarios and hardware-adaptive rollout plans."""
    normalized_request = parse_execution_config(execution_request)
    hardware_context = inspect_hardware_profile(normalized_request)
    scenario_context = synthesize_scenario(hardware_context)
    sizing_context = size_rollout_batch(scenario_context)
    partial_bundle = assemble_execution_bundle(sizing_context)
    result = finalize_execution_bundle(partial_bundle)
    if result.rollout_plan.estimated_time_acceleration < 60.0:
        raise IntegrationError("IF-01 requires at least 60x estimated time acceleration")
    return result


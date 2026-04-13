from hf_sim.models import ExecutionRequest
from uf.if01_orchestration import (
    assemble_execution_bundle,
    finalize_execution_bundle,
    inspect_hardware_profile,
    parse_execution_config,
    size_rollout_batch,
    synthesize_scenario,
)


def test_if01_uf_chain_builds_60x_bundle():
    request = ExecutionRequest(scenario_id="scenario-a", run_id="run-a", agent_count=4, target_time_acceleration=60.0)
    normalized = parse_execution_config(request)
    hardware = inspect_hardware_profile(normalized)
    scenario = synthesize_scenario(hardware)
    sizing = size_rollout_batch(scenario)
    partial = assemble_execution_bundle(sizing)
    bundle = finalize_execution_bundle(partial)
    assert bundle.rollout_plan.estimated_time_acceleration >= 60.0
    assert bundle.agent_count == 4


def test_parse_execution_config_none_raises():
    import pytest

    with pytest.raises(ValueError):
        parse_execution_config(None)


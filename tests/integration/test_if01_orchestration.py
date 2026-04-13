import importlib

from hf_sim.models import ExecutionRequest


def test_if01_execution_bundle_acceptance():
    module = importlib.import_module("if.if01_orchestration")
    result = module.if_01_build_execution_bundle(
        ExecutionRequest(scenario_id="scenario-int-1", run_id="run-int-1", agent_count=4, target_time_acceleration=60.0)
    )
    assert result.rollout_plan.estimated_time_acceleration >= 60.0
    assert result.agent_count == 4


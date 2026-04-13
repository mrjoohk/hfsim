import importlib

from hf_sim.models import EvaluationRequest, HardwareProfile


def test_if05_reporting_acceptance():
    module = importlib.import_module("if.if05_reporting")
    result = module.if_05_build_evaluation_report(
        EvaluationRequest(
            run_id="run-int-report",
            revision="abc123",
            hardware_profile=HardwareProfile(cpu_cores=8, ram_bytes=16 * 1024**3, gpu_vram_bytes=8 * 1024**3, gpu_enabled=True, accelerator_name="gpu"),
            config={"scenario": "baseline"},
            seed_bundle={"sim": 1},
            metrics={"prediction_error_1step": 0.1, "latent_consistency": 0.9, "policy_convergence_score": 0.8},
            benchmark_counters={"wall_clock_time_s": 1.0, "sim_time_s": 60.0},
            feature_plan=["state_vector", "terrain", "threat"],
        )
    )
    assert result.benchmark_metrics["time_acceleration_x"] == 60.0

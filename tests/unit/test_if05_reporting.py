import pytest

from hf_sim.models import EvaluationRequest, HardwareProfile
from uf.if05_reporting import (
    audit_scope_exclusions,
    build_reproducibility_manifest,
    collect_run_metadata,
    compose_evaluation_report,
    compute_benchmark_metrics,
    rank_learning_metrics,
)


def _request():
    return EvaluationRequest(
        run_id="run-eval",
        revision="abc123",
        hardware_profile=HardwareProfile(cpu_cores=8, ram_bytes=16 * 1024**3, gpu_vram_bytes=8 * 1024**3, gpu_enabled=True, accelerator_name="gpu"),
        config={"scenario": "baseline"},
        seed_bundle={"sim": 1, "train": 2},
        metrics={"prediction_error_1step": 0.1, "latent_consistency": 0.95, "policy_convergence_score": 0.8},
        benchmark_counters={"wall_clock_time_s": 2.0, "sim_time_s": 120.0},
        feature_plan=["state_vector", "terrain", "threat", "photoreal_rendering"],
    )


def test_if05_uf_chain_composes_report():
    metadata = collect_run_metadata(_request())
    benchmark = compute_benchmark_metrics(metadata)
    ranking = rank_learning_metrics(benchmark)
    scope = audit_scope_exclusions(ranking)
    report_context = build_reproducibility_manifest(scope)
    report = compose_evaluation_report(report_context)
    assert report.benchmark_metrics["time_acceleration_x"] == 60.0
    assert "photoreal_rendering" in report.scope_findings


def test_compute_benchmark_metrics_zero_wall_clock_raises():
    request = _request()
    request.benchmark_counters["wall_clock_time_s"] = 0.0
    metadata = collect_run_metadata(request)
    with pytest.raises(ValueError):
        compute_benchmark_metrics(metadata)

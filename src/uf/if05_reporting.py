"""UF implementations for IF-05 reporting."""

from __future__ import annotations

import json

from hf_sim.models import (
    BenchmarkMetricsContext,
    EvaluationMetadataContext,
    EvaluationReportBundle,
    EvaluationRequest,
    RankingContext,
    ReportAssemblyContext,
    ScopeAuditContext,
)


def collect_run_metadata(evaluation_request: EvaluationRequest) -> EvaluationMetadataContext:
    """Collect reproducibility metadata."""
    if evaluation_request.hardware_profile is None:
        raise ValueError("hardware profile required")
    metadata = {
        "run_id": evaluation_request.run_id,
        "revision": evaluation_request.revision or "unknown",
        "hardware_profile": {
            "cpu_cores": evaluation_request.hardware_profile.cpu_cores,
            "ram_bytes": evaluation_request.hardware_profile.ram_bytes,
            "gpu_vram_bytes": evaluation_request.hardware_profile.gpu_vram_bytes,
            "gpu_enabled": evaluation_request.hardware_profile.gpu_enabled,
            "accelerator_name": evaluation_request.hardware_profile.accelerator_name,
        },
        "seed_bundle": dict(sorted(evaluation_request.seed_bundle.items())),
        "config": dict(evaluation_request.config),
        "feature_plan": list(evaluation_request.feature_plan),
    }
    return EvaluationMetadataContext(evaluation_request=evaluation_request, metadata=metadata)


def compute_benchmark_metrics(evaluation_metadata_context: EvaluationMetadataContext) -> BenchmarkMetricsContext:
    """Compute benchmark and acceleration metrics."""
    counters = evaluation_metadata_context.evaluation_request.benchmark_counters
    wall_clock_time = counters["wall_clock_time_s"]
    sim_time = counters["sim_time_s"]
    if wall_clock_time <= 0:
        raise ValueError("wall_clock_time must be > 0")
    if sim_time < 0:
        raise ValueError("sim_time must be >= 0")

    benchmark_metrics = dict(counters)
    benchmark_metrics["time_acceleration_x"] = sim_time / wall_clock_time
    benchmark_metrics["meets_target_60x"] = 1.0 if benchmark_metrics["time_acceleration_x"] >= 60.0 else 0.0
    learning_metrics = dict(evaluation_metadata_context.evaluation_request.metrics)
    return BenchmarkMetricsContext(
        metadata=evaluation_metadata_context.metadata,
        benchmark_metrics=benchmark_metrics,
        learning_metrics=learning_metrics,
    )


def rank_learning_metrics(benchmark_metrics_context: BenchmarkMetricsContext) -> RankingContext:
    """Rank learning metrics by validation priority."""
    learning_metrics = benchmark_metrics_context.learning_metrics
    prediction = {k: v for k, v in learning_metrics.items() if "prediction" in k}
    if not prediction:
        raise ValueError("prediction error metrics required")
    latent = {k: v for k, v in learning_metrics.items() if "latent" in k}
    policy = {k: v for k, v in learning_metrics.items() if "policy" in k}
    auxiliary = {k: v for k, v in learning_metrics.items() if k not in {**prediction, **latent, **policy}}
    return RankingContext(
        metadata=benchmark_metrics_context.metadata,
        benchmark_metrics=benchmark_metrics_context.benchmark_metrics,
        ranked_groups={
            "prediction_error": prediction,
            "latent_rollout_consistency": latent,
            "policy_convergence": policy,
            "auxiliary": auxiliary,
        },
    )


def audit_scope_exclusions(ranking_context: RankingContext) -> ScopeAuditContext:
    """Audit phase-one scope exclusions."""
    feature_plan = ranking_context.metadata.get("feature_plan")
    if feature_plan is None:
        raise ValueError("feature plan required")
    excluded = {
        "photoreal_rendering",
        "hil_sil",
        "manned_handover",
        "measured_data_calibration",
    }
    findings = sorted({feature for feature in feature_plan if feature in excluded})
    return ScopeAuditContext(
        metadata=ranking_context.metadata,
        benchmark_metrics=ranking_context.benchmark_metrics,
        ranked_groups=ranking_context.ranked_groups,
        scope_findings=findings,
    )


def build_reproducibility_manifest(scope_audit_context: ScopeAuditContext) -> ReportAssemblyContext:
    """Build reproducibility manifest."""
    required = ["run_id", "revision", "hardware_profile", "seed_bundle"]
    for key in required:
        if not scope_audit_context.metadata.get(key):
            raise ValueError(key)
    manifest = {
        "schema_version": "1.0",
        "run_id": scope_audit_context.metadata["run_id"],
        "revision": scope_audit_context.metadata["revision"],
        "hardware_profile": scope_audit_context.metadata["hardware_profile"],
        "seed_bundle": scope_audit_context.metadata["seed_bundle"],
        "config": scope_audit_context.metadata["config"],
    }
    json.dumps(manifest, sort_keys=True)
    return ReportAssemblyContext(
        metadata=scope_audit_context.metadata,
        benchmark_metrics=scope_audit_context.benchmark_metrics,
        ranked_groups=scope_audit_context.ranked_groups,
        scope_findings=scope_audit_context.scope_findings,
        manifest=manifest,
    )


def compose_evaluation_report(report_assembly_context: ReportAssemblyContext) -> EvaluationReportBundle:
    """Compose final evaluation report."""
    if report_assembly_context.benchmark_metrics is None:
        raise RuntimeError("benchmark_metrics missing")
    if report_assembly_context.scope_findings is None:
        raise RuntimeError("scope_audit missing")
    return EvaluationReportBundle(
        run_id=report_assembly_context.metadata["run_id"],
        benchmark_metrics=report_assembly_context.benchmark_metrics,
        ranked_groups=report_assembly_context.ranked_groups,
        scope_findings=report_assembly_context.scope_findings,
        manifest=report_assembly_context.manifest,
    )

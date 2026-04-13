"""IF-05 integration module."""

from __future__ import annotations

from hf_sim.models import EvaluationReportBundle, EvaluationRequest
from uf.if05_reporting import (
    audit_scope_exclusions,
    build_reproducibility_manifest,
    collect_run_metadata,
    compose_evaluation_report,
    compute_benchmark_metrics,
    rank_learning_metrics,
)


def if_05_build_evaluation_report(evaluation_request: EvaluationRequest) -> EvaluationReportBundle:
    """Evaluate benchmark performance and record reproducible experiment evidence."""
    metadata_context = collect_run_metadata(evaluation_request)
    benchmark_context = compute_benchmark_metrics(metadata_context)
    ranking_context = rank_learning_metrics(benchmark_context)
    scope_context = audit_scope_exclusions(ranking_context)
    report_context = build_reproducibility_manifest(scope_context)
    return compose_evaluation_report(report_context)

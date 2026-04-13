# Unit Function Blocks

- UF-ID: UF-05-01
- Parent IF: IF-05
- Goal: collect reproducibility metadata
- I/O Contract:
    Input:  evaluation_request: EvaluationRequest, metrics + config + seed + hardware profile bundle, valid schema
    Output: evaluation_metadata_context: EvaluationMetadataContext, eval metrics + run metadata fields, valid schema
- Algorithm Summary:
    Metadata collection: extract reproducibility-critical fields from evaluation request into normalized manifest-ready metadata.
- Edge Cases:
    - revision field is missing: set `revision="unknown"` and log warning
    - hardware profile is absent: raise `ValueError("hardware profile required")`
    - seed bundle contains duplicate names: deduplicate deterministically and log warning
- Verification Plan:
    Unit:        tests/unit/test_collect_run_metadata.py::test_collects_required_metadata
                 tests/unit/test_collect_run_metadata.py::test_missing_hardware_profile_raises
                 tests/unit/test_collect_run_metadata.py::test_duplicate_seed_names_are_deduplicated
    Integration: tests/integration/test_if05_reporting.py::test_metadata_collection_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-02
- Parent IF: IF-05
- Goal: compute benchmark and acceleration metrics
- I/O Contract:
    Input:  evaluation_metadata_context: EvaluationMetadataContext, eval metrics + run metadata fields, valid schema
    Output: benchmark_metrics_context: BenchmarkMetricsContext, benchmark metrics + metadata refs, valid schema
- Algorithm Summary:
    Benchmark metric computation: aggregate runtime, sim-time, and benchmark outcome counters into performance metrics including time acceleration.
- Edge Cases:
    - wall_clock_time is zero: raise `ValueError("wall_clock_time must be > 0")`
    - sim_time is negative: raise `ValueError("sim_time must be >= 0")`
    - required benchmark counter is missing: raise `KeyError` with counter name
- Verification Plan:
    Unit:        tests/unit/test_compute_benchmark_metrics.py::test_computes_acceleration_ratio
                 tests/unit/test_compute_benchmark_metrics.py::test_zero_wall_clock_raises
                 tests/unit/test_compute_benchmark_metrics.py::test_missing_counter_raises
    Integration: tests/integration/test_if05_reporting.py::test_benchmark_metric_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-03
- Parent IF: IF-05
- Goal: rank learning metrics by validation priority
- I/O Contract:
    Input:  benchmark_metrics_context: BenchmarkMetricsContext, benchmark metrics + metadata refs, valid schema
    Output: ranking_context: RankingContext, ranked metrics + metadata refs, valid schema
- Algorithm Summary:
    Priority ordering: group and order metrics as prediction error first, latent rollout consistency second, and policy convergence third.
- Edge Cases:
    - prediction error metrics are missing: raise `ValueError("prediction error metrics required")`
    - unknown metric group appears: place in auxiliary section and log warning
    - duplicate priority key is found: keep first deterministic ordering and log warning
- Verification Plan:
    Unit:        tests/unit/test_rank_learning_metrics.py::test_orders_metrics_by_priority
                 tests/unit/test_rank_learning_metrics.py::test_missing_prediction_metrics_raises
                 tests/unit/test_rank_learning_metrics.py::test_unknown_group_is_marked_auxiliary
    Integration: tests/integration/test_if05_reporting.py::test_metric_ranking_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-04
- Parent IF: IF-05
- Goal: audit phase-one scope exclusions
- I/O Contract:
    Input:  ranking_context: RankingContext, ranked metrics + metadata refs, valid schema
    Output: scope_audit_context: ScopeAuditContext, ranked metrics + scope findings + metadata refs, valid schema
- Algorithm Summary:
    Scope audit: compare run/config feature declarations against phase-1 exclusion rules and emit explicit findings.
- Edge Cases:
    - feature plan is absent: raise `ValueError("feature plan required")`
    - excluded feature appears multiple times: collapse duplicates into one finding
    - unknown feature token is encountered: record as unclassified and log warning
- Verification Plan:
    Unit:        tests/unit/test_audit_scope_exclusions.py::test_flags_excluded_features
                 tests/unit/test_audit_scope_exclusions.py::test_missing_feature_plan_raises
                 tests/unit/test_audit_scope_exclusions.py::test_duplicate_features_are_collapsed
    Integration: tests/integration/test_if05_reporting.py::test_scope_audit_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-05
- Parent IF: IF-05
- Goal: build reproducibility manifest
- I/O Contract:
    Input:  scope_audit_context: ScopeAuditContext, ranked metrics + scope findings + metadata refs, valid schema
    Output: report_assembly_context: ReportAssemblyContext, manifest + scope + ranked metrics refs, valid schema
- Algorithm Summary:
    Manifest construction: serialize normalized reproducibility metadata into stable manifest fields and schema version.
- Edge Cases:
    - manifest serialization target is unwritable: propagate `IOError`
    - required metadata field is empty: raise `ValueError` with field name
    - manifest schema version is unsupported: raise `RuntimeError("unsupported manifest schema")`
- Verification Plan:
    Unit:        tests/unit/test_build_reproducibility_manifest.py::test_builds_valid_manifest
                 tests/unit/test_build_reproducibility_manifest.py::test_empty_required_field_raises
                 tests/unit/test_build_reproducibility_manifest.py::test_unwritable_target_propagates_ioerror
    Integration: tests/integration/test_if05_reporting.py::test_manifest_build_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

---

- UF-ID: UF-05-06
- Parent IF: IF-05
- Goal: compose final evaluation report bundle
- I/O Contract:
    Input:  report_assembly_context: ReportAssemblyContext, manifest + scope + ranked metrics refs, valid schema
    Output: evaluation_report_bundle: EvaluationReportBundle, ranked metrics + benchmark report + scope audit + manifest, valid schema
- Algorithm Summary:
    Report composition: merge ranked learning metrics with benchmark, scope-audit, and manifest dependencies into final evidence bundle.
- Edge Cases:
    - benchmark metrics dependency is missing: raise `RuntimeError("benchmark_metrics missing")`
    - scope audit dependency is missing: raise `RuntimeError("scope_audit missing")`
    - final report bundle exceeds configured artifact size limit: raise `MemoryError`
- Verification Plan:
    Unit:        tests/unit/test_compose_evaluation_report.py::test_composes_final_report_bundle
                 tests/unit/test_compose_evaluation_report.py::test_missing_benchmark_metrics_raises
                 tests/unit/test_compose_evaluation_report.py::test_missing_scope_audit_raises
    Integration: tests/integration/test_if05_reporting.py::test_report_composition_chain
    Coverage:    >= 90%
- Evidence Pack Fields: scenario_id, run_id, metrics, environment, commit_sha

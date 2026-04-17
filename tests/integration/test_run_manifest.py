"""Integration tests for run manifest and evidence pack (REQ-010).

Verifies:
- capture_run_manifest() completes within 5 s including hardware detection
  and git query (REQ-010 acceptance criterion).
- All required manifest fields are populated.
- Evidence pack can be built, saved, and round-tripped through JSON.
"""

import json
import time
from pathlib import Path

from hf_sim.benchmark import BenchmarkConfig, run_benchmark
from hf_sim.run_manifest import (
    build_evidence_pack,
    capture_run_manifest,
)


def test_capture_run_manifest_within_5s_acceptance():
    """REQ-010: manifest capture including hardware + git query must be < 5 s."""
    t0 = time.perf_counter()
    manifest = capture_run_manifest(
        run_id="integration-test",
        seed=42,
        config={"n_agents": 4, "scenario": "reference"},
    )
    elapsed = time.perf_counter() - t0

    assert elapsed < 5.0, f"REQ-010 FAIL: manifest capture took {elapsed:.2f}s > 5s"
    assert manifest.hardware_profile.cpu_count >= 1
    assert manifest.hardware_profile.platform_str != ""
    assert manifest.hardware_profile.python_version != ""
    # code_revision is either a 40-char git SHA or "unknown"
    assert manifest.code_revision == "unknown" or len(manifest.code_revision) == 40
    assert manifest.seed == 42


def test_run_manifest_all_required_fields_populated():
    """REQ-010: manifest must include config, seed, hardware profile, code revision."""
    manifest = capture_run_manifest(seed=7, config={"env": "hfsim", "dt": 0.01})
    d = manifest.to_dict()

    assert d["seed"] == 7
    assert d["config"]["env"] == "hfsim"
    assert d["hardware_profile"]["cpu_count"] >= 1
    assert d["hardware_profile"]["ram_total_gb"] >= 0.0
    assert isinstance(d["code_revision"], str)
    assert len(d["code_revision"]) > 0


def test_evidence_pack_round_trip_with_benchmark():
    """Build, save, and reload an evidence pack populated from a real benchmark run."""
    # Run a quick benchmark (1 worker, 5 s simulated)
    bench_cfg = BenchmarkConfig(n_workers=1, sim_duration_s=5.0, seed=0)
    bench_result = run_benchmark(bench_cfg)

    manifest = capture_run_manifest(
        seed=bench_cfg.seed,
        config={"n_workers": bench_cfg.n_workers, "sim_duration_s": bench_cfg.sim_duration_s},
    )

    report_dir = Path.cwd() / "test_benchmark_evidence_dir"
    report_path = report_dir / "bench_report.json"
    pack_path = report_dir / "evidence" / "req004.json"
    try:
        report_dir.mkdir(exist_ok=True)
        with report_path.open("w", encoding="utf-8") as fh:
            json.dump(bench_result.to_dict(), fh)

        pack = build_evidence_pack(
            req_id="REQ-004",
            run_manifest=manifest,
            artifact_paths={"benchmark_report": str(report_path)},
            pass_fail=bench_result.passes_60x,
            notes=[f"min_acceleration={bench_result.min_acceleration:.1f}x"],
        )

        pack_path = pack.save(pack_path)
        assert pack_path.exists()

        loaded = json.loads(pack_path.read_text(encoding="utf-8"))
        assert loaded["req_id"] == "REQ-004"
        assert loaded["pass_fail"] == bench_result.passes_60x
        assert loaded["run_manifest"]["seed"] == bench_cfg.seed
        assert "min_acceleration" in loaded["notes"][0]
    finally:
        pack_path.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)
        (report_dir / "evidence").rmdir()
        report_dir.rmdir()


def test_multiple_manifests_have_unique_run_ids():
    """Sequential captures must produce different run IDs (UUID)."""
    m1 = capture_run_manifest(seed=0)
    m2 = capture_run_manifest(seed=0)
    assert m1.run_id != m2.run_id

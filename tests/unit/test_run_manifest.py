"""Unit tests for hf_sim.run_manifest (REQ-010 reproducibility)."""

import json
import time
from pathlib import Path

import pytest

from hf_sim.run_manifest import (
    EvidencePackManifest,
    HardwareProfile,
    RunManifest,
    build_evidence_pack,
    capture_run_manifest,
)


# ---------------------------------------------------------------------------
# HardwareProfile
# ---------------------------------------------------------------------------

def test_hardware_profile_fields():
    hp = HardwareProfile(cpu_count=4, ram_total_gb=16.0, platform_str="win32", python_version="3.14.0")
    assert hp.cpu_count == 4
    assert hp.ram_total_gb == 16.0
    assert hp.platform_str == "win32"
    assert hp.python_version == "3.14.0"
    assert hp.cpu_freq_mhz == 0.0  # default


# ---------------------------------------------------------------------------
# RunManifest dataclass
# ---------------------------------------------------------------------------

def test_run_manifest_to_dict_has_required_keys():
    manifest = capture_run_manifest(run_id="u-001", seed=42, config={"n_agents": 4})
    d = manifest.to_dict()
    required = {"run_id", "timestamp_utc", "seed", "config", "hardware_profile", "code_revision", "sim_version"}
    assert required.issubset(d.keys())


def test_run_manifest_to_dict_hardware_keys():
    manifest = capture_run_manifest(seed=0)
    hw = manifest.to_dict()["hardware_profile"]
    required = {"cpu_count", "ram_total_gb", "platform_str", "python_version", "cpu_freq_mhz"}
    assert required.issubset(hw.keys())


def test_run_manifest_seed_preserved():
    manifest = capture_run_manifest(seed=99, config={})
    assert manifest.seed == 99
    assert manifest.to_dict()["seed"] == 99


def test_run_manifest_config_preserved():
    cfg = {"scenario": "reference", "n_workers": 4}
    manifest = capture_run_manifest(seed=0, config=cfg)
    assert manifest.config == cfg


def test_run_manifest_auto_run_id_unique():
    m1 = capture_run_manifest(seed=1)
    m2 = capture_run_manifest(seed=2)
    assert m1.run_id != m2.run_id


def test_run_manifest_explicit_run_id():
    manifest = capture_run_manifest(run_id="explicit-id-123", seed=0)
    assert manifest.run_id == "explicit-id-123"


def test_run_manifest_code_revision_not_empty():
    manifest = capture_run_manifest(seed=0)
    assert isinstance(manifest.code_revision, str)
    assert len(manifest.code_revision) > 0


def test_run_manifest_sim_version():
    manifest = capture_run_manifest(seed=0)
    assert manifest.sim_version == "hfsim-0.1.0"


def test_run_manifest_timestamp_iso8601():
    manifest = capture_run_manifest(seed=0)
    # ISO-8601 timestamps contain "T" and "+"/"Z"
    ts = manifest.timestamp_utc
    assert "T" in ts


def test_run_manifest_save_creates_valid_json():
    manifest = capture_run_manifest(seed=77, config={"key": "val"})
    out_path = Path.cwd() / "test_run_manifest.json"
    try:
        out = manifest.save(out_path)
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["seed"] == 77
        assert loaded["config"] == {"key": "val"}
        assert "hardware_profile" in loaded
        assert loaded["hardware_profile"]["cpu_count"] >= 1
    finally:
        out_path.unlink(missing_ok=True)


def test_run_manifest_save_creates_parent_dirs():
    manifest = capture_run_manifest(seed=0)
    out_dir = Path.cwd() / "test_run_manifest_dir"
    out_path = out_dir / "deep" / "nested" / "manifest.json"
    try:
        out = manifest.save(out_path)
        assert out.exists()
    finally:
        out_path.unlink(missing_ok=True)
        (out_dir / "deep" / "nested").rmdir()
        (out_dir / "deep").rmdir()
        out_dir.rmdir()


# ---------------------------------------------------------------------------
# capture_run_manifest timing (REQ-010)
# ---------------------------------------------------------------------------

def test_capture_run_manifest_within_5s():
    t0 = time.perf_counter()
    capture_run_manifest(seed=0)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"capture_run_manifest took {elapsed:.2f}s > 5s (REQ-010)"


def test_capture_run_manifest_hardware_cpu_count():
    manifest = capture_run_manifest(seed=0)
    assert manifest.hardware_profile.cpu_count >= 1


# ---------------------------------------------------------------------------
# EvidencePackManifest
# ---------------------------------------------------------------------------

def test_build_evidence_pack_fields():
    manifest = capture_run_manifest(seed=0)
    pack = build_evidence_pack(
        req_id="REQ-004",
        run_manifest=manifest,
        artifact_paths={"benchmark_report": "reports/time_accel/result.json"},
        pass_fail=True,
        notes=["60x achieved"],
    )
    assert pack.req_id == "REQ-004"
    assert pack.pass_fail is True
    assert pack.artifact_paths["benchmark_report"] == "reports/time_accel/result.json"
    assert "60x achieved" in pack.notes
    assert len(pack.pack_id) > 0


def test_build_evidence_pack_unique_pack_ids():
    m = capture_run_manifest(seed=0)
    p1 = build_evidence_pack(req_id="REQ-001", run_manifest=m)
    p2 = build_evidence_pack(req_id="REQ-001", run_manifest=m)
    assert p1.pack_id != p2.pack_id


def test_evidence_pack_to_dict_required_keys():
    m = capture_run_manifest(seed=0)
    pack = build_evidence_pack(req_id="REQ-001", run_manifest=m, pass_fail=False)
    d = pack.to_dict()
    required = {"pack_id", "req_id", "timestamp_utc", "run_manifest", "artifact_paths", "pass_fail", "notes"}
    assert required.issubset(d.keys())


def test_evidence_pack_to_dict_embeds_run_manifest():
    m = capture_run_manifest(seed=42)
    pack = build_evidence_pack(req_id="REQ-010", run_manifest=m, pass_fail=True)
    d = pack.to_dict()
    assert d["run_manifest"]["seed"] == 42
    assert d["run_manifest"]["sim_version"] == "hfsim-0.1.0"


def test_evidence_pack_save_creates_valid_json():
    m = capture_run_manifest(seed=5, config={"scenario": "reference"})
    pack = build_evidence_pack(
        req_id="REQ-004",
        run_manifest=m,
        artifact_paths={"log": "reports/bench.json"},
        pass_fail=True,
        notes=["auto-generated"],
    )
    out_dir = Path.cwd() / "test_evidence_pack_dir"
    out_path = out_dir / "evidence" / "req004.json"
    try:
        out = pack.save(out_path)
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["req_id"] == "REQ-004"
        assert loaded["pass_fail"] is True
        assert loaded["run_manifest"]["seed"] == 5
        assert loaded["artifact_paths"]["log"] == "reports/bench.json"
    finally:
        out_path.unlink(missing_ok=True)
        (out_dir / "evidence").rmdir()
        out_dir.rmdir()

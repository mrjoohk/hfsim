"""Unit tests for hf_sim.log_store (Parquet round-trip + JSONL fallback)."""

import json
import math
from pathlib import Path

import pytest

from hf_sim.log_store import read_log, write_parquet

# ---------------------------------------------------------------------------
# Minimal entry fixture
# ---------------------------------------------------------------------------

def _entry(branch_id: str = "main", step_index: int = 0) -> dict:
    return {
        "branch_id": branch_id,
        "step_index": step_index,
        "sim_time_s": step_index * 0.01,
        "ownship": {
            "position_m": [100.0, 200.0, 1000.0],
            "velocity_mps": [200.0, 0.0, 0.0],
            "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
            "angular_rate_rps": [0.0, 0.0, 0.0],
            "speed_mps": 200.0,
            "altitude_m": 1000.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "heading_deg": 0.0,
        },
        "control": {
            "throttle": 0.6,
            "body_rate_cmd_rps": [0.1, 0.0, 0.0],
            "load_factor_cmd": 1.0,
        },
        "environment": {"terrain_reference": [100.0, 120.0, 130.0]},
        "atmosphere": {
            "wind_vector_mps": [5.0, 0.0, 0.0],
            "wind_speed_mps": 5.0,
            "density_kgpm3": 1.1,
            "turbulence_level": 0.1,
        },
        "sensor": {"quality": 0.9, "contact_count": 1},
        "radar": {"track_ids": ["th-1"], "track_count": 1},
        "threats": [{"identifier": "th-1", "position_m": [1000.0, 0.0, 1000.0], "distance_m": 900.0}],
        "derived_metrics": {"nearest_threat_distance_m": 900.0, "heading_deg": 0.0},
    }


def _entries() -> list[dict]:
    return [_entry("branch_0", i) for i in range(5)] + [_entry("branch_1", i) for i in range(3)]


# ---------------------------------------------------------------------------
# JSONL round-trip
# ---------------------------------------------------------------------------

def test_read_log_jsonl(tmp_path: Path) -> None:
    src = tmp_path / "replay.jsonl"
    entries = _entries()
    src.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")

    loaded = read_log(src)
    assert len(loaded) == len(entries)
    assert loaded[0]["branch_id"] == "branch_0"
    assert loaded[0]["step_index"] == 0
    assert loaded[0]["ownship"]["altitude_m"] == pytest.approx(1000.0)


def test_read_log_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    src = tmp_path / "replay.jsonl"
    entries = _entries()[:2]
    text = "\n".join(json.dumps(e) for e in entries) + "\n\n"
    src.write_text(text, encoding="utf-8")
    loaded = read_log(src)
    assert len(loaded) == 2


# ---------------------------------------------------------------------------
# Parquet round-trip
# ---------------------------------------------------------------------------

pytest.importorskip("pyarrow", reason="pyarrow not installed")


def test_write_parquet_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "replay.parquet"
    result = write_parquet(_entries(), out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0


def test_read_log_parquet_row_count(tmp_path: Path) -> None:
    out = tmp_path / "replay.parquet"
    entries = _entries()
    write_parquet(entries, out)
    loaded = read_log(out)
    assert len(loaded) == len(entries)


def test_parquet_scalar_fields_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "replay.parquet"
    e = _entry("main", 7)
    write_parquet([e], out)
    [row] = read_log(out)

    assert row["branch_id"] == "main"
    assert row["step_index"] == 7
    assert row["ownship"]["speed_mps"] == pytest.approx(200.0, abs=1e-3)
    assert row["ownship"]["altitude_m"] == pytest.approx(1000.0, abs=1e-3)
    assert row["control"]["throttle"] == pytest.approx(0.6, abs=1e-3)
    assert row["atmosphere"]["turbulence_level"] == pytest.approx(0.1, abs=1e-3)
    assert row["sensor"]["quality"] == pytest.approx(0.9, abs=1e-3)
    assert row["derived_metrics"]["nearest_threat_distance_m"] == pytest.approx(900.0, abs=1e-1)


def test_parquet_position_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "replay.parquet"
    write_parquet([_entry()], out)
    [row] = read_log(out)
    pos = row["ownship"]["position_m"]
    assert len(pos) == 3
    assert pos[0] == pytest.approx(100.0, abs=1e-3)
    assert pos[1] == pytest.approx(200.0, abs=1e-3)
    assert pos[2] == pytest.approx(1000.0, abs=1e-3)


def test_parquet_terrain_reference_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "replay.parquet"
    write_parquet([_entry()], out)
    [row] = read_log(out)
    terr = row["environment"]["terrain_reference"]
    assert len(terr) == 3
    assert terr[0] == pytest.approx(100.0, abs=1e-3)


def test_parquet_threats_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "replay.parquet"
    write_parquet([_entry()], out)
    [row] = read_log(out)
    threats = row["threats"]
    assert len(threats) == 1
    assert threats[0]["identifier"] == "th-1"
    assert threats[0]["distance_m"] == pytest.approx(900.0, abs=1e-1)


def test_parquet_branch_filter_via_read_log(tmp_path: Path) -> None:
    out = tmp_path / "replay.parquet"
    entries = _entries()
    write_parquet(entries, out)
    loaded = read_log(out)
    b0 = [e for e in loaded if e["branch_id"] == "branch_0"]
    b1 = [e for e in loaded if e["branch_id"] == "branch_1"]
    assert len(b0) == 5
    assert len(b1) == 3


def test_parquet_multi_branch_step_order(tmp_path: Path) -> None:
    out = tmp_path / "replay.parquet"
    entries = _entries()
    write_parquet(entries, out)
    loaded = read_log(out)
    b0 = [e for e in loaded if e["branch_id"] == "branch_0"]
    steps = [e["step_index"] for e in b0]
    assert steps == list(range(5))


def test_read_log_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_log(tmp_path / "nonexistent.parquet")

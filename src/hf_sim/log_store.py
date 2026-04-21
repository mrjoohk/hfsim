"""Log store — read/write replay logs in Parquet or JSONL format.

Public API
----------
write_parquet(entries, path) → Path
read_log(path)               → list[dict]   # auto-detects format

The Parquet schema flattens nested dicts into typed columns for efficient
columnar access (filter by branch_id, slice step ranges, etc.).
``read_log`` reconstructs the original nested dict structure so callers are
format-agnostic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Flat-column extraction helpers  (entry dict → scalar / array values)
# ---------------------------------------------------------------------------

def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _flatten(entry: dict[str, Any]) -> dict[str, Any]:
    own  = entry.get("ownship", {})
    ctrl = entry.get("control", {})
    atm  = entry.get("atmosphere", {})
    env  = entry.get("environment", {})
    sens = entry.get("sensor", {})
    rad  = entry.get("radar", {})
    met  = entry.get("derived_metrics", {})

    pos  = own.get("position_m", [0.0, 0.0, 0.0])
    vel  = own.get("velocity_mps", [0.0, 0.0, 0.0])
    quat = own.get("quaternion_wxyz", [1.0, 0.0, 0.0, 0.0])
    ang  = own.get("angular_rate_rps", [0.0, 0.0, 0.0])
    br   = ctrl.get("body_rate_cmd_rps", [0.0, 0.0, 0.0])
    wind = atm.get("wind_vector_mps", [0.0, 0.0, 0.0])
    terr = [float(v) for v in env.get("terrain_reference", [])]
    t_ids = list(rad.get("track_ids", []))
    threats_json = json.dumps(entry.get("threats", []))

    return {
        "branch_id":           str(entry.get("branch_id", "main")),
        "step_index":          int(entry.get("step_index", 0)),
        "sim_time_s":          _f(entry.get("sim_time_s")),
        # ownship
        "pos_x":               _f(pos[0] if len(pos) > 0 else 0),
        "pos_y":               _f(pos[1] if len(pos) > 1 else 0),
        "pos_z":               _f(pos[2] if len(pos) > 2 else 0),
        "vel_x":               _f(vel[0] if len(vel) > 0 else 0),
        "vel_y":               _f(vel[1] if len(vel) > 1 else 0),
        "vel_z":               _f(vel[2] if len(vel) > 2 else 0),
        "quat_w":              _f(quat[0] if len(quat) > 0 else 1),
        "quat_x":              _f(quat[1] if len(quat) > 1 else 0),
        "quat_y":              _f(quat[2] if len(quat) > 2 else 0),
        "quat_z":              _f(quat[3] if len(quat) > 3 else 0),
        "ang_p":               _f(ang[0] if len(ang) > 0 else 0),
        "ang_q":               _f(ang[1] if len(ang) > 1 else 0),
        "ang_r":               _f(ang[2] if len(ang) > 2 else 0),
        "speed_mps":           _f(own.get("speed_mps")),
        "altitude_m":          _f(own.get("altitude_m")),
        "roll_deg":            _f(own.get("roll_deg")),
        "pitch_deg":           _f(own.get("pitch_deg")),
        "heading_deg":         _f(own.get("heading_deg")),
        # control
        "throttle":            _f(ctrl.get("throttle")),
        "roll_cmd":            _f(br[0] if len(br) > 0 else 0),
        "pitch_cmd":           _f(br[1] if len(br) > 1 else 0),
        "yaw_cmd":             _f(br[2] if len(br) > 2 else 0),
        "load_factor_cmd":     _f(ctrl.get("load_factor_cmd", 1.0)),
        # environment
        "terrain_reference":   terr,
        # atmosphere
        "wind_x":              _f(wind[0] if len(wind) > 0 else 0),
        "wind_y":              _f(wind[1] if len(wind) > 1 else 0),
        "wind_z":              _f(wind[2] if len(wind) > 2 else 0),
        "wind_speed_mps":      _f(atm.get("wind_speed_mps")),
        "density_kgpm3":       _f(atm.get("density_kgpm3")),
        "turbulence_level":    _f(atm.get("turbulence_level")),
        # sensor
        "sensor_quality":      _f(sens.get("quality")),
        "sensor_contact_count": int(sens.get("contact_count", 0)),
        # radar
        "radar_track_count":   int(rad.get("track_count", len(t_ids))),
        "radar_track_ids":     t_ids,
        "threats_json":        threats_json,
        # derived
        "nearest_threat_m":    _f(met.get("nearest_threat_distance_m")),
    }


def _unflatten(row: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the nested replay-record dict from Parquet flat columns."""
    br = [row.get("roll_cmd", 0.0), row.get("pitch_cmd", 0.0), row.get("yaw_cmd", 0.0)]
    wind = [row.get("wind_x", 0.0), row.get("wind_y", 0.0), row.get("wind_z", 0.0)]
    pos  = [row.get("pos_x", 0.0), row.get("pos_y", 0.0), row.get("pos_z", 0.0)]
    vel  = [row.get("vel_x", 0.0), row.get("vel_y", 0.0), row.get("vel_z", 0.0)]
    quat = [row.get("quat_w", 1.0), row.get("quat_x", 0.0),
            row.get("quat_y", 0.0), row.get("quat_z", 0.0)]
    ang  = [row.get("ang_p", 0.0), row.get("ang_q", 0.0), row.get("ang_r", 0.0)]
    terr = list(row.get("terrain_reference") or [])

    try:
        threats = json.loads(row.get("threats_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        threats = []

    track_ids_raw = row.get("radar_track_ids") or []
    track_ids = list(track_ids_raw)

    return {
        "branch_id":   row["branch_id"],
        "step_index":  int(row["step_index"]),
        "sim_time_s":  float(row["sim_time_s"]),
        "ownship": {
            "position_m":       pos,
            "velocity_mps":     vel,
            "quaternion_wxyz":  quat,
            "angular_rate_rps": ang,
            "speed_mps":        float(row.get("speed_mps", 0.0)),
            "altitude_m":       float(row.get("altitude_m", 0.0)),
            "roll_deg":         float(row.get("roll_deg", 0.0)),
            "pitch_deg":        float(row.get("pitch_deg", 0.0)),
            "heading_deg":      float(row.get("heading_deg", 0.0)),
        },
        "control": {
            "throttle":          float(row.get("throttle", 0.0)),
            "body_rate_cmd_rps": br,
            "load_factor_cmd":   float(row.get("load_factor_cmd", 1.0)),
        },
        "environment": {
            "terrain_reference": terr,
        },
        "atmosphere": {
            "wind_vector_mps": wind,
            "wind_speed_mps":  float(row.get("wind_speed_mps", 0.0)),
            "density_kgpm3":   float(row.get("density_kgpm3", 0.0)),
            "turbulence_level": float(row.get("turbulence_level", 0.0)),
        },
        "sensor": {
            "quality":       float(row.get("sensor_quality", 0.0)),
            "contact_count": int(row.get("sensor_contact_count", 0)),
        },
        "radar": {
            "track_ids":   track_ids,
            "track_count": int(row.get("radar_track_count", 0)),
        },
        "threats": threats,
        "derived_metrics": {
            "nearest_threat_distance_m": float(row.get("nearest_threat_m", 0.0)),
            "heading_deg":               float(row.get("heading_deg", 0.0)),
        },
    }


# ---------------------------------------------------------------------------
# Public write / read API
# ---------------------------------------------------------------------------

def write_parquet(entries: list[dict[str, Any]], path: str | Path) -> Path:
    """Flatten and write replay entries to a Parquet file."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise RuntimeError("pyarrow is required for Parquet support: pip install pyarrow") from exc

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    flat_rows = [_flatten(e) for e in entries]
    if not flat_rows:
        pq.write_table(pa.table({}), target)
        return target

    # Build per-column lists
    cols: dict[str, list[Any]] = {k: [] for k in flat_rows[0]}
    for row in flat_rows:
        for k, v in row.items():
            cols[k].append(v)

    # Build Arrow arrays with explicit types for scalars
    _float32 = pa.float32()
    _int32   = pa.int32()
    _str     = pa.string()

    scalar_float = {
        "sim_time_s", "pos_x", "pos_y", "pos_z", "vel_x", "vel_y", "vel_z",
        "quat_w", "quat_x", "quat_y", "quat_z", "ang_p", "ang_q", "ang_r",
        "speed_mps", "altitude_m", "roll_deg", "pitch_deg", "heading_deg",
        "throttle", "roll_cmd", "pitch_cmd", "yaw_cmd", "load_factor_cmd",
        "wind_x", "wind_y", "wind_z", "wind_speed_mps", "density_kgpm3",
        "turbulence_level", "sensor_quality", "nearest_threat_m",
    }
    scalar_int   = {"step_index", "sensor_contact_count", "radar_track_count"}
    list_float   = {"terrain_reference"}
    list_str     = {"radar_track_ids"}

    arrays: dict[str, pa.Array] = {}
    for col, values in cols.items():
        if col in scalar_float:
            arrays[col] = pa.array([float(v) for v in values], type=_float32)
        elif col in scalar_int:
            arrays[col] = pa.array([int(v) for v in values], type=_int32)
        elif col in list_float:
            arrays[col] = pa.array(
                [[float(x) for x in (v or [])] for v in values],
                type=pa.list_(_float32),
            )
        elif col in list_str:
            arrays[col] = pa.array(
                [[str(x) for x in (v or [])] for v in values],
                type=pa.list_(_str),
            )
        else:
            arrays[col] = pa.array([str(v) if v is not None else "" for v in values], type=_str)

    table = pa.table(arrays)
    pq.write_table(table, target, compression="snappy")
    return target


def read_log(path: str | Path) -> list[dict[str, Any]]:
    """Read a replay log file (.parquet or .jsonl) and return list of entry dicts.

    Always returns the same nested-dict structure regardless of file format,
    so callers (pyvista_viewer, API routes, tests) are format-agnostic.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    if p.suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ModuleNotFoundError as exc:
            raise RuntimeError("pyarrow is required: pip install pyarrow") from exc

        table = pq.read_table(p)
        col_names = table.schema.names
        rows: list[dict[str, Any]] = []
        for i in range(table.num_rows):
            row = {col: table.column(col)[i].as_py() for col in col_names}
            rows.append(_unflatten(row))
        return rows

    # .jsonl fallback (default format for existing files)
    lines = p.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]

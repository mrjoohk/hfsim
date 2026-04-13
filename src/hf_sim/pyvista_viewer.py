"""Offline PyVista viewer helpers for validation logs."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Iterable


def load_validation_log_jsonl(input_path: str | Path) -> list[dict[str, Any]]:
    """Load validation log entries from JSONL."""
    source = Path(input_path)
    with source.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def render_validation_log(
    entries: Iterable[dict[str, Any]],
    *,
    pyvista_module: Any | None = None,
    plotter: Any | None = None,
) -> Any:
    """Render a validation log with an optional injected PyVista module."""
    records = list(entries)
    if not records:
        raise ValueError("validation log entries required")

    pv = pyvista_module
    if pv is None:
        try:
            pv = importlib.import_module("pyvista")
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError("pyvista is required for offline visualization") from exc

    plot = plotter or pv.Plotter(off_screen=True)
    first = records[0]

    points = [
        row.get("ownship", {}).get("position_m", row.get("ownship_position_m", [0.0, 0.0, 0.0]))
        for row in records
    ]
    trajectory_mesh = pv.PolyData(points)
    plot.add_mesh(trajectory_mesh, color="cyan", point_size=6)

    if len(points) >= 2 and hasattr(pv, "Spline"):
        plot.add_mesh(pv.Spline(points, len(points) * 4), color="yellow", line_width=3)

    terrain_reference = first.get("environment", {}).get("terrain_reference", [])
    if not terrain_reference and "derived_metrics" in first:
        terrain_reference = [first["derived_metrics"].get("terrain_mean_m", 0.0)]
    terrain_points = [[index * 100.0, 0.0, float(height)] for index, height in enumerate(terrain_reference)]
    if terrain_points:
        plot.add_mesh(pv.PolyData(terrain_points), color="tan", point_size=10)

    wind_vector = first.get("atmosphere", {}).get("wind_vector_mps", first.get("wind_vector_mps", [0.0, 0.0, 0.0]))
    if hasattr(pv, "Arrow") and any(abs(value) > 1e-9 for value in wind_vector):
        plot.add_mesh(pv.Arrow(start=points[0], direction=wind_vector), color="green")

    final_sensor_quality = first.get("sensor", {}).get("quality", first.get("sensor_quality", 0.0))
    if hasattr(plot, "add_text"):
        plot.add_text(f"sensor_quality={final_sensor_quality:.3f}", position="upper_left", font_size=10)
    return plot

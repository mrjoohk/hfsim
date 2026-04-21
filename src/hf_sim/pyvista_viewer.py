"""Offline PyVista replay viewer helpers for validation logs."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np


def load_validation_log_jsonl(input_path: str | Path) -> list[dict[str, Any]]:
    """Load validation log entries from JSONL."""
    source = Path(input_path)
    with source.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_validation_log(input_path: str | Path) -> list[dict[str, Any]]:
    """Load a replay log file into viewer-ready records."""
    return load_validation_log_jsonl(input_path)


class PlaybackController:
    """Stateful branch-aware playback controller for offline replay logs."""

    def __init__(self, entries: Iterable[dict[str, Any]]) -> None:
        self._entries: list[dict[str, Any]] = []
        self._branches: list[str] = []
        self.current_branch: str = "main"
        self.current_index: int = 0
        self.is_playing: bool = False
        self.playback_speed: float = 1.0
        self.loaded_path: str | None = None
        self.load_entries(entries)

    @property
    def branches(self) -> list[str]:
        return list(self._branches)

    def load_entries(self, entries: Iterable[dict[str, Any]]) -> None:
        records = sorted(
            (dict(entry) for entry in entries),
            key=lambda row: (str(row.get("branch_id", "main")), int(row.get("step_index", 0))),
        )
        if not records:
            raise ValueError("validation log entries required")
        self._entries = records
        self._branches = sorted({str(entry.get("branch_id", "main")) for entry in records})
        self.current_branch = self._branches[0]
        self.current_index = 0
        self.is_playing = False

    def load_path(self, input_path: str | Path) -> None:
        path = Path(input_path)
        self.load_entries(load_validation_log_jsonl(path))
        self.loaded_path = str(path)

    def current_branch_entries(self) -> list[dict[str, Any]]:
        return [entry for entry in self._entries if str(entry.get("branch_id", "main")) == self.current_branch]

    def current_entry(self) -> dict[str, Any]:
        branch_entries = self.current_branch_entries()
        if not branch_entries:
            raise ValueError("selected branch has no entries")
        self.current_index = max(0, min(self.current_index, len(branch_entries) - 1))
        return branch_entries[self.current_index]

    def set_branch(self, branch_id: str) -> dict[str, Any]:
        if branch_id not in self._branches:
            raise ValueError(f"unknown branch_id: {branch_id}")
        self.current_branch = branch_id
        self.current_index = 0
        return self.current_entry()

    def branch_at_index(self, branch_index: int) -> dict[str, Any]:
        if not self._branches:
            raise ValueError("no branches available")
        branch_id = self._branches[max(0, min(int(branch_index), len(self._branches) - 1))]
        return self.set_branch(branch_id)

    def seek(self, index: int) -> dict[str, Any]:
        branch_entries = self.current_branch_entries()
        if not branch_entries:
            raise ValueError("selected branch has no entries")
        self.current_index = max(0, min(int(index), len(branch_entries) - 1))
        return self.current_entry()

    def step_forward(self, step_size: int = 1) -> dict[str, Any]:
        return self.seek(self.current_index + max(1, int(step_size)))

    def step_backward(self, step_size: int = 1) -> dict[str, Any]:
        return self.seek(self.current_index - max(1, int(step_size)))

    def toggle_play(self) -> bool:
        self.is_playing = not self.is_playing
        return self.is_playing

    def set_playback_speed(self, speed: float) -> float:
        self.playback_speed = max(0.1, float(speed))
        return self.playback_speed

    def tick(self) -> dict[str, Any]:
        step_size = max(1, int(round(self.playback_speed)))
        return self.step_forward(step_size=step_size)


def _get_pyvista_module(pyvista_module: Any | None = None) -> Any:
    pv = pyvista_module
    if pv is None:
        try:
            pv = importlib.import_module("pyvista")
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError("pyvista is required for offline visualization") from exc
    return pv


def _position(entry: dict[str, Any]) -> list[float]:
    return list(entry.get("ownship", {}).get("position_m", entry.get("ownship_position_m", [0.0, 0.0, 0.0])))


def _velocity(entry: dict[str, Any]) -> list[float]:
    return list(entry.get("ownship", {}).get("velocity_mps", entry.get("ownship_velocity_mps", [0.0, 0.0, 0.0])))


def _terrain_reference(entry: dict[str, Any]) -> list[float]:
    terrain = entry.get("environment", {}).get("terrain_reference", [])
    if terrain:
        return [float(value) for value in terrain]
    if "derived_metrics" in entry:
        return [float(entry["derived_metrics"].get("terrain_mean_m", 0.0))]
    return []


def _threat_positions(entry: dict[str, Any]) -> list[list[float]]:
    threats = entry.get("threats")
    if threats is not None:
        return [list(threat.get("position_m", [0.0, 0.0, 0.0])) for threat in threats]
    return [list(position) for position in entry.get("threat_positions_m", [])]


def _wind_vector(entry: dict[str, Any]) -> list[float]:
    return list(entry.get("atmosphere", {}).get("wind_vector_mps", entry.get("wind_vector_mps", [0.0, 0.0, 0.0])))


def _vector_norm(values: list[float]) -> float:
    return float(np.linalg.norm(np.asarray(values, dtype=float)))


def _direction(vector: list[float], fallback: list[float] | None = None) -> list[float]:
    base = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(base))
    if norm <= 1e-9:
        return list(fallback or [1.0, 0.0, 0.0])
    return list((base / norm).tolist())


def _trajectory_scale(points: list[list[float]]) -> float:
    if len(points) < 2:
        return 40.0
    arr = np.asarray(points, dtype=float)
    extents = np.ptp(arr, axis=0)
    return float(max(20.0, min(200.0, max(extents.max() * 0.03, 20.0))))


def _playback_lines(entry: dict[str, Any], controller: PlaybackController) -> list[str]:
    state = "PLAYING" if controller.is_playing else "PAUSED"
    return [
        "=== HF_Sim Replay ===",
        f"branch  {entry.get('branch_id', controller.current_branch)}",
        f"step    {entry.get('step_index', 0)} / {max(0, len(controller.current_branch_entries()) - 1)}",
        f"sim t   {entry.get('sim_time_s', 0.0):.2f} s",
        f"speed   x{controller.playback_speed:.1f}",
        f"state   {state}",
    ]


def _vehicle_lines(entry: dict[str, Any]) -> list[str]:
    ownship = entry.get("ownship", {})
    return [
        "--- Ownship ---",
        f"altitude  {float(ownship.get('altitude_m', _position(entry)[2])):8.1f} m",
        f"speed     {float(ownship.get('speed_mps', 0.0)):8.2f} mps",
        f"roll      {float(ownship.get('roll_deg', 0.0)):8.1f} deg",
        f"pitch     {float(ownship.get('pitch_deg', 0.0)):8.1f} deg",
        f"heading   {float(ownship.get('heading_deg', 0.0)):8.1f} deg",
        f"q_norm    {float(ownship.get('quaternion_norm', 1.0)):8.5f}",
    ]


def _replace_actor(plotter: Any, actors: dict[str, Any], key: str, actor: Any) -> None:
    previous = actors.get(key)
    if previous is not None and hasattr(plotter, "remove_actor"):
        try:
            plotter.remove_actor(previous)
        except Exception:
            pass
    actors[key] = actor


def _add_mesh(plotter: Any, actors: dict[str, Any], key: str, mesh: Any, **kwargs: Any) -> None:
    actor = plotter.add_mesh(mesh, **kwargs)
    _replace_actor(plotter, actors, key, actor)


def _control_lines(entry: dict[str, Any]) -> list[str]:
    control = entry.get("control", {})
    body_rate_cmd = control.get("body_rate_cmd_rps", [0.0, 0.0, 0.0])
    return [
        "--- Control ---",
        f"throttle  {float(control.get('throttle', 0.0)):8.2f}",
        f"roll cmd  {float(body_rate_cmd[0]):8.2f} r/s",
        f"pitch cmd {float(body_rate_cmd[1]):8.2f} r/s",
        f"yaw cmd   {float(body_rate_cmd[2]):8.2f} r/s",
        f"load fac  {float(control.get('load_factor_cmd', 1.0)):8.2f}",
    ]


def _sensor_lines(entry: dict[str, Any]) -> list[str]:
    sensor = entry.get("sensor", {})
    radar = entry.get("radar", {})
    atmosphere = entry.get("atmosphere", {})
    derived = entry.get("derived_metrics", {})
    quality = float(sensor.get("quality", 0.0))
    det_range = 6000.0 * (0.5 + 0.5 * quality)
    return [
        "--- Sensor / Environment ---",
        f"sensor q  {quality:8.3f}",
        f"det range {det_range:8.0f} m",
        f"contacts  {int(sensor.get('contact_count', 0)):8d}",
        f"tracks    {int(radar.get('track_count', len(radar.get('track_ids', [])))):8d}",
        f"nearest   {float(derived.get('nearest_threat_distance_m', 0.0)):8.1f} m",
        f"wind      {float(atmosphere.get('wind_speed_mps', 0.0)):8.2f} mps",
        f"density   {float(atmosphere.get('density_kgpm3', 0.0)):8.3f}",
    ]


def _help_lines(controller: PlaybackController) -> list[str]:
    branch_hint = f"Branch: 0..{max(0, len(controller.branches) - 1)}" if len(controller.branches) > 1 else "Single branch"
    return [
        "Space:play/pause  Left/Right:step  R:reset cam  O:open  S:screenshot",
        branch_hint,
    ]


def _set_text_block(
    plotter: Any,
    scene: dict[str, Any],
    key: str,
    lines: list[str],
    *,
    position: str,
    font_size: int,
) -> None:
    if not hasattr(plotter, "add_text"):
        return
    text_actors = scene.setdefault("text_actors", {})
    if hasattr(plotter, "remove_actor") and text_actors.get(key) is not None:
        try:
            plotter.remove_actor(text_actors[key])
        except Exception:
            pass
    text_actors[key] = plotter.add_text(
        "\n".join(lines),
        position=position,
        font_size=font_size,
    )


def _configure_plotter(plotter: Any) -> None:
    if hasattr(plotter, "set_background"):
        try:
            plotter.set_background("#1a1a2e", top="#16213e")
        except TypeError:
            plotter.set_background("#1a1a2e")
    if hasattr(plotter, "show_grid"):
        try:
            plotter.show_grid(color="#2d3748")
        except Exception:
            pass
    if hasattr(plotter, "add_axes"):
        try:
            plotter.add_axes()
        except Exception:
            pass


def _apply_transform(
    mesh: Any,
    fwd: np.ndarray,
    rgt: np.ndarray,
    up: np.ndarray,
    origin: np.ndarray,
) -> Any:
    """Map mesh points from local (x=fwd, y=rgt, z=up) frame to world frame."""
    pts = np.asarray(mesh.points, dtype=float)
    world = pts[:, 0:1] * fwd + pts[:, 1:2] * rgt + pts[:, 2:3] * up + origin
    result = mesh.copy()
    result.points = world
    return result


def _local_axes(velocity: list[float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (fwd, rgt, up) unit vectors aligned to velocity direction."""
    fwd = np.array(_direction(velocity), dtype=float)
    world_up = np.array([0.0, 0.0, 1.0])
    rgt = np.cross(fwd, world_up)
    rgt_norm = float(np.linalg.norm(rgt))
    if rgt_norm < 1e-9:
        rgt = np.array([0.0, 1.0, 0.0])
    else:
        rgt = rgt / rgt_norm
    up = np.cross(rgt, fwd)
    return fwd, rgt, up


def _build_terrain_mesh(pv: Any, terrain_reference: list[float], origin: list[float]) -> Any:
    """Build a static terrain strip at fixed world origin (not re-centered each frame)."""
    spacing = 120.0
    half_width = 600.0
    if hasattr(pv, "StructuredGrid") and terrain_reference:
        x = np.tile(
            np.arange(len(terrain_reference), dtype=float) * spacing + (origin[0] - spacing),
            (2, 1),
        )
        y = np.vstack([
            np.full(len(terrain_reference), origin[1] - half_width),
            np.full(len(terrain_reference), origin[1] + half_width),
        ])
        z = np.vstack([terrain_reference, terrain_reference]).astype(float)
        return pv.StructuredGrid(x, y, z)
    terrain_points = [
        [origin[0] - spacing + index * spacing, origin[1], float(height)]
        for index, height in enumerate(terrain_reference)
    ]
    return pv.PolyData(terrain_points)


def _build_ownship_icon(
    pv: Any,
    position: list[float],
    velocity: list[float],
    scale: float,
) -> list[tuple[str, Any, dict[str, Any]]]:
    """Build aircraft mesh: fuselage + delta wings + vertical tail fin."""
    fwd, rgt, up = _local_axes(velocity)
    pos = np.array(position, dtype=float)
    s = scale
    meshes: list[tuple[str, Any, dict[str, Any]]] = []

    # Fuselage: long narrow box along local X (forward direction)
    fuselage = pv.Box(bounds=[-s * 1.0, s * 1.0, -s * 0.09, s * 0.09, -s * 0.09, s * 0.09])
    meshes.append((
        "ownship_fuselage",
        _apply_transform(fuselage, fwd, rgt, up, pos),
        {"color": "#f97316", "smooth_shading": True},
    ))

    # Left wing (negative rgt direction)
    left_wing = pv.Box(bounds=[-s * 0.15, s * 0.40, -s * 0.85, -s * 0.09, -s * 0.04, s * 0.04])
    meshes.append((
        "ownship_left_wing",
        _apply_transform(left_wing, fwd, rgt, up, pos),
        {"color": "#fb923c", "smooth_shading": True},
    ))

    # Right wing (positive rgt direction)
    right_wing = pv.Box(bounds=[-s * 0.15, s * 0.40, s * 0.09, s * 0.85, -s * 0.04, s * 0.04])
    meshes.append((
        "ownship_right_wing",
        _apply_transform(right_wing, fwd, rgt, up, pos),
        {"color": "#fb923c", "smooth_shading": True},
    ))

    # Vertical tail fin
    tail_fin = pv.Box(bounds=[-s * 0.95, -s * 0.55, -s * 0.04, s * 0.04, s * 0.05, s * 0.50])
    meshes.append((
        "ownship_tail",
        _apply_transform(tail_fin, fwd, rgt, up, pos),
        {"color": "#ea580c", "smooth_shading": True},
    ))

    return meshes


def _build_radar_sphere(
    pv: Any,
    position: list[float],
    sensor_quality: float,
) -> tuple[str, Any, dict[str, Any]]:
    """Build transparent wireframe sphere showing radar detection range."""
    detection_range = 6000.0 * (0.5 + 0.5 * float(sensor_quality))
    sphere = pv.Sphere(radius=detection_range, center=position, theta_resolution=24, phi_resolution=24)
    return (
        "radar_range_sphere",
        sphere,
        {"color": "#38bdf8", "opacity": 0.07, "style": "wireframe", "line_width": 1},
    )


def _build_threat_meshes(
    pv: Any,
    threat_positions: list[list[float]],
    scale: float,
) -> list[tuple[str, Any, dict[str, Any]]]:
    meshes: list[tuple[str, Any, dict[str, Any]]] = []
    threat_range_m = 1500.0
    for index, position in enumerate(threat_positions):
        # Solid marker sphere
        marker = pv.Sphere(radius=scale * 0.28, center=position)
        meshes.append((f"threat_marker_{index}", marker, {"color": "#e11d48", "smooth_shading": True}))
        # Transparent range sphere
        range_sphere = pv.Sphere(
            radius=threat_range_m,
            center=position,
            theta_resolution=20,
            phi_resolution=20,
        )
        meshes.append((
            f"threat_range_{index}",
            range_sphere,
            {"color": "#f43f5e", "opacity": 0.06, "style": "wireframe", "line_width": 1},
        ))
    return meshes


def _clear_actor_prefix(plotter: Any, actors: dict[str, Any], prefix: str) -> None:
    for key in [name for name in actors if name.startswith(prefix)]:
        if hasattr(plotter, "remove_actor"):
            try:
                plotter.remove_actor(actors[key])
            except Exception:
                pass
        actors.pop(key, None)


def _update_scene(scene: dict[str, Any]) -> dict[str, Any]:
    plotter = scene["plotter"]
    pv = scene["pyvista"]
    controller: PlaybackController = scene["controller"]
    entry = controller.current_entry()
    branch_entries = controller.current_branch_entries()
    actors = scene["actors"]

    points = [_position(row) for row in branch_entries]
    scale = _trajectory_scale(points)

    # Trajectory
    _add_mesh(plotter, actors, "trajectory_points", pv.PolyData(points), color="#38bdf8", point_size=4, opacity=0.30)
    if len(points) >= 2 and hasattr(pv, "Spline"):
        _add_mesh(plotter, actors, "trajectory_spline", pv.Spline(points, max(2, len(points) * 4)), color="#0ea5e9", line_width=4)

    # Aircraft mesh
    current_position = _position(entry)
    for key, mesh, kwargs in _build_ownship_icon(pv, current_position, _velocity(entry), scale):
        _add_mesh(plotter, actors, key, mesh, **kwargs)

    # Velocity arrow
    velocity = _velocity(entry)
    if hasattr(pv, "Arrow"):
        _add_mesh(plotter, actors, "velocity_arrow", pv.Arrow(start=current_position, direction=velocity), color="#fbbf24")

    # Terrain is static — only built once in build_scene; skip here

    # Threat markers + range spheres
    threat_positions = _threat_positions(entry)
    _clear_actor_prefix(plotter, actors, "threat_marker_")
    _clear_actor_prefix(plotter, actors, "threat_range_")
    for key, mesh, kwargs in _build_threat_meshes(pv, threat_positions, scale):
        _add_mesh(plotter, actors, key, mesh, **kwargs)

    # Radar detection range sphere
    sensor_quality = float(entry.get("sensor", {}).get("quality", 0.5))
    key, mesh, kwargs = _build_radar_sphere(pv, current_position, sensor_quality)
    _add_mesh(plotter, actors, key, mesh, **kwargs)

    # Wind arrow
    wind_vector = _wind_vector(entry)
    if hasattr(pv, "Arrow") and any(abs(value) > 1e-9 for value in wind_vector):
        wind_start = [current_position[0], current_position[1], current_position[2] + scale * 1.4]
        _add_mesh(plotter, actors, "wind_arrow", pv.Arrow(start=wind_start, direction=wind_vector), color="#22c55e")

    # Text panels — two left columns (playback + vehicle), two right columns (sensor + control)
    # Help bar at bottom edge (single line)
    _set_text_block(plotter, scene, "playback", _playback_lines(entry, controller), position="upper_left", font_size=13)
    _set_text_block(plotter, scene, "vehicle", _vehicle_lines(entry), position="lower_left", font_size=12)
    _set_text_block(plotter, scene, "sensor", _sensor_lines(entry), position="upper_right", font_size=12)
    _set_text_block(plotter, scene, "control", _control_lines(entry), position="lower_right", font_size=12)
    _set_text_block(plotter, scene, "help", _help_lines(controller), position="lower_edge", font_size=10)
    return entry


def build_scene(
    entries: Iterable[dict[str, Any]],
    *,
    pyvista_module: Any | None = None,
    plotter: Any | None = None,
    branch_id: str | None = None,
    off_screen: bool = True,
) -> dict[str, Any]:
    """Build a replay scene and return scene state with controller."""
    pv = _get_pyvista_module(pyvista_module)
    controller = PlaybackController(entries)
    if branch_id is not None:
        controller.set_branch(branch_id)
    plot = plotter or pv.Plotter(off_screen=off_screen)
    _configure_plotter(plot)
    scene: dict[str, Any] = {
        "pyvista": pv,
        "plotter": plot,
        "controller": controller,
        "actors": {},
        "text_actors": {},
    }

    # Build terrain once from the first entry at its fixed world position
    first_entry = controller.current_entry()
    terrain_ref = _terrain_reference(first_entry)
    if terrain_ref:
        first_pos = _position(first_entry)
        terrain_mesh = _build_terrain_mesh(pv, terrain_ref, first_pos)
        plot.add_mesh(terrain_mesh, color="#8b7355", opacity=0.90, show_edges=True, edge_color="#4a5568")

    _update_scene(scene)
    return scene


def render_validation_log(
    entries: Iterable[dict[str, Any]],
    *,
    pyvista_module: Any | None = None,
    plotter: Any | None = None,
) -> Any:
    """Render a validation log and return the plotter for backward compatibility."""
    scene = build_scene(entries, pyvista_module=pyvista_module, plotter=plotter)
    return scene["plotter"]


def _default_file_dialog() -> str | None:
    try:
        import tkinter
        from tkinter import filedialog
    except Exception:
        return None

    root = tkinter.Tk()
    root.withdraw()
    selected = filedialog.askopenfilename(
        title="Open HF_Sim replay log",
        filetypes=[("JSONL", "*.jsonl"), ("JSON", "*.json")],
    )
    root.destroy()
    return selected or None


def _default_screenshot_path(controller: PlaybackController) -> Path:
    if controller.loaded_path is not None:
        source = Path(controller.loaded_path)
        return source.with_name(f"{source.stem}_screenshot.png")
    return Path.cwd() / "hf_sim_replay_screenshot.png"


def launch_replay_viewer(
    *,
    input_path: str | Path | None = None,
    entries: Iterable[dict[str, Any]] | None = None,
    pyvista_module: Any | None = None,
    plotter: Any | None = None,
    file_dialog_factory: Callable[[], str | None] | None = None,
    screenshot_path: str | Path | None = None,
    off_screen: bool = False,
) -> dict[str, Any]:
    """Launch or configure the offline replay viewer workbench."""
    if input_path is None and entries is None:
        raise ValueError("input_path or entries required")

    records = list(entries) if entries is not None else load_validation_log_jsonl(input_path)  # type: ignore[arg-type]
    scene = build_scene(records, pyvista_module=pyvista_module, plotter=plotter, off_screen=off_screen)
    controller: PlaybackController = scene["controller"]
    if input_path is not None:
        controller.loaded_path = str(Path(input_path))

    plot = scene["plotter"]
    chooser = file_dialog_factory or _default_file_dialog

    def refresh() -> dict[str, Any]:
        return _update_scene(scene)

    def on_play_toggle(*_: Any) -> bool:
        controller.toggle_play()
        refresh()
        return controller.is_playing

    def on_step_forward(*_: Any) -> dict[str, Any]:
        controller.step_forward()
        return refresh()

    def on_step_backward(*_: Any) -> dict[str, Any]:
        controller.step_backward()
        return refresh()

    def on_seek(value: float) -> dict[str, Any]:
        controller.seek(int(round(value)))
        return refresh()

    def on_speed(value: float) -> float:
        controller.set_playback_speed(float(value))
        refresh()
        return controller.playback_speed

    def on_branch(value: float) -> dict[str, Any]:
        controller.branch_at_index(int(round(value)))
        return refresh()

    def on_reset_camera(*_: Any) -> None:
        if hasattr(plot, "reset_camera"):
            plot.reset_camera()
        refresh()

    def on_export_screenshot(*_: Any) -> str:
        target = Path(screenshot_path) if screenshot_path is not None else _default_screenshot_path(controller)
        if hasattr(plot, "screenshot"):
            plot.screenshot(str(target))
        return str(target)

    def on_open_file(*_: Any) -> str | None:
        selected = chooser()
        if selected:
            controller.load_path(selected)
            refresh()
            return selected
        return None

    scene["callbacks"] = {
        "toggle_play": on_play_toggle,
        "step_forward": on_step_forward,
        "step_backward": on_step_backward,
        "seek": on_seek,
        "set_speed": on_speed,
        "select_branch": on_branch,
        "reset_camera": on_reset_camera,
        "export_screenshot": on_export_screenshot,
        "open_file": on_open_file,
        "refresh": refresh,
    }

    if hasattr(plot, "add_key_event"):
        plot.add_key_event("space", lambda: on_play_toggle())
        plot.add_key_event("Right", lambda: on_step_forward())
        plot.add_key_event("Left", lambda: on_step_backward())
        plot.add_key_event("o", lambda: on_open_file())
        plot.add_key_event("s", lambda: on_export_screenshot())
        plot.add_key_event("r", lambda: on_reset_camera())

    if hasattr(plot, "add_slider_widget"):
        branch_entries = controller.current_branch_entries()
        n_steps = max(0, len(branch_entries) - 1)

        # Timeline slider — full width, bottom strip
        plot.add_slider_widget(
            on_seek,
            [0, n_steps],
            value=0,
            title="Timeline",
            pointa=(0.05, 0.07),
            pointb=(0.70, 0.07),
        )

        # Playback speed slider — compact, right side
        plot.add_slider_widget(
            on_speed,
            [0.1, 8.0],
            value=controller.playback_speed,
            title="Speed",
            pointa=(0.75, 0.07),
            pointb=(0.95, 0.07),
        )

        # Branch slider — only if multiple branches present
        if len(controller.branches) > 1:
            plot.add_slider_widget(
                on_branch,
                [0, len(controller.branches) - 1],
                value=0,
                title="Branch",
                pointa=(0.75, 0.02),
                pointb=(0.95, 0.02),
            )

    return scene

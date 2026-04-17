"""Offline PyVista replay viewer helpers for validation logs."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable


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


def _summary_lines(entry: dict[str, Any], controller: PlaybackController) -> list[str]:
    ownship = entry.get("ownship", {})
    control = entry.get("control", {})
    sensor = entry.get("sensor", {})
    radar = entry.get("radar", {})
    derived = entry.get("derived_metrics", {})
    return [
        f"branch={entry.get('branch_id', controller.current_branch)} step={entry.get('step_index', 0)} sim_t={entry.get('sim_time_s', 0.0):.2f}s",
        (
            "alt={alt:.1f}m speed={speed:.2f}mps roll={roll:.1f}deg pitch={pitch:.1f}deg heading={heading:.1f}deg"
        ).format(
            alt=float(ownship.get("altitude_m", _position(entry)[2])),
            speed=float(ownship.get("speed_mps", 0.0)),
            roll=float(ownship.get("roll_deg", 0.0)),
            pitch=float(ownship.get("pitch_deg", 0.0)),
            heading=float(ownship.get("heading_deg", derived.get("heading_deg", 0.0))),
        ),
        (
            "thr={thr:.2f} roll={roll:.2f} pitch={pitch:.2f} yaw={yaw:.2f} nz={nz:.2f}"
        ).format(
            thr=float(control.get("throttle", 0.0)),
            roll=float(control.get("body_rate_cmd_rps", [0.0, 0.0, 0.0])[0]),
            pitch=float(control.get("body_rate_cmd_rps", [0.0, 0.0, 0.0])[1]),
            yaw=float(control.get("body_rate_cmd_rps", [0.0, 0.0, 0.0])[2]),
            nz=float(control.get("load_factor_cmd", 1.0)),
        ),
        (
            "sensor_q={quality:.3f} contacts={contacts} radar_tracks={tracks} nearest_threat={nearest:.1f}m"
        ).format(
            quality=float(sensor.get("quality", 0.0)),
            contacts=int(sensor.get("contact_count", 0)),
            tracks=int(radar.get("track_count", len(radar.get("track_ids", [])))),
            nearest=float(derived.get("nearest_threat_distance_m", 0.0)),
        ),
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


def _set_text(plotter: Any, scene: dict[str, Any], lines: list[str]) -> None:
    if not hasattr(plotter, "add_text"):
        return
    if hasattr(plotter, "remove_actor") and scene.get("text_actor") is not None:
        try:
            plotter.remove_actor(scene["text_actor"])
        except Exception:
            pass
    scene["text_actor"] = plotter.add_text("\n".join(lines), position="upper_left", font_size=10)


def _update_scene(scene: dict[str, Any]) -> dict[str, Any]:
    plotter = scene["plotter"]
    pv = scene["pyvista"]
    controller: PlaybackController = scene["controller"]
    entry = controller.current_entry()
    branch_entries = controller.current_branch_entries()
    actors = scene["actors"]

    points = [_position(row) for row in branch_entries]
    _add_mesh(plotter, actors, "trajectory_points", pv.PolyData(points), color="cyan", point_size=6)
    if len(points) >= 2 and hasattr(pv, "Spline"):
        _add_mesh(plotter, actors, "trajectory_spline", pv.Spline(points, max(2, len(points) * 4)), color="yellow", line_width=3)

    current_position = _position(entry)
    _add_mesh(plotter, actors, "current_pose", pv.PolyData([current_position]), color="red", point_size=14)

    velocity = _velocity(entry)
    if hasattr(pv, "Arrow"):
        _add_mesh(plotter, actors, "velocity_arrow", pv.Arrow(start=current_position, direction=velocity), color="orange")

    terrain_reference = _terrain_reference(entry)
    terrain_points = [[index * 100.0, 0.0, float(height)] for index, height in enumerate(terrain_reference)]
    if terrain_points:
        _add_mesh(plotter, actors, "terrain", pv.PolyData(terrain_points), color="tan", point_size=10)

    threat_positions = _threat_positions(entry)
    if threat_positions:
        _add_mesh(plotter, actors, "threat_markers", pv.PolyData(threat_positions), color="magenta", point_size=12)

    wind_vector = _wind_vector(entry)
    if hasattr(pv, "Arrow") and any(abs(value) > 1e-9 for value in wind_vector):
        _add_mesh(plotter, actors, "wind_arrow", pv.Arrow(start=current_position, direction=wind_vector), color="green")

    _set_text(plotter, scene, _summary_lines(entry, controller))
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
    scene = {
        "pyvista": pv,
        "plotter": plot,
        "controller": controller,
        "actors": {},
        "text_actor": None,
    }
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
        plot.add_key_event("space", on_play_toggle)
        plot.add_key_event("Right", on_step_forward)
        plot.add_key_event("Left", on_step_backward)
        plot.add_key_event("o", on_open_file)
        plot.add_key_event("s", on_export_screenshot)
        plot.add_key_event("r", on_reset_camera)

    if hasattr(plot, "add_slider_widget"):
        branch_entries = controller.current_branch_entries()
        plot.add_slider_widget(on_seek, [0, max(0, len(branch_entries) - 1)], value=0, title="step")
        plot.add_slider_widget(on_speed, [0.1, 8.0], value=controller.playback_speed, title="speed")
        if len(controller.branches) > 1:
            plot.add_slider_widget(on_branch, [0, len(controller.branches) - 1], value=0, title="branch")

    if hasattr(plot, "add_checkbox_button_widget"):
        plot.add_checkbox_button_widget(lambda value: on_play_toggle(), value=controller.is_playing)
        plot.add_checkbox_button_widget(lambda value: on_open_file(), value=False)
        plot.add_checkbox_button_widget(lambda value: on_export_screenshot(), value=False)
        plot.add_checkbox_button_widget(lambda value: on_reset_camera(), value=False)

    return scene

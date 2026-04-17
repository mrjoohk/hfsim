import json
from pathlib import Path

from hf_sim.pyvista_viewer import (
    PlaybackController,
    build_scene,
    launch_replay_viewer,
    load_validation_log_jsonl,
    render_validation_log,
)


class _FakePolyData:
    def __init__(self, points):
        self.points = points


class _FakeSpline:
    def __init__(self, points, segments):
        self.points = points
        self.segments = segments


class _FakeArrow:
    def __init__(self, start, direction):
        self.start = start
        self.direction = direction


class _FakePlotter:
    def __init__(self, off_screen=True):
        self.off_screen = off_screen
        self.meshes = []
        self.texts = []
        self.key_events = {}
        self.slider_widgets = []
        self.checkbox_widgets = []
        self.removed = []
        self.camera_reset = 0
        self.screenshots = []

    def add_mesh(self, mesh, **kwargs):
        actor = {"mesh": mesh, "kwargs": kwargs}
        self.meshes.append(actor)
        return actor

    def add_text(self, text, **kwargs):
        actor = {"text": text, "kwargs": kwargs}
        self.texts.append(actor)
        return actor

    def add_key_event(self, key, callback):
        self.key_events[key] = callback

    def add_slider_widget(self, callback, rng, value=0, title=""):
        self.slider_widgets.append({"callback": callback, "range": rng, "value": value, "title": title})

    def add_checkbox_button_widget(self, callback, value=False):
        self.checkbox_widgets.append({"callback": callback, "value": value})

    def remove_actor(self, actor):
        self.removed.append(actor)

    def reset_camera(self):
        self.camera_reset += 1

    def screenshot(self, path):
        self.screenshots.append(path)


class _FakePyVista:
    PolyData = _FakePolyData
    Spline = _FakeSpline
    Arrow = _FakeArrow
    Plotter = _FakePlotter


def _entries():
    return [
        {
            "branch_id": "branch_0",
            "step_index": 0,
            "sim_time_s": 0.0,
            "ownship": {
                "position_m": [0.0, 0.0, 1000.0],
                "velocity_mps": [200.0, 0.0, 0.0],
                "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                "angular_rate_rps": [0.0, 0.0, 0.0],
                "speed_mps": 200.0,
                "altitude_m": 1000.0,
                "roll_deg": 0.0,
                "pitch_deg": 0.0,
                "heading_deg": 0.0,
            },
            "control": {"throttle": 0.5, "body_rate_cmd_rps": [0.0, 0.0, 0.0], "load_factor_cmd": 1.0},
            "environment": {"terrain_reference": [100.0, 120.0, 130.0]},
            "atmosphere": {"wind_vector_mps": [5.0, 0.0, 0.0], "wind_speed_mps": 5.0, "density_kgpm3": 1.1, "turbulence_level": 0.1},
            "sensor": {"quality": 0.9, "contact_count": 1},
            "radar": {"track_ids": ["th-1"], "track_count": 1},
            "threats": [{"identifier": "th-1", "position_m": [1000.0, 0.0, 1000.0], "distance_m": 1000.0}],
            "derived_metrics": {"nearest_threat_distance_m": 1000.0, "heading_deg": 0.0},
        },
        {
            "branch_id": "branch_0",
            "step_index": 1,
            "sim_time_s": 0.01,
            "ownship": {
                "position_m": [20.0, 0.0, 1005.0],
                "velocity_mps": [205.0, 0.0, 0.0],
                "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                "angular_rate_rps": [0.1, 0.0, 0.0],
                "speed_mps": 205.0,
                "altitude_m": 1005.0,
                "roll_deg": 1.0,
                "pitch_deg": 0.0,
                "heading_deg": 0.0,
            },
            "control": {"throttle": 0.8, "body_rate_cmd_rps": [0.1, 0.0, 0.0], "load_factor_cmd": 1.0},
            "environment": {"terrain_reference": [100.0, 120.0, 130.0]},
            "atmosphere": {"wind_vector_mps": [5.0, 0.0, 0.0], "wind_speed_mps": 5.0, "density_kgpm3": 1.1, "turbulence_level": 0.1},
            "sensor": {"quality": 0.85, "contact_count": 1},
            "radar": {"track_ids": ["th-1"], "track_count": 1},
            "threats": [{"identifier": "th-1", "position_m": [980.0, 0.0, 1000.0], "distance_m": 960.0}],
            "derived_metrics": {"nearest_threat_distance_m": 960.0, "heading_deg": 0.0},
        },
        {
            "branch_id": "branch_1",
            "step_index": 0,
            "sim_time_s": 0.0,
            "ownship": {
                "position_m": [0.0, 10.0, 1000.0],
                "velocity_mps": [190.0, 0.0, 0.0],
                "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                "angular_rate_rps": [0.0, 0.1, 0.0],
                "speed_mps": 190.0,
                "altitude_m": 1000.0,
                "roll_deg": 0.0,
                "pitch_deg": 1.0,
                "heading_deg": 5.0,
            },
            "control": {"throttle": 0.3, "body_rate_cmd_rps": [0.0, 0.1, 0.0], "load_factor_cmd": 1.0},
            "environment": {"terrain_reference": [100.0, 120.0, 130.0]},
            "atmosphere": {"wind_vector_mps": [0.0, 2.0, 0.0], "wind_speed_mps": 2.0, "density_kgpm3": 1.1, "turbulence_level": 0.2},
            "sensor": {"quality": 0.8, "contact_count": 0},
            "radar": {"track_ids": [], "track_count": 0},
            "threats": [],
            "derived_metrics": {"nearest_threat_distance_m": 0.0, "heading_deg": 5.0},
        },
    ]


def test_render_validation_log_smoke():
    plotter = render_validation_log(_entries()[:2], pyvista_module=_FakePyVista)
    assert len(plotter.meshes) >= 4
    assert plotter.texts


def test_playback_controller_branch_navigation_and_seek():
    controller = PlaybackController(_entries())
    assert controller.current_entry()["branch_id"] == "branch_0"
    controller.step_forward()
    assert controller.current_entry()["step_index"] == 1
    controller.set_branch("branch_1")
    assert controller.current_entry()["branch_id"] == "branch_1"
    controller.seek(10)
    assert controller.current_index == 0
    controller.set_playback_speed(2.4)
    controller.set_branch("branch_0")
    controller.tick()
    assert controller.current_index == 1


def test_build_scene_returns_controller_and_plotter():
    scene = build_scene(_entries(), pyvista_module=_FakePyVista)
    assert scene["controller"].branches == ["branch_0", "branch_1"]
    assert scene["plotter"].texts
    assert scene["actors"]


def test_launch_replay_viewer_registers_callbacks_and_file_reload():
    input_path = Path.cwd() / "test_pyvista_replay.jsonl"
    screenshot_path = Path.cwd() / "test_pyvista_shot.png"
    try:
        input_path.write_text("\n".join(json.dumps(entry) for entry in _entries()[:2]), encoding="utf-8")
        scene = launch_replay_viewer(
            entries=_entries()[:2],
            pyvista_module=_FakePyVista,
            plotter=_FakePlotter(),
            file_dialog_factory=lambda: str(input_path),
            screenshot_path=screenshot_path,
            off_screen=True,
        )
        callbacks = scene["callbacks"]
        callbacks["step_forward"]()
        assert scene["controller"].current_index == 1
        callbacks["step_backward"]()
        assert scene["controller"].current_index == 0
        callbacks["open_file"]()
        assert scene["controller"].loaded_path == str(input_path)
        shot = callbacks["export_screenshot"]()
        assert shot.endswith("test_pyvista_shot.png")
        assert scene["plotter"].screenshots
        callbacks["reset_camera"]()
        assert scene["plotter"].camera_reset == 1
    finally:
        input_path.unlink(missing_ok=True)
        screenshot_path.unlink(missing_ok=True)


def test_load_validation_log_jsonl_round_trip():
    input_path = Path.cwd() / "test_pyvista_roundtrip.jsonl"
    try:
        input_path.write_text("\n".join(json.dumps(entry) for entry in _entries()[:2]), encoding="utf-8")
        rows = load_validation_log_jsonl(input_path)
        assert len(rows) == 2
        assert rows[0]["branch_id"] == "branch_0"
    finally:
        input_path.unlink(missing_ok=True)

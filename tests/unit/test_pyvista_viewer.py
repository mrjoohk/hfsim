from hf_sim.pyvista_viewer import render_validation_log


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

    def add_mesh(self, mesh, **kwargs):
        self.meshes.append((mesh, kwargs))

    def add_text(self, text, **kwargs):
        self.texts.append((text, kwargs))


class _FakePyVista:
    PolyData = _FakePolyData
    Spline = _FakeSpline
    Arrow = _FakeArrow
    Plotter = _FakePlotter


def test_render_validation_log_smoke():
    plotter = render_validation_log(
        [
            {
                "ownship": {"position_m": [0.0, 0.0, 1000.0]},
                "environment": {"terrain_reference": [100.0, 120.0, 130.0]},
                "atmosphere": {"wind_vector_mps": [5.0, 0.0, 0.0]},
                "sensor": {"quality": 0.9},
            },
            {
                "ownship": {"position_m": [20.0, 0.0, 1005.0]},
                "environment": {"terrain_reference": [100.0, 120.0, 130.0]},
                "atmosphere": {"wind_vector_mps": [5.0, 0.0, 0.0]},
                "sensor": {"quality": 0.85},
            },
        ],
        pyvista_module=_FakePyVista,
    )
    assert len(plotter.meshes) >= 3
    assert plotter.texts

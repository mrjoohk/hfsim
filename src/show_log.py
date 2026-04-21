from hf_sim.pyvista_viewer import launch_replay_viewer

scene = launch_replay_viewer(
    input_path="reports/manual_replay.jsonl",
    off_screen=False,
)
import pyvista as pv
pv.set_jupyter_backend("none")

scene["plotter"].show(jupyter_backend="none")

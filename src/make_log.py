import json
from pathlib import Path

import numpy as np

from hf_sim.env import HFSimEnv
from hf_sim.validation_logging import (
    build_replay_record,
    export_validation_log_jsonl,
    export_validation_log_parquet,
    export_validation_summary_csv,
)

env = HFSimEnv(seed=0, use_radar_obs=True)
obs, info = env.reset(seed=0)

records = []
action = np.array([0.6, 0.1, 0.0, 0.0, 1.0], dtype=np.float32)

for step_index in range(50):
    obs, reward, terminated, truncated, info = env.step(action)

    record = build_replay_record(
        env._runtime,
        {
            "throttle": float(action[0]),
            "roll": float(action[1]),
            "pitch": float(action[2]),
            "yaw": float(action[3]),
            "load_factor": float(action[4]),
        },
        step_index=step_index,
        branch_id="main",
        scenario_tags=["manual", "demo"],
    )
    records.append(record)

    if terminated or truncated:
        break

export_validation_log_jsonl(records, Path("reports/manual_replay.jsonl"))
export_validation_summary_csv(records, Path("reports/manual_replay.csv"))

try:
    export_validation_log_parquet(records, Path("reports/manual_replay.parquet"))
    print(f"[make_log] Exported {len(records)} steps → reports/manual_replay.{{jsonl,csv,parquet}}")
except RuntimeError as e:
    print(f"[make_log] Parquet skipped ({e})")
    print(f"[make_log] Exported {len(records)} steps → reports/manual_replay.{{jsonl,csv}}")

env.close()

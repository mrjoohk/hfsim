# HF_Sim 사용 매뉴얼

## 1. 개요

HF_Sim은 월드모델 학습 검증을 위한 물리 기반 시뮬레이션 환경입니다. 현재 사용 흐름은 크게 4가지입니다.

1. `HFSimEnv`로 Gymnasium 스타일 rollout 실행
2. validation log(JSONL/CSV) 생성
3. `PyVista` 기반 오프라인 replay viewer로 로그 재생
4. ownship fidelity gate와 benchmark로 동역학/성능 검증

이 문서는 위 4가지 흐름을 실제 코드 기준으로 바로 따라 할 수 있게 정리한 사용자 매뉴얼입니다.

---

## 2. 설치

### 2.1 기본 설치

프로젝트 루트에서 실행합니다.

```powershell
python -m pip install -r requirements.txt
```

### 2.2 선택 설치

`PyVista` viewer는 선택 기능입니다. 설치하지 않아도 core simulator와 테스트는 동작합니다.

```powershell
python -m pip install pyvista
```

`Ray`도 선택 기능입니다.

```powershell
python -m pip install "ray[default]"
```

---

## 3. 빠른 시작

가장 기본적인 사용법은 `HFSimEnv`를 reset/step 하는 것입니다.

```python
import numpy as np

from hf_sim.env import HFSimEnv

env = HFSimEnv(
    curriculum_level=0,
    max_steps=200,
    n_substeps=5,
    seed=0,
    use_radar_obs=True,
)

obs, info = env.reset(seed=0)
print("obs shape:", obs.shape)
print("sim_time_s:", info["sim_time_s"])

action = np.array([0.5, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)

for step in range(10):
    obs, reward, terminated, truncated, info = env.step(action)
    print(
        step,
        info["sim_time_s"],
        info["ownship"]["position_m"],
        reward,
        info["termination_reason"],
    )
    if terminated or truncated:
        break

env.close()
```

### 3.1 action 의미

`HFSimEnv.action_space`는 5차원입니다.

- `action[0]`: `throttle`
- `action[1]`: `roll_rate`
- `action[2]`: `pitch_rate`
- `action[3]`: `yaw_rate`
- `action[4]`: `load_factor`

기본 범위는 아래와 같습니다.

- `throttle`: `[0, 1]`
- 나머지: `[-1, 1]`

### 3.2 observation shape

- 기본: `16`차원
- `use_radar_obs=True`: `22`차원

추가 6채널은 radar/sensor 정보입니다.

---

## 4. 테스트 실행

전체 unit/integration 테스트:

```powershell
python -m pytest tests\unit tests\integration -q -p no:cacheprovider
```

특정 영역만 빠르게 확인:

```powershell
python -m pytest tests\unit\test_ownship_fidelity.py -q -p no:cacheprovider
python -m pytest tests\unit\test_pyvista_viewer.py -q -p no:cacheprovider
python -m pytest tests\integration\test_6dof_comparison.py -q -p no:cacheprovider
```

---

## 5. Validation Log 생성

viewer는 JSONL replay log를 입력으로 사용합니다. 가장 간단한 방법은 env rollout 중에 현재 runtime을 replay record로 저장하는 것입니다.

```python
import json
from pathlib import Path

import numpy as np

from hf_sim.env import HFSimEnv
from hf_sim.validation_logging import (
    build_replay_record,
    export_validation_log_jsonl,
    export_validation_summary_csv,
)

env = HFSimEnv(seed=0, use_radar_obs=True)
obs, info = env.reset(seed=0)

records = []
action = np.array([0.6, 0.1, 0.0, 0.0, 1.0], dtype=np.float32)

for step_index in range(50):
    obs, reward, terminated, truncated, info = env.step(action)

    record = build_replay_record(
        env._runtime,  # 현재 표준 로그 입력은 EnvironmentRuntime
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
env.close()
```

### 5.1 replay record에 들어가는 주요 필드

- `sim_time_s`, `branch_id`, `step_index`
- `ownship.position_m`, `velocity_mps`, `quaternion_wxyz`, `angular_rate_rps`
- `control.throttle`, `body_rate_cmd_rps`, `load_factor_cmd`
- `sensor`, `radar`, `atmosphere`, `environment`
- `derived_metrics`
- `acceptance_snapshot`

즉, viewer와 후처리에 필요한 정보가 한 레코드에 모두 들어갑니다.

---

## 6. Branch Rollout 로그 생성

branch rollout 결과는 `flatten_branch_runtime_result(...)`로 viewer용 표준 로그로 변환할 수 있습니다.

```python
from hf_sim.validation_logging import (
    export_validation_log_jsonl,
    flatten_branch_runtime_result,
)
from if.if03_snapshot import if_03_branch_snapshot_rollout
from hf_sim.models import BranchRolloutRequest

result = if_03_branch_snapshot_rollout(
    BranchRolloutRequest(
        runtime=env._runtime,
        runtime_source_spec={"source": "current", "k": 0},
        branch_mode="single_action_set",
        branch_controls=[
            {"throttle": 0.8, "roll": 0.2, "pitch": 0.1},
            {"throttle": 0.2, "roll": -0.2, "pitch": -0.1},
        ],
        horizon=50,
    )
)

rows = flatten_branch_runtime_result(result)
export_validation_log_jsonl(rows, "reports/branch_replay.jsonl")
```

이렇게 만든 JSONL은 branch별 playback이 가능합니다.

---

## 7. PyVista Replay Viewer 사용법

### 7.1 파일에서 바로 열기

```python
from hf_sim.pyvista_viewer import launch_replay_viewer

scene = launch_replay_viewer(
    input_path="reports/manual_replay.jsonl",
    off_screen=False,
)
```

### 7.2 메모리의 records로 바로 열기

```python
from hf_sim.pyvista_viewer import launch_replay_viewer

scene = launch_replay_viewer(
    entries=records,
    off_screen=False,
)
```

### 7.3 제공 기능

- 파일 불러오기: `open_file`
- 재생/일시정지: `toggle_play`
- 한 step 전진/후진: `step_forward`, `step_backward`
- scrub slider: step 이동
- playback speed 조절
- branch 선택
- camera reset
- screenshot export

`launch_replay_viewer(...)`는 scene dict를 반환합니다.

```python
controller = scene["controller"]
callbacks = scene["callbacks"]

callbacks["step_forward"]()
callbacks["set_speed"](2.0)
callbacks["select_branch"](1)
callbacks["export_screenshot"]()
```

### 7.4 기본 키 입력

가능한 plotter에서는 아래 키가 연결됩니다.

- `Space`: play/pause
- `Right`: 다음 step
- `Left`: 이전 step
- `o`: 파일 열기
- `s`: screenshot 저장
- `r`: camera reset

### 7.5 viewer overlay

기본적으로 아래 요소를 렌더링합니다.

- ownship trajectory
- current ownship pose
- velocity arrow
- terrain reference
- threat markers
- wind arrow
- 텍스트 요약 오버레이

텍스트 요약에는 아래 정보가 포함됩니다.

- 현재 branch / step / sim time
- altitude / speed / roll / pitch / heading
- throttle / roll / pitch / yaw / load factor
- sensor quality / contact count / radar tracks / nearest threat distance

---

## 8. Ownship Fidelity Gate 사용법

ownship fidelity gate는 조종 입력에 대한 상태 응답이 일관적인지 확인하는 도구입니다.

현재 helper는 `EnvironmentRuntime`를 입력으로 받습니다. 가장 간단한 시작점은 `HFSimEnv.reset()` 후 `env._runtime`을 baseline runtime으로 사용하는 것입니다.

```python
from hf_sim.env import HFSimEnv
from hf_sim.ownship_fidelity import run_ownship_fidelity_gate

env = HFSimEnv(seed=0)
env.reset(seed=0)

reports = run_ownship_fidelity_gate(env._runtime)

for report in reports:
    print(
        report.scenario_name,
        report.response_signal,
        report.initial_speed_mps,
        report.final_speed_mps,
        report.max_abs_angular_rate_rps,
        report.quaternion_norm_error_max,
        report.finite_state,
        report.monotonic_sim_time,
    )

env.close()
```

### 8.1 기본 maneuver 세트

- `straight_hold`
- `throttle_step`
- `pitch_doublet`
- `roll_doublet`
- `yaw_pulse`
- `load_factor_hold`
- `coordinated_turn_like`

### 8.2 주요 메트릭

- `initial_speed_mps`, `final_speed_mps`, `max_speed_mps`
- `max_abs_angular_rate_rps`
- `max_position_delta_m`
- `quaternion_norm_error_max`
- `energy_like_drift`
- `response_latency_steps`
- `overshoot`
- `steady_state_drift`
- `finite_state`
- `monotonic_sim_time`

---

## 9. Euler vs RK4 Regression Suite 사용법

reference model 기반 trajectory regression은 `src/uf/reference_dynamics.py`에 있습니다.

```python
from hf_sim.models import AtmosphereState, OwnshipState
from uf.reference_dynamics import run_maneuver_regression_suite

ownship = OwnshipState(
    position_m=[0.0, 0.0, 1000.0],
    velocity_mps=[200.0, 0.0, 0.0],
    quaternion_wxyz=[1.0, 0.0, 0.0, 0.0],
    angular_rate_rps=[0.0, 0.0, 0.0],
    mass_kg=9000.0,
    aero_params={"drag_coeff": 0.02, "max_thrust_n": 20000.0, "lift_gain": 9.0},
)

atmosphere = AtmosphereState(
    density_kgpm3=1.225,
    wind_vector_mps=[5.0, 0.0, 0.0],
    turbulence_level=0.1,
)

report = run_maneuver_regression_suite(
    initial_ownship=ownship,
    atmosphere=atmosphere,
    dt=0.01,
)

for result in report.scenario_results:
    print(
        result.maneuver_name,
        result.mean_position_error_m,
        result.peak_position_error_m,
        result.mean_velocity_error_mps,
        result.peak_velocity_error_mps,
    )
```

이 리포트는 production Euler 적분과 RK4 reference 적분의 차이를 maneuver별로 요약합니다.

---

## 10. Benchmark 사용법

60x time acceleration 추적은 `hf_sim.benchmark`로 수행합니다.

```python
from hf_sim.benchmark import BenchmarkConfig, run_benchmark

result = run_benchmark(
    BenchmarkConfig(
        n_workers=4,
        sim_duration_s=600.0,
        n_substeps=5,
        seed=42,
    )
)

print(result.to_dict())
print("passes_60x =", result.passes_60x)
print("mean_acceleration =", result.mean_acceleration)
print("min_acceleration =", result.min_acceleration)
```

짧게 빠르게 확인하려면:

```python
result = run_benchmark(BenchmarkConfig(n_workers=1, sim_duration_s=5.0, seed=0))
print(result.to_dict())
```

---

## 11. Local Worker / Logger 사용법

`Ray` 없이도 `LocalEnvWorker`와 `LocalLoggerWorker`를 사용할 수 있습니다.

```python
import numpy as np

from hf_sim.ray_runtime import LocalEnvWorker, LocalLoggerWorker

worker = LocalEnvWorker(env_kwargs={"seed": 0, "use_radar_obs": True})
logger = LocalLoggerWorker()

worker.reset(seed=0)
actions = [np.array([0.5, 0.0, 0.0, 0.0, 1.0], dtype=np.float32) for _ in range(20)]
result = worker.step_chunk(actions)

entry = logger.build_runtime_entry(
    worker,
    {"throttle": 0.5, "roll": 0.0, "pitch": 0.0, "yaw": 0.0, "load_factor": 1.0},
    step_index=0,
    branch_id="main",
)

logger.export_runtime_chunk_logs(
    [entry],
    jsonl_path="reports/worker_log.jsonl",
    csv_path="reports/worker_log.csv",
)

worker.close()
```

---

## 12. 자주 겪는 문제

### 12.1 `ModuleNotFoundError: pyvista is required for offline visualization`

`PyVista`가 설치되지 않은 상태입니다.

```powershell
python -m pip install pyvista
```

### 12.2 viewer는 열리는데 아무 것도 안 보임

- 입력 JSONL이 비어 있지 않은지 확인합니다.
- `branch_id`가 여러 개면 올바른 branch를 선택했는지 확인합니다.
- 로그 레코드에 `ownship.position_m` 또는 `ownship_position_m`이 들어 있는지 확인합니다.

### 12.3 fidelity gate 입력 runtime을 어떻게 만들지 모르겠음

현재 가장 쉬운 방법은 아래와 같습니다.

```python
env = HFSimEnv(seed=0)
env.reset(seed=0)
runtime = env._runtime
```

이 값으로 `run_ownship_fidelity_gate(runtime)`를 호출하면 됩니다.

### 12.4 Windows에서 `tmp_path` 관련 권한 문제가 보임

이 프로젝트는 일부 Windows 환경에서 시스템 temp 디렉터리 접근 제한이 있을 수 있습니다. 테스트나 실험용 파일은 가급적 repo 내부 경로(`reports/`, 현재 작업 디렉터리 등)에 쓰는 것을 권장합니다.

---

## 13. 추천 사용 순서

가장 실용적인 순서는 아래입니다.

1. `HFSimEnv`로 기본 rollout 확인
2. `build_replay_record(...)`로 JSONL log 저장
3. `launch_replay_viewer(...)`로 궤적/자세/위협/바람 시각 확인
4. `run_ownship_fidelity_gate(...)`로 조종 응답 메트릭 확인
5. `run_maneuver_regression_suite(...)`로 Euler vs RK4 차이 확인
6. `run_benchmark(...)`로 성능 회귀 확인
7. 그 다음에 threat/radar, weather 시나리오를 확장

---

## 14. 관련 파일

- 환경 wrapper: [env.py](/C:/Users/user/Desktop/AI_workspace/hfsim/src/hf_sim/env.py)
- replay logging: [validation_logging.py](/C:/Users/user/Desktop/AI_workspace/hfsim/src/hf_sim/validation_logging.py)
- PyVista viewer: [pyvista_viewer.py](/C:/Users/user/Desktop/AI_workspace/hfsim/src/hf_sim/pyvista_viewer.py)
- ownship fidelity gate: [ownship_fidelity.py](/C:/Users/user/Desktop/AI_workspace/hfsim/src/hf_sim/ownship_fidelity.py)
- regression reference: [reference_dynamics.py](/C:/Users/user/Desktop/AI_workspace/hfsim/src/uf/reference_dynamics.py)
- benchmark: [benchmark.py](/C:/Users/user/Desktop/AI_workspace/hfsim/src/hf_sim/benchmark.py)


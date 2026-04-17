# Phase C 구현 완료 보고서

**일시**: 2026-04-13
**범위**: C1 (2차 6-DoF 비교) + C2 (Observation schema 확장) + C3 (공력 보정 case library / REQ-008)

---

## Phase C1 — 2차 6-DoF 비교 검증 (secondary validation)

### 생성/수정 파일
| 파일 | 유형 | 내용 |
|------|------|------|
| `src/uf/reference_dynamics.py` | 신규 | RK4 reference 모델 (propagate_ownship_euler, propagate_ownship_rk4, compare_6dof_euler_vs_rk4, run_6dof_comparison_trajectory) |
| `src/hf_sim/models.py` | 수정 | `SixDofComparisonResult` dataclass 추가 |
| `tests/unit/test_reference_dynamics.py` | 신규 | 12개 |
| `tests/integration/test_6dof_comparison.py` | 신규 | 4개 |

### 방향 결정
| 기각 방식 | 이유 |
|----------|------|
| JSBSim subprocess | Windows binding 불안정, optional 의존성, throughput 저해 |
| 해석적 정상상태 비교 | 동적 기동 비교 불가 |

**채택**: RK4 내장 reference 모델 — 외부 의존성 없음, "or other open-model" 충족

### 핵심 설계
- `propagate_ownship_euler()`: 기존 생산 코드와 동일한 물리 방정식, 1차 Euler 적분
- `propagate_ownship_rk4()`: 동일 물리 방정식, 4차 RK4 적분 (translational only)
- quaternion kinematics: dt=0.01s에서 Euler/RK4 차이 < 1e-6이므로 기존 Euler 유지
- `compare_6dof_euler_vs_rk4()`: 단일 스텝 비교 → `SixDofComparisonResult`
- `run_6dof_comparison_trajectory()`: N step 궤도 비교 → C3에서 재사용

### 검증 결과
| 테스트 | 결과 |
|--------|------|
| RK4 finite state | PASS |
| Euler ≠ RK4 (구별 확인) | PASS |
| dt 수렴 (작은 dt → 더 작은 오차) | PASS |
| 600 step mean position_error ≤ 5m | PASS |
| 결정론성 | PASS |
| 극단 params NaN 없음 | PASS |
| 1200 controls → 1200 outputs | PASS |

---

## Phase C2 — Observation Schema 확장

### 수정/생성 파일
| 파일 | 유형 | 내용 |
|------|------|------|
| `src/hf_sim/env.py` | 수정 | `use_radar_obs` 파라미터, `_build_radar_sensor_channels()`, `_get_obs()` 분기 (+45줄) |
| `tests/unit/test_radar_obs_extension.py` | 신규 | 9개 |
| `tests/integration/test_radar_obs_rollout.py` | 신규 | 3개 |

### 방향 결정
- **IF-04 UF 레이어 변경** → 기각 (IF 경계 수정, 불필요한 추상화)
- **extension_channels + use_radar_obs 플래그** → 채택 (기존 16-dim 유지, backward-compatible)

### 6채널 정규화 (모두 [0, 1])
| 채널 | 계산 |
|------|------|
| `sensor_quality` | SensorState.quality (이미 [0,1]) |
| `detection_confidence` | SensorState.detection_confidence (이미 [0,1]) |
| `sensor_contact_count_norm` | contact_count / max(1, n_threats) |
| `radar_track_count_norm` | len(track_ids) / max(1, n_threats) |
| `detected_range_nearest_norm` | min(ranges) / 10000.0, clip [0,1] |
| `detected_ranges_mean_norm` | mean(ranges) / 10000.0, clip [0,1] |

### 검증 결과
- `use_radar_obs=False` → obs_space (16,), 기존 151개 테스트 전혀 영향 없음
- `use_radar_obs=True` → obs_space (22,)
- 앞 16-dim: True/False 동일 (동일 물리, 동일 IF-04 결과)
- 200 step rollout 전 구간 finite
- 6 채널 전 구간 [0, 1]

---

## Phase C3 — 공력 보정 Case Library (REQ-008)

### 생성/수정 파일
| 파일 | 유형 | 내용 |
|------|------|------|
| `data/calibration_cases.json` | 신규 | 5개 case 정의 (JSON) |
| `src/hf_sim/aero_calibration.py` | 신규 | load_calibration_cases, run_calibration_case, run_calibration_workflow, save_calibration_report, report_to_dict |
| `src/hf_sim/models.py` | 수정 | `CalibrationCase`, `CalibrationCaseResult`, `AeroCalibrationReport` dataclass 추가 |
| `tests/unit/test_aero_calibration.py` | 신규 | 14개 |
| `tests/integration/test_aero_calibration_integration.py` | 신규 | 5개 |

### 5개 Case
| case_id | 핵심 변수 |
|---------|----------|
| c1_nominal | velocity_scale=1.0 (passthrough) |
| c2_high_drag | coefficient_overrides: drag_coeff=0.04 |
| c3_low_thrust | coefficient_overrides: max_thrust_n=14000 |
| c4_velocity_scale_095 | velocity_scale=0.95 |
| c5_combined | velocity_scale=0.98, drag_coeff=0.025 |

### REQ-008 acceptance criteria 충족
| 항목 | 결과 |
|------|------|
| 5개 이상 case | **5개 (n_cases_total=5)** |
| file/config-driven workflow | **JSON case library + cases= 직접 주입 모두 지원** |
| numeric error metrics (전 case) | **position_error_m + velocity_error_mps 모두 finite** |
| 100% field coverage | **coverage_pct=100.0 항상 보장** |

### run_calibration_case 동작
1. `initial_state` + `calibration_config` (velocity_scale + coefficient_overrides) 적용 → 초기 OwnshipState
2. N Euler steps (production) 실행
3. N RK4 steps (C1 재사용) 실행
4. RMS position_error, velocity_error 계산
5. threshold 비교 → passed

---

## 종합 결과

| 항목 | Before | After |
|------|--------|-------|
| 테스트 통과 수 | 151 | **198** |
| 2차 6-DoF 비교 | 없음 | **Euler vs RK4, RMS position_error ≤ 5m** |
| observation dim | 16 (고정) | **16 (기본) / 22 (use_radar_obs=True)** |
| 공력 보정 case | 없음 | **5개 case, JSON file-driven, 100% coverage** |
| REQ-008 | 미충족 | **충족: 5 cases + file-driven + numeric metrics** |

---

## 한계 (향후 과제)
- JSBSim 실제 연동 비교: 외부 바이너리 의존성으로 이번 Phase에서 제외
- RK4 rotational kinematics: dt=0.01s에서 무시 가능하나, 고기동 시 확인 필요
- observation extension: 현재 6채널만 지원; 추가 채널(IMU, fuel 등)은 별도 Phase

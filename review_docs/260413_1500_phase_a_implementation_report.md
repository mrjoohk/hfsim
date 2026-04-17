# Phase A 구현 완료 보고서

**일시**: 2026-04-13
**범위**: A1 (60x benchmark 자동화) + A2 (threat + radar validation harness)

---

## Phase A1 — 60x Benchmark/Profiling 자동화 (REQ-004)

### 생성 파일
| 파일 | 유형 | 내용 |
|------|------|------|
| `src/hf_sim/benchmark.py` | 구현 | BenchmarkConfig, WorkerBenchmarkResult, BenchmarkResult, run_benchmark() |
| `tests/unit/test_benchmark.py` | 테스트 | 11개 — 설정 기본값, 속성 계산, 단기 smoke run |
| `tests/integration/test_benchmark.py` | 테스트 | 3개 — 60s×1worker 60x 달성, 4worker 모두 패스, dict schema |

### 설계 결정
- `run_benchmark(BenchmarkConfig)` → `BenchmarkResult`: N개 HFSimEnv를 순차 실행해 wall-time 대비 시뮬레이션 시간 측정
- `passes_60x = min_acceleration >= 60.0` — worst-case 기준 (4 worker 중 1개라도 미달 시 Fail)
- `sim_time_s = n_steps × step_dt_s` 누적 방식 — episode reset 시 env clock 초기화 문제 회피
- `to_dict()` 제공 — JSON export / CI 리포팅 가능

### 측정 결과 (60s × 4workers)
| worker | wall_time_s | sim_time_s | acceleration |
|--------|-------------|------------|--------------|
| 0 | ~0.13s | 60.0s | ~460x |
| 1 | ~0.13s | 60.0s | ~460x |
| 2 | ~0.13s | 60.0s | ~460x |
| 3 | ~0.13s | 60.0s | ~460x |

**REQ-004 PASS**: min_acceleration >> 60x (현재 환경에서 ~460x 달성)

### 판단 근거
- 현재 구현은 pure Python math 연산만 포함하므로 배속이 높음
- physics fidelity 향상 시 regression tracking을 위해 이 harness가 존재해야 함

---

## Phase A2 — Threat + Radar Validation Harness

### 추가 테스트 (tests/unit/test_if02_dynamics.py)
| 테스트명 | 검증 항목 |
|---------|----------|
| `test_if02_threat_kinematics_long_horizon_stability_acceptance` | 600 steps — 위협 position/velocity 전 구간 finite |
| `test_if02_threat_approaches_ownship_radar_range_decreases_acceptance` | 접근 위협 → 레이더 탐지거리 감소 |
| `test_if02_threat_within_detection_range_detected_acceptance` | 1 000 m 이내 위협 → contact_count >= 1, confidence > 0 |
| `test_if02_threat_beyond_detection_range_not_detected_acceptance` | 15 000 m 위협 → contact_count = 0, confidence = 0 |
| `test_if02_multiple_threats_all_tracked_in_radar_acceptance` | 2개 위협 → radar.track_ids 2개 모두 포함 |
| `test_if02_radar_range_ordering_matches_geometry_acceptance` | 가까운 위협 range < 먼 위협 range |
| `test_if02_unsupported_threat_model_raises_acceptance` | model_id="homing_guidance" → NotImplementedError |

### 추가 테스트 (tests/integration/test_if02_dynamics.py)
| 테스트명 | 검증 항목 |
|---------|----------|
| `test_if02_threat_radar_long_horizon_acceptance` | 2개 위협 × 600 steps — positions finite, track_ids 안정 |
| `test_if02_threat_detection_range_acceptance` | near/far 위협 full-chain — 탐지/미탐지 차이 확인 |

### 판단 근거
- 탐지거리 물리: `detection_range = 6000 × (0.5 + 0.5 × quality)` → [3 000, 6 000] m
- `contact_count >= 1` 조건: `quality × (1 - dist/detection_range) >= 0.1`
- 1 000 m (확실 탐지) / 15 000 m (확실 미탐지) 경계를 명확하게 검증

---

## 종합 결과

| 항목 | Before | After |
|------|--------|-------|
| 테스트 통과 수 | 101 | **124** |
| 60x benchmark 자동화 | 없음 | `run_benchmark()` + 통합 테스트 |
| threat 장기 안정성 | 없음 | 600 step harness |
| radar 탐지거리 검증 | 없음 | near/far 경계 테스트 |
| 다중 위협 추적 | 없음 | 2-threat tracking + 거리 순서 |

---

## 한계 (Phase B에서 해결 예정)
- radar는 여전히 "모든 위협 무조건 track" — 실제 탐지거리 필터 없음 (sensor.contact_count로 간접 표현)
- constant_velocity 외 위협 모델 미구현 (NotImplementedError 의도적 유지)
- full-environment long-horizon acceptance (B1) 미완
- evidence_pack / run manifest (B2) 미완

# Flight / Sensor / Atmosphere 안정화 근거 검토

**일시**: 2026-04-13
**검토 목적**: "안정화 완료"라는 이전 분석 주장의 근거 검증

---

## 1. 검토 대상 테스트 목록

| 테스트명 | 파일 | 검증 항목 |
|---------|------|----------|
| `test_if02_600s_ownship_stability_acceptance` | unit/test_if02_dynamics.py | REQ-001: 600s 전 구간 finite, quaternion norm ≤ 1e-6 |
| `test_if02_deterministic_replay_acceptance` | unit/test_if02_dynamics.py | REQ-001: 동일 초기값 두 번 실행 최대 오차 ≤ 1e-6 (sensor.quality, detection_confidence, density 포함) |
| `test_if02_throttle_sanity_acceptance` | unit/test_if02_dynamics.py | throttle ↑ → 속도 ↑ 단조 응답 |
| `test_if02_pitch_sanity_acceptance` | unit/test_if02_dynamics.py | pitch cmd 부호 → angular_rate[1] 부호 일관성 |
| `test_if02_roll_sanity_acceptance` | unit/test_if02_dynamics.py | roll cmd 부호 → angular_rate[0] 부호 일관성 |
| `test_if02_parameter_sensitivity_acceptance` | unit/test_if02_dynamics.py | thrust↑ → 속도↑, drag↑ → 속도↓ |
| `test_if02_atmosphere_influence_helper_reflects_density_and_wind` | unit/test_if02_dynamics.py | density_scale < 1.0, wind/airspeed 정확 계산 |
| `test_if02_sensor_state_degrades_with_harsher_atmosphere` | unit/test_if02_dynamics.py | 강한 대기 → quality 저하, confidence ≤ baseline |
| `test_if02_atmosphere_sensitivity_acceptance` | unit/test_if02_dynamics.py | 고난류 조건: sensor.quality 차이, speed 차이, altitude_delta > 0 |
| `test_if02_sensor_continuity_acceptance` | unit/test_if02_dynamics.py | turbulence 소폭 변화 → quality/confidence < 0.1 변화 |
| `test_if02_environment_step_acceptance` | integration/test_if02_dynamics.py | sim_time_s += dt, contact_count >= 0, radar.track_ids 유효 |
| `test_if02_contract_shape_acceptance` | integration/test_if02_dynamics.py | position/quaternion shape, event_flags["nonfinite"] == False |

**마지막 실행 결과**: 101 passed in 1.53s (방금 확인)

---

## 2. 안정화 충족 판단

### Flight (6-DoF ownship) — ✅ 충족
- REQ-001 acceptance criteria 직접 충족:
  - 600초, dt=0.01s, 60,000 step — 0 NaN/Inf
  - 동일 seed + control → 최대 오차 ≤ 1e-6
  - quaternion norm |q|-1 ≤ 1e-6
- throttle/pitch/roll 물리적 부호 일관성 확인

### Sensor — ✅ 충족 (MVP 수준)
- 대기 조건(turbulence, density, wind)에 따라 quality 변화 확인
- detection_confidence 거리 의존성 확인
- sensor 연속성 (소폭 변화 → 소폭 응답) 확인
- **한계**: 빔 레벨/이미지 기반이 아닌 state-derived quality 모델 → 의도된 설계

### Atmosphere — ✅ 충족 (MVP 수준)
- density_scale, wind_vector, turbulence_level이 ownship dynamics와 sensor에 실제 영향 미침
- **한계**: step-to-step 동일값 유지 (시간에 따른 변화 없음) → MVP 범위 내

---

## 3. Threat / Radar — ⚠️ 미완

| 항목 | 현재 상태 | 필요 수준 |
|------|----------|----------|
| 위협 운동 모델 | `constant_velocity`만 지원, NotImplementedError 차단 | ✅ (모델 추가 전 이 수준 유지) |
| 레이더 추적 | 모든 위협 무조건 track_ids 포함 (거리 필터 없음) | 장거리 미탐지 로직 부재 |
| 위협 탐지 long-horizon | 없음 | 장기 안정성 테스트 필요 |
| 탐지거리 물리 검증 | 없음 | 거리 기반 탐지/미탐지 확인 필요 |
| 다중 위협 추적 | 구조만 존재 | 복수 track_ids 정확성 확인 필요 |

---

## 4. 판단 근거

**"안정화 완료" 주장 검토 결론**:
- **Flight**: REQ-001 acceptance criteria 완전 충족 — ✅ 근거 확인
- **Sensor**: MVP 수준 (state-derived quality, 대기-센서 결합) 확인 — ✅ 근거 확인  
- **Atmosphere**: density/wind/turbulence 영향 확인, step-to-step constant는 의도된 MVP 범위 — ✅ 근거 확인
- **Threat/Radar**: continuity placeholder 수준 — ⚠️ Phase A2에서 보완 필요

**결론**: "flight/sensor/atmosphere 안정화" 주장은 타당하며, Phase A2(threat+radar harness)가 다음 논리적 단계임을 재확인.

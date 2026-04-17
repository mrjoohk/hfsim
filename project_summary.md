# HF_Sim — Project Summary

> **목적**: 월드모델 학습 가능성을 빠르게 검증하기 위한 물리 일관성 기반 시뮬레이션 환경의 설계·구현 요약
> **기간**: 2026-04-08 ~ 진행 중
> **최종 업데이트**: 2026-04-17

---

## 1. 프로젝트 개요

- **배경**: 목표는 고충실 디지털트윈 완성이 아니라, 월드모델이 학습 가능한지와 병렬 rollout/시간 배속이 실용적인지를 검증하는 것이다.
- **목표**: `6-DoF ownship`, `snapshot/branch rollout`, `structured observation`, `4-agent baseline`, `60x benchmark`를 중심으로 MVP를 설계하고 구현하는 것이다.
- **핵심 철학**: learnability, determinism, throughput의 균형 — realism-max 는 아니다.

---

## 2. 아키텍처 요약

```
ExecutionRequest (사용자 입력)
        ↓ IF-01 (Orchestration)
ExecutionBundle (scenario + rollout plan)
        ↓
HFSimEnv (Gymnasium wrapper)
        ↓
EnvironmentRuntime  ← ownship(6-DoF) / threats / targets / radar / sensor / atmosphere
        ↓ step × N
    IF-02 (Dynamics) → IF-04 (Observation) → reward / termination
        ↓ (optional)
    IF-03 (Snapshot Branch Rollout)
        ↓ (episode end)
    IF-05 (Evaluation & Reporting)
```

**레이어 구조**

| 레이어 | 경로 | 역할 |
|--------|------|------|
| 스키마 | `src/hf_sim/models.py` | 52개 dataclass — 모든 I/O 계약 정의 |
| IF 계층 | `src/if/if0X_*.py` | UF 체인 진입점 (5개 통합 함수) |
| UF 계층 | `src/uf/if0X_*.py` | 핵심 로직 구현 (30개 단위 함수 + reference_dynamics) |
| 환경 래퍼 | `src/hf_sim/env.py` | Gymnasium.Env — RL 학습 파이프라인 인터페이스 |
| 런타임 | `src/hf_sim/ray_runtime.py` | 병렬 rollout (Ray optional, local fallback) |
| 보정 워크플로우 | `src/hf_sim/aero_calibration.py` | REQ-008 — JSON case library 기반 공력 보정 |
| 실험 재현성 | `src/hf_sim/run_manifest.py` | REQ-010 — RunManifest + EvidencePackManifest |
| 월드모델 | `src/world_model/` | RSSM/DreamerV3 인터페이스 (placeholder) |

---

## 3. 설계 및 구현 이력

### 3.1 구현 단계별 완료 현황

| 단계 | 내용 | 테스트 누적 |
|------|------|------------|
| 초기 구현 (2026-04-08~09) | UF/IF 스키마 + 30 UF Python 구현, branch rollout MVP, IF-02 validation harness, flight+sensor+atmosphere, Ray runtime | **101 passed** |
| Phase A (2026-04-13) | A1: 60x benchmark 자동화 (`benchmark.py`) + A2: threat/radar validation harness 추가 | **124 passed** |
| Phase B (2026-04-13~14) | B1: full-environment long-horizon acceptance (1 000~1 200 steps, mid-run checkpoint restore) + B2: RunManifest/EvidencePackManifest (REQ-010) | **151 passed** |
| Phase C (2026-04-14~17) | C1: RK4 2차 6-DoF 비교 + C2: use_radar_obs observation 확장 (16→22 dim) + C3: 공력 보정 case library 5개 (REQ-008) | **198 passed** |

### 3.2 REQ 달성 현황

| REQ | 내용 | 상태 |
|-----|------|------|
| REQ-001 | 6-DoF 동역학 | ✅ 구현 + validation harness |
| REQ-002 | snapshot/branch rollout | ✅ full-environment, determinism 1e-6 |
| REQ-003 | 하드웨어 적응형 스케줄링 | △ LocalEnvWorker 구현, auto-sizing 검증 미흡 |
| REQ-004 | 60x 시간 배속 | ✅ 실측 ~460x (benchmark.py 자동화, regression 추적 가능) |
| REQ-005 | 구조화 관측 | ✅ 16-dim 기본 + 22-dim (use_radar_obs) 확장 |
| REQ-006 | 커리큘럼 시나리오 | △ domain_rand.py 존재, 단계별 검증 미흡 |
| REQ-007 | 4-agent 기본 임무 | ✅ env.py + integration 테스트 |
| REQ-008 | 공력 계수 보정 | ✅ 5 cases + file-driven JSON workflow + 100% metric coverage |
| REQ-009 | 평가 우선순위 | ✅ IF-05 구현 |
| REQ-010 | 실험 재현성 | ✅ capture_run_manifest() < 5s, config+seed+hw+revision |
| REQ-011 | 범위 배제 | ✅ 정책 준수 |

---

## 4. 핵심 설계 결정 (Key Decisions)

| 결정 | 선택한 방법 | 기각한 대안 | 이유 |
|------|------------|------------|------|
| 운동 모델 충실도 | simplified 6-DoF rigid-body | 고충실 공력 모델 | 학습 검증 속도 우선, throughput 유지 |
| snapshot 의미 | full-environment runtime checkpoint | ownship-only snapshot | 월드모델/플래너가 전체 환경 분기 rollout 필요 |
| IF-03 설계 | full-environment branch runtime service | ownship 중심 snapshot | 초기 좁은 해석 → 전면 재설계, 재현성과 branchability 확보 |
| benchmark sim_time 집계 | `n_steps * step_dt_s` (루프 후 누적) | `info["sim_time_s"]` (env 내부 elapsed) | env.reset() 시 sim_time_s가 0으로 리셋됨 → 에피소드 단위 시간만 나와 60x 검증 불가 |
| checkpoint restore API | validate → materialize 체인 (3단계) | 단일 restore_environment_checkpoint() | 해당 함수 미존재, IF-03 실제 API는 validate+materialize 2단계 체인 |
| 2차 6-DoF reference | RK4 내장 reference 모델 | JSBSim subprocess 연동 | Windows binding 불안정, 외부 의존성 없이 "open-model" 충족 |
| observation 확장 | extension_channels + use_radar_obs 플래그 | IF-04 UF 레이어 변경 | 기존 16-dim 유지, backward-compatible, 기존 테스트 무영향 |
| 공력 보정 workflow | JSON case library + file-driven | 하드코딩 case | REQ-008 file/config-driven 요건 명시적 충족, 확장성 |
| evidence_pack 설계 | EvidencePackManifest (pack_id + req_id + run_manifest + artifact_paths + pass_fail) | MVP 단계에서 즉시 연결 | acceptance lock 전까지 deferred가 설계집중에 유리 → Phase B에서 도입 |
| RAM 탐지 (run_manifest) | psutil → ctypes (Windows MEMORYSTATUSEX) → /proc/meminfo → 0.0 fallback | psutil 단독 의존 | 하드 의존성 없이 Windows/Linux 최대 호환 |

---

## 5. 겪었던 문제점

| # | 문제 | 원인 | 영향 |
|---|------|------|------|
| 1 | UF 문서 검증 책임 불명확 | 모든 UF를 독립 기능테스트 대상으로 가정 | 문서-테스트-구현 정합성이 반복적으로 깨짐 |
| 2 | snapshot 요구 해석 오류 | 초기에 ownship 중심으로 좁게 이해 | IF-03 의미와 UF 구조를 전면 재설계해야 했음 |
| 3 | evidence_pack strict 완결 선행 요구 | MVP acceptance 경계 잠금 전에 evidence 형태 상정 | 불필요한 FAIL 누적, 병목 발생 |
| 4 | Windows/pytest 임시 디렉터리 권한 문제 | `tmp_path`/`TemporaryDirectory`가 환경에서 제한적 동작 | 로깅 관련 테스트가 권한 오류로 반복 실패 |
| 5 | pyvista/ray 의존성 범위 불명확 | 시각화·분산실행과 학습용 rollout의 목적 차이 | optional/offline 분리 설계가 뒤늦게 필요해짐 |
| 6 | benchmark 60x 검증 실패 (`sim_time_s` 1.4s 출력) | env.reset() 시 sim_time_s가 에피소드 시작 기준으로 리셋됨 | 60s 시뮬레이션 목표치가 1.4s로 측정돼 FAIL; 집계 방식 수정 필요 |
| 7 | restore_environment_checkpoint() 함수 미존재 | IF-03 실제 API가 validate → materialize 2단계 체인임을 모름 | B1 checkpoint restore 테스트 AttributeError로 실패 |

---

## 6. 극복 방법

| # | 해결 방법 | 결과 |
|---|----------|------|
| 1 | verification ownership을 `UF-local / guard-rail / IF acceptance`로 재분류 | uf.md와 실제 테스트 구조 정합성 회복 |
| 2 | IF-03를 `full-environment branch runtime service`로 재정의 | ownship·threat·radar·sensor·atmosphere 포함 branch rollout 가능 |
| 3 | evidence는 MVP acceptance 잠금 이후로 미루고 `todo.md`에 deferred 처리 | 설계/구현 정합성 확보에 집중 가능 |
| 4 | 테스트를 workspace 내 명시적 파일 생성/삭제 방식으로 변경 | 로깅/branch export 테스트 안정화 |
| 5 | offline export + optional helper 패턴으로 분리 | core simulation과 분석 도구 결합도 감소 |
| 6 | `sim_time_s = n_steps * step_dt_s` 로 수정 (루프 외 누적) | benchmark 60x 검증 정상화, 실측 ~460x 확인 |
| 7 | IF-03 소스 직접 탐색 → validate+materialize 체인으로 수정 | checkpoint restore determinism 테스트 PASS |

---

## 7. 개선점 및 교훈

### 7.1 기술적 개선점
- threat + radar는 validation harness까지 완성됐으나, 고기동 시 homing 모델 등 추가 위협 유형 미지원
- atmosphere 모델은 `density + wind + turbulence` 수준 — richer weather coupling 여지 존재
- RK4 quaternion kinematics: 현재 rotational은 Euler 유지; 고기동(dt > 0.01s) 시 RK4 rotational 적용 가능
- World model 인터페이스 (RSSM/DreamerV3)는 placeholder — 실 학습 파이프라인 연결이 다음 핵심 과제

### 7.2 프로세스 개선점
- UF 설계 단계부터 verification ownership을 기본 규칙으로 적용
- Windows 로컬 권한 이슈를 고려한 테스트 파일 출력 규칙 공통화
- Phase 단계 구분 + 단계마다 보고/승인 방식이 설계 품질 유지에 효과적이었음

### 7.3 핵심 교훈 (Key Takeaways)
1. **learnability, determinism, throughput의 균형** — realism-max가 목표가 아니다. 측정 가능한 기준(60x, 1e-6 determinism)이 모든 설계 결정의 기준이 된다.
2. **snapshot = branchable runtime semantics** — "저장"이 아니라 "분기 가능한 환경 전체의 복원"이다. 이를 놓치면 IF-03 전체를 재설계해야 한다.
3. **측정 가능성이 모든 변경의 전제조건** — benchmark 자동화 없이는 어떤 변경도 regression 여부를 알 수 없다. Phase A에서 먼저 측정 도구를 만든 것이 옳았다.

---

## 8. 현재 상태 및 다음 단계

**현재 상태**: 진행 중 — **198 tests passed** (2026-04-17 기준)

### 완료
- [x] REQ → IF → UF 설계 아티팩트 전체 작성
- [x] 30 UF Python 구현 + unit/integration 테스트
- [x] full-environment runtime checkpoint 및 branch rollout MVP
- [x] IF-02 6-DoF validation harness (600s, 1e-6 determinism)
- [x] flight + sensor + atmosphere 고도화, logging, optional viewer
- [x] Gymnasium wrapper (HFSimEnv), dataset, reward, noise, domain_rand
- [x] Ray runtime layer (LocalEnvWorker/Collector/Logger + optional Ray actor)
- [x] world_model/ 인터페이스 placeholder (RSSM, DreamerV3)
- [x] **Phase A**: 60x benchmark 자동화 (`benchmark.py`) + threat/radar validation harness
- [x] **Phase B**: full-environment long-horizon acceptance + RunManifest/EvidencePackManifest (REQ-010)
- [x] **Phase C**: RK4 2차 6-DoF 비교 + 22-dim observation extension + 공력 보정 case library 5개 (REQ-008)

### 남은 작업 (Phase D — 선택적)
- [ ] **D1**: real pyvista 설치 + viewer overlays (offline 분석 도구)
- [ ] **D2**: real Ray actor-pool harness (멀티머신 스케일아웃)
- [ ] **D3**: atmosphere/weather 모델 고도화 (현재 MVP 수준은 충분)
- [ ] **D4**: World model 실 학습 파이프라인 연결 (RSSM/DreamerV3 placeholder → 구현)
- [ ] **D5**: curriculum 단계별 도전 수준 검증 강화

### 알려진 이슈
- REQ-003 auto-sizing 검증 미흡 (LocalEnvWorker 동작하나 하드웨어 적응 단계별 테스트 없음)
- REQ-006 curriculum 난이도 단계별 acceptance 미완

---

## 9. 참고 자료 및 산출물

| 유형 | 파일/경로 | 설명 |
|------|----------|------|
| 요구사항 | `output_docs/requirements.md` | MVP 요구사항 11개 + acceptance 기준 |
| IF 설계 | `output_docs/if_list.md` | IF 경계와 계약 |
| IF 분해 | `output_docs/if_decomposition.md` | IF → UF 분해 결과 |
| UF 설계 | `output_docs/uf.md` | canonical UF 문서 (30 UF) |
| 미결 작업 | `output_docs/todo.md` | deferred 항목 목록 |
| 스키마 | `src/hf_sim/models.py` | 52개 dataclass I/O 계약 |
| case library | `data/calibration_cases.json` | REQ-008 공력 보정 5개 case |
| Phase A 보고서 | `review_docs/260413_1500_phase_a_implementation_report.md` | benchmark + threat/radar harness |
| Phase B 보고서 | `review_docs/260414_0930_phase_b_implementation_report.md` | long-horizon + run_manifest |
| Phase C 보고서 | `review_docs/260413_1800_phase_c_implementation_report.md` | RK4 + obs extension + aero calibration |
| 작업 로그 | `0.FilesUpdate.xlsx` | 생성 파일 목록 (일시, 파일명, 요약) |
| 프롬프트 로그 | `1.PromptsUpdate.xlsx` | 프롬프트/응답 이력 |

# HF_Sim Project Summary

> **목적**: 월드모델 학습 가능성을 빠르게 검증하기 위한 물리 일관성 기반 시뮬레이션 환경의 설계·구현 요약
> **기간**: 2026-04-08 ~ 진행 중
> **최종 업데이트**: 2026-04-13

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
| 스키마 | `src/hf_sim/models.py` | 42개 dataclass — 모든 I/O 계약 정의 |
| IF 계층 | `src/if/if0X_*.py` | UF 체인 진입점 (5개 통합 함수) |
| UF 계층 | `src/uf/if0X_*.py` | 핵심 로직 구현 (30개 단위 함수) |
| 환경 래퍼 | `src/hf_sim/env.py` | Gymnasium.Env — RL 학습 파이프라인 인터페이스 |
| 런타임 | `src/hf_sim/ray_runtime.py` | 병렬 rollout (Ray optional, local fallback) |
| 월드모델 | `src/world_model/` | RSSM/DreamerV3 인터페이스 (placeholder) |

---

## 3. 설계 및 구현 이력

### 3.1 핵심 설계 결정

| 결정 | 채택 | 기각 | 이유 |
|------|------|------|------|
| 운동 모델 | simplified 6-DoF rigid-body | 3-DoF / 고충실 공력 | 자세/기동 일관성 확보 + 학습 검증 속도 유지 |
| snapshot 의미 | full-environment runtime checkpoint | ownship-only snapshot | 월드모델·플래너가 전체 환경 분기 rollout 필요 |
| 관측 전략 | structured state + terrain/threat features | 이미지/포토리얼 센서 | throughput과 학습 안정성 우선 |
| 병렬화 | Ray optional + local fallback | Ray 필수 의존 | 코어 시뮬레이션 독립성 유지 |
| 가시화 | offline export + optional pyvista | runtime 직접 렌더링 | 병렬 rollout 성능과 분석 도구 분리 |

### 3.2 구현 단계별 완료 현황

| 단계 | 내용 | 테스트 |
|------|------|--------|
| UF/IF 스키마 + 기본 구현 | 30 UF × 5 IF 전 구현, models.py 42개 클래스 | 23 passed |
| MVP branch rollout | full-environment checkpoint capture/clone/branch rollout | 17 passed |
| IF-02 validation harness | 600s 안정성, deterministic replay, throttle/pitch/roll sanity | 23 passed |
| flight+sensor+atmosphere | 대기 영향, 센서 품질/열화, logging, pyvista helper | 32 passed |
| Ray 런타임 레이어 | LocalEnvWorker / LocalCollector / LocalLoggerWorker + optional Ray actor | **101 passed** |

---

## 4. 겪었던 문제점

| # | 문제 | 원인 | 영향 |
|---|------|------|------|
| 1 | UF 문서 검증 책임 불명확 | 모든 UF를 독립 기능테스트 대상으로 가정 | 문서-테스트-구현 정합성이 반복적으로 깨짐 |
| 2 | snapshot 요구 해석 오류 | 초기에 ownship 중심으로 좁게 이해 | IF-03 의미와 UF 구조를 전면 재설계해야 했음 |
| 3 | evidence_pack strict 완결 선행 요구 | MVP acceptance 경계 잠금 전에 evidence 형태 상정 | 불필요한 FAIL 누적, 병목 발생 |
| 4 | Windows/pytest 임시 디렉터리 권한 문제 | `tmp_path`/`TemporaryDirectory`가 환경에서 제한적 동작 | 로깅 관련 테스트가 권한 오류로 반복 실패 |
| 5 | pyvista/ray 의존성 범위 불명확 | 시각화·분산실행과 학습용 rollout의 목적 차이 | optional/offline 분리 설계가 뒤늦게 필요해짐 |

---

## 5. 극복 방법

| # | 해결 방법 | 결과 |
|---|----------|------|
| 1 | verification ownership을 `UF-local / guard-rail / IF acceptance`로 재분류 | uf.md 와 실제 테스트 구조 정합성 회복 |
| 2 | IF-03를 `full-environment branch runtime service`로 재정의 | ownship·threat·radar·sensor·atmosphere 포함 branch rollout 가능 |
| 3 | evidence는 MVP acceptance 잠금 이후로 미루고 `todo.md`에 deferred 처리 | 설계/구현 정합성 확보에 집중 가능 |
| 4 | 테스트를 workspace 내 명시적 파일 생성/삭제 방식으로 변경 | 로깅/branch export 테스트 안정화 |
| 5 | offline export + optional helper 패턴으로 분리 | core simulation과 분석 도구 결합도 감소 |

---

## 6. 개선 필요 사항

### 기술적
- threat + radar validation harness를 flight/sensor/atmosphere 수준으로 끌어올릴 필요
- atmosphere 모델은 `density + wind + turbulence` 수준이며 물리 의미를 더 다듬을 여지 존재
- sensor는 state-derived quality 모델 → richer mission sensor/radar coupling으로 확장 필요
- branch rollout 결과를 learner input/analysis pipeline과 더 직접 연결하는 인터페이스 필요

### 프로세스
- UF 설계 단계부터 verification ownership을 기본 규칙으로 적용
- Windows 로컬 권한 이슈를 고려한 테스트 파일 출력 규칙 공통화
- validator 결과를 "runtime / document alignment / evidence completeness" 기준으로 구분 유지

---

## 7. 현재 상태 및 다음 단계

**현재 상태**: 진행 중 — 101 tests passed (2026-04-09 기준)

### 완료
- [x] REQ → IF → UF 설계 아티팩트 전체 작성
- [x] 30 UF Python 구현 + unit/integration 테스트
- [x] full-environment runtime checkpoint 및 branch rollout MVP
- [x] IF-02 6-DoF validation harness (600s, 1e-6 determinism)
- [x] flight + sensor + atmosphere 고도화, logging, optional viewer
- [x] Gymnasium wrapper (HFSimEnv), dataset, reward, noise, domain_rand
- [x] Ray runtime layer (LocalEnvWorker/Collector/Logger + optional Ray actor)
- [x] world_model/ 인터페이스 placeholder (RSSM, DreamerV3)

### 다음 작업 (`output_docs/todo.md` 참조)
- [ ] threat + radar validation harness 추가
- [ ] full-environment long-horizon acceptance 추가
- [ ] `evidence_pack` 스키마와 artifact policy 확정
- [ ] JSBSim/open-model 기반 2차 6-DoF 비교 검증
- [ ] benchmark/profiling 자동화 (60x 시간 배속 regression tracking)
- [ ] real pyvista/ray 의존성 설치 경로 + richer viewer overlays
- [ ] observation schema 재정리 (radar/sensor 채널이 learner input 될 때)

---

## 8. 핵심 교훈

1. 이 프로젝트의 핵심은 realism-max가 아니라 **learnability, determinism, throughput의 균형**이다.
2. snapshot은 단순 저장 기능이 아니라 **planner/world-model을 위한 branchable runtime semantics**여야 한다.
3. 문서 설계와 테스트 책임 경계가 구현 품질만큼 중요하며, 경계가 흐리면 더 큰 재작업이 생긴다.

---

## 9. 참고 자료 및 산출물

| 유형 | 파일/경로 | 설명 |
|------|----------|------|
| 요구사항 | `output_docs/requirements.md` | MVP 요구사항 11개 + acceptance 기준 |
| IF 설계 | `output_docs/if_list.md` | IF 경계와 계약 |
| IF 분해 | `output_docs/if_decomposition.md` | IF → UF 분해 결과 |
| UF 설계 | `output_docs/uf.md` | canonical UF 문서 (30 UF) |
| UF 분할 | `output_docs/uf_split/` | IF별 UF 상세 문서 |
| 미결 작업 | `output_docs/todo.md` | deferred 항목 목록 |
| 구현 리포트 | `reports/impl/` | 단계별 구현 요약 (5개 리포트) |
| 스키마 | `src/hf_sim/models.py` | 42개 dataclass I/O 계약 |

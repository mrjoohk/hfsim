# HF_Sim 우선순위 분석

**일시**: 2026-04-13  
**분석 대상**: CLAUDE.md, project_summary.md, output_docs/todo.md, output_docs/requirements.md

---

## 1. 현재 프로젝트 상태 요약

| 항목 | 상태 |
|------|------|
| 테스트 통과 수 | 101 (unit + integration) |
| IF 구현 | 5/5 완료 |
| UF 구현 | 30/30 완료 |
| Gymnasium 래퍼 | 완료 (env.py) |
| Ray 런타임 | LocalEnvWorker/Collector/Logger 완료 (optional Ray actor) |
| World Model 인터페이스 | Placeholder (RSSM, DreamerV3) |
| E2E 테스트 | **없음** (requirements.md에 명시된 tests/e2e/ 미존재) |
| evidence_pack | **없음** (미생성) |
| 60x 벤치마크 자동화 | **없음** |

---

## 2. REQ 달성 현황 분석

| REQ | 내용 | 현황 | 갭 |
|-----|------|------|-----|
| REQ-001 | 6-DoF 동역학 | ✅ 구현 + unit/integration 테스트 | E2E 미완, evidence_pack 없음 |
| REQ-002 | snapshot/branch rollout | ✅ 구현 + unit/integration 테스트 | E2E 미완, evidence_pack 없음 |
| REQ-003 | 하드웨어 적응형 스케줄링 | △ LocalEnvWorker 구현 | auto-sizing 로직 검증 미흡 |
| REQ-004 | 60x 시간 배속 | △ 구조는 존재 | **자동화된 benchmark 없음** — 회귀 추적 불가 |
| REQ-005 | 구조화 관측 | ✅ 구현 + 테스트 | radar/sensor 채널 확장 시 재검토 필요 |
| REQ-006 | 커리큘럼 시나리오 | △ domain_rand.py 존재 | curriculum 난이도 단계별 검증 미흡 |
| REQ-007 | 4-agent 기본 임무 | ✅ env.py + integration 테스트 | — |
| REQ-008 | 공력 계수 보정 | △ UF 구현 | calibration workflow 확장 필요 |
| REQ-009 | 평가 우선순위 | ✅ IF-05 구현 | — |
| REQ-010 | 실험 재현성 | △ validation_logging.py | run manifest 자동 저장 미연결 |
| REQ-011 | 범위 배제 | ✅ 정책 준수 | — |

---

## 3. todo.md 항목 분류 및 우선순위 분석

### 판단 기준
1. **MVP 수용성 완결 기여도** — 현재 101 tests passed 상태에서 acceptance gap을 메우는가
2. **차단 관계 (blocking)** — 다른 작업을 막고 있는가
3. **핵심 철학 기여도** — learnability, determinism, throughput 중 어느 것에 직결되는가
4. **구현 복잡도** — 리소스 대비 효과

### 우선순위 분류

| 순위 | 항목 | 판단 근거 |
|------|------|-----------|
| **P1** | threat + radar validation harness | - 현재 threat/radar는 continuity placeholder 상태 <br>- IF-02의 acceptance 완결에 필수 <br>- flight/sensor/atmosphere는 이미 안정화 → 다음 논리적 단계 |
| **P1** | benchmark/profiling 자동화 (60x) | - REQ-004가 하드 acceptance criterion <br>- 현재 60x 달성 여부를 **측정 불가** <br>- regression tracking 없으면 이후 변경이 전부 blind |
| **P2** | full-environment long-horizon acceptance | - checkpoint 완결성, 서브시스템 연속성 교차 검증 <br>- P1 완료 후 전체 스택 수직 통합 테스트로 의미 있음 |
| **P2** | evidence_pack 스키마 + run manifest 저장 | - REQ-001~011 전체에 evidence 항목 명시 <br>- acceptance 잠금 전에 확정 필요 <br>- REQ-010 (재현성) 충족 조건 |
| **P3** | JSBSim/open-model 2차 6-DoF 비교 | - 현재 simplified 모델 신뢰성 보강 <br>- 외부 의존성 필요, P1/P2 완료 후 수행이 효율적 |
| **P3** | observation schema 재정리 | - radar/sensor 채널이 실제 learner input이 되는 시점에 수행 <br>- 현재는 선행 구조 변경 없이 deferred 유지 합리적 |
| **P4** | 공력 보정 워크플로우 확장 | - REQ-008 보강, 현재 구조는 동작하나 case library 부족 <br>- 학습 검증 목적과 직접 연결 약함 |
| **P4** | atmosphere/weather 모델 고도화 | - 현재 density+wind+turbulence 수준은 MVP에 충분 <br>- 물리 정밀도 향상은 throughput 목표와 충돌 가능 |
| **P5** | real pyvista 설치 + viewer overlays | - 오프라인 분석 도구, 핵심 경로 아님 |
| **P5** | real ray actor-pool 실행 harness | - LocalEnvWorker가 fallback으로 동작 중 <br>- 멀티머신 스케일아웃 필요 시점까지 deferred 합리적 |

---

## 4. 추천 실행 순서 (검토 요청)

```
Phase A (지금 바로)
  ├── A1. 60x benchmark/profiling 자동화
  │       → 이유: 측정 없이는 어떤 변경도 regression 여부 불명
  └── A2. threat + radar validation harness
          → 이유: IF-02 acceptance의 마지막 공백 메우기

Phase B (A 완료 후)
  ├── B1. full-environment long-horizon acceptance test
  │       → 이유: 전체 스택 수직 통합 검증
  └── B2. evidence_pack 스키마 + run manifest 자동 저장
          → 이유: REQ acceptance 잠금을 위한 artifact 정책

Phase C (B 완료 후)
  ├── C1. JSBSim/open-model 2차 6-DoF 비교
  ├── C2. observation schema 재정리
  └── C3. 공력 보정 case library 확장

Phase D (선택적 / 필요 시)
  ├── D1. real pyvista 설치
  ├── D2. real ray actor-pool
  └── D3. atmosphere 모델 고도화
```

---

## 5. 판단 근거 요약

- **A1 우선**: 60x가 검증되지 않으면 B/C 단계의 어떤 변경도 throughput regression을 모른 채 진행된다. 측정 가능성은 모든 작업의 전제조건이다.
- **A2 우선**: todo.md와 CLAUDE.md 모두 "threat + radar harness"를 Next Priorities 1번으로 명시하고 있다. flight/sensor/atmosphere 수준까지 끌어올리는 것이 IF-02 acceptance 완결을 의미한다.
- **B2 앞당김**: evidence_pack이 없으면 requirements.md에 명시된 모든 REQ의 evidence 항목이 공백이다. acceptance lock 전 필수 작업이다.

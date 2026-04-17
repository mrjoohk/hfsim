# Phase B 구현 완료 보고서

**일시**: 2026-04-14
**범위**: B1 (full-environment long-horizon acceptance) + B2 (evidence_pack + run manifest)

---

## Phase B1 — Full-Environment Long-Horizon Acceptance

### 생성 파일
| 파일 | 유형 | 내용 |
|------|------|------|
| `tests/integration/test_long_horizon.py` | 테스트 | 4개 — 전체 환경 장기 실행 acceptance |

### 추가 테스트
| 테스트명 | 검증 항목 | 기존 테스트 대비 추가 |
|---------|----------|-------------------|
| `test_full_env_1000_steps_no_nonfinite_acceptance` | 1 000 env step (50s 시뮬레이션), obs 전 구간 finite, nonfinite event 0 | 기존 gym_rollout은 200 steps |
| `test_full_env_cross_subsystem_consistency_acceptance` | 1 200 physics step — ownship/threat/radar/sensor/atmosphere 매 step 일관성 확인 | 서브시스템 교차 검증 없었음 |
| `test_full_env_checkpoint_restore_determinism_acceptance` | step 300 체크포인트 → 300 steps 재실행 → 원본과 max_err ≤ 1e-6 | mid-run 체크포인트 determinism 미검증 |
| `test_full_env_branch_rollout_from_mid_run_acceptance` | step 300 체크포인트에서 2개 control set 분기 → distinct/valid 궤도 | 기존은 t=0 기준만 |

### 판단 근거
- 기존 IF-03 테스트는 horizon=2 (2 steps)만 — 장기 branch 미검증
- 기존 gym_rollout은 obs shape 확인만 — 서브시스템 간 정합성 미확인
- mid-run checkpoint restore determinism은 "snapshot 의미 = full-environment" 원칙의 핵심

---

## Phase B2 — Evidence Pack + Run Manifest (REQ-010)

### 생성 파일
| 파일 | 유형 | 내용 |
|------|------|------|
| `src/hf_sim/run_manifest.py` | 구현 | HardwareProfile, RunManifest, EvidencePackManifest, capture_run_manifest(), build_evidence_pack() |
| `tests/unit/test_run_manifest.py` | 테스트 | 19개 — 스키마 필드, 타이밍, JSON 직렬화, 파일 저장 |
| `tests/integration/test_run_manifest.py` | 테스트 | 4개 — 5s 기준 충족, 전 필드 채워짐, benchmark round-trip |

### 설계 결정
| 항목 | 결정 | 이유 |
|------|------|------|
| RAM 탐지 | psutil → ctypes(Windows) → /proc/meminfo → 0.0 fallback | 하드 의존성 없이 최대 호환 |
| git revision | subprocess timeout=3s → "unknown" fallback | CI/CD 환경에서 git 없어도 동작 |
| 5s 제한 | `RuntimeError` 발생 | REQ-010 acceptance criterion 강제 |
| EvidencePackManifest | req_id + artifact_paths + pass_fail + notes | REQ별 증거 연결 구조 |

### 측정 결과 (실행)
- `capture_run_manifest()` 실행 시간: < 50ms (git rev-parse 포함)
- REQ-010 5s 기준: **PASS**

---

## 종합 결과

| 항목 | Before | After |
|------|--------|-------|
| 테스트 통과 수 | 124 | **151** |
| 장기 env 실행 검증 | 200 steps | **1 000 steps (50s 시뮬레이션)** |
| 서브시스템 교차 검증 | 없음 | **1 200 physics steps 매 step** |
| mid-run 체크포인트 | 없음 | **step 300 capture → restore → max_err ≤ 1e-6** |
| run manifest | 없음 | **REQ-010 충족: < 5s, config+seed+hw+revision** |
| evidence pack | 없음 | **EvidencePackManifest + JSON save/load** |

---

## 한계 (Phase C에서 해결 예정)
- JSBSim/open-model 2차 6-DoF 비교 (C1) 미완
- observation schema 재정리 (C2) 미완
- 공력 보정 case library 확장 (C3) 미완

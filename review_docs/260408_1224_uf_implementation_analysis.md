# UF 구현 시작 분석 메모

## 요청 요약
- `uf-implementor` 기준으로 검증된 설계를 바탕으로 구현을 시작한다.
- 현재 저장소에는 소스/테스트/evidence 스켈레톤이 없으므로 초기 코드베이스를 함께 세워야 한다.

## 현재 상태 진단
- 입력 설계 문서:
  - `output_docs/requirements.md`
  - `output_docs/if_list.md`
  - `output_docs/if_decomposition.md`
  - `output_docs/uf.md`
- 코드 상태:
  - `src/`, `tests/`, `reports/impl/`가 아직 없음
- 설계 검증 상태:
  - UF 문서 구조와 체인 연속성은 통과
  - 테스트/evidence 경로는 아직 실체 없음

## 구현 판단

### 1. 구현 언어
- Python으로 진행하는 것이 적절하다.
- 이유:
  - 저장소에 기존 언어/프레임워크가 없고, `uf-implementor` 기본도 Python이다.
  - 수치 계산과 테스트 스캐폴드 작성이 빠르다.

### 2. 초기 모듈 구성
- `src/uf/if01_orchestration.py`
- `src/uf/if02_dynamics.py`
- `src/uf/if03_snapshot.py`
- `src/uf/if04_observation.py`
- `src/uf/if05_reporting.py`
- `tests/unit/test_if01_orchestration.py`
- `tests/unit/test_if02_dynamics.py`
- `tests/unit/test_if03_snapshot.py`
- `tests/unit/test_if04_observation.py`
- `tests/unit/test_if05_reporting.py`
- `reports/impl/uf_impl_report_<timestamp>.md`

### 3. 구현 우선순위
- 높은 구현 확실성:
  - IF-01 orchestration
  - IF-03 snapshot/restore/request validation
  - IF-04 observation shaping
  - IF-05 reporting/manifest
- 중간 구현 확실성:
  - IF-02 dynamics
- 이유:
  - IF-02는 구조는 명확하지만 고정밀 수치모델/공력 파라미터는 후속 조정 여지가 크다.
  - 따라서 이번 단계는 “동작 가능한 6-DoF 기반 초기 구현 + calibration hook”이 적절하다.

### 4. 구현 전략
- 모든 UF에 대해:
  - 실제 함수 바디 제공
  - 입력 검증
  - docstring
  - 최소 단위 테스트
- IF-02는 아래 수준으로 시작:
  - 6-DoF 상태 propagation의 기초 수치 적분
  - 단순화된 force/moment 계산
  - calibration config hook
  - threat/environment propagation은 파라미터화된 deterministic update
- IF-03는 serialized snapshot보다 우선 Python dict 기반 immutable payload로 시작 가능
- IF-04/05는 구현 리스크가 낮아 full initial implementation 가능

### 5. 리스크
- `uf-implementor` 스킬 설명상 Stage 7.5 coverage review 후 구현이 이상적이지만 현재 coverage review 문서는 없음
- 다만 IF/UF 설계와 chain validation은 완료된 상태라 MVP 구현 착수는 가능
- 수치모델 정확도는 이번 구현으로 최종 확정되지 않으며 후속 calibration이 필요

## 권장 진행안
- 지금 바로 초기 구현을 진행한다.
- 범위:
  - `src/uf` 5개 모듈 생성
  - `tests/unit` 5개 파일 생성
  - `reports/impl` 구현 리포트 생성
- 구현 상태 표기는 대부분 `IMPLEMENTED`, 물리 정확도 고도화가 필요한 부분은 notes에 제한사항 기록

## 판단 근거
- 사용자는 이미 설계 문서 정비와 검증을 마쳤고 구현 시작을 요청했다.
- 저장소가 비어 있으므로 지금 가장 큰 가치는 “실행 가능한 기본 뼈대 + 테스트 연결”을 빠르게 세우는 것이다.

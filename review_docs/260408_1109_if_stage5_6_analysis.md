# IF-Designer Stage 5~6 설계 분석 메모

## 요청 요약
- `output_docs/requirements.md`를 입력으로 Stage 5~6 설계를 수행한다.
- 산출물은 `if_list.md`, `if_decomposition.md`이며 검토용으로 `review_docs`에 먼저 작성한다.

## 핵심 판단

### 1. IF 개수
- 이번 요구는 `5`개 IF로 나누는 것이 가장 균형이 좋다.
- 이유:
  - 3개 이하면 snapshot/branching, observation, orchestration 책임이 과도하게 합쳐진다.
  - 6개 이상이면 현재 MVP 범위에서 경계가 지나치게 세분화된다.

### 2. 권장 IF 경계
- `IF-01`: Scenario & Resource Orchestration
- `IF-02`: Flight and Threat Dynamics Propagation
- `IF-03`: Snapshot Branch Rollout Service
- `IF-04`: Structured Observation Interface
- `IF-05`: Evaluation, Benchmark, and Reproducibility Reporting

### 3. 경계 설정 근거
- `IF-01`은 외부 config/hardware profile을 받아 실행 계획과 scenario instance를 내보내는 상위 입력 경계다.
- `IF-02`는 전체 운동모델 스택의 상태전이 경계다.
- `IF-03`은 저장/복원/분기 rollout이라는 별도의 실행 의미를 가지므로 독립 IF가 적절하다.
- `IF-04`는 simulator state를 학습 관측으로 변환하는 데이터 타입 변화 경계다.
- `IF-05`는 benchmark/evaluation/manifest 생성이라는 출력 및 증적 경계다.

### 4. REQ 매핑 전략
- REQ-001, REQ-004, REQ-007, REQ-008은 주로 `IF-02`
- REQ-002는 주로 `IF-03`
- REQ-003, REQ-006, REQ-007, REQ-011은 주로 `IF-01`
- REQ-005는 `IF-04`
- REQ-004, REQ-009, REQ-010, REQ-011은 `IF-05`
- 일부 REQ는 복수 IF에 걸쳐 연결된다. 특히 REQ-004와 REQ-010은 cross-cutting requirement다.

## 판단 근거
- 요구사항은 입력 경계, 상태전이 경계, branch execution 경계, 학습 관측 경계, 평가 출력 경계로 명확히 분리된다.
- 이 분해는 이후 UF 정의 시 leaf function이 지나치게 비대해지는 것을 방지한다.

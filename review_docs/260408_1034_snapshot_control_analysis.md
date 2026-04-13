# Snapshot + Control Reinjection 검토 메모

## 요청 요약
- `t-1`뿐 아니라 각 시점의 객체 정보를 저장하고 싶다.
- 저장된 그 시점 상태를 기준으로 새로운 조종값(control input)을 넣어 상태를 다시 갱신할 수 있어야 한다.
- 이 요구를 검토해 `AGENTS.md`에 반영해야 한다.

## 검토 결과

### 결론
- 강하게 권장한다.
- 다만 "객체 자체 저장"보다 "시점별 복원 가능한 시뮬레이션 상태 저장 + control reinjection"으로 정의하는 것이 더 정확하고 구현 친화적이다.

### 왜 필요한가
- 월드모델 학습에서는 동일한 상태에서 다른 action/control을 넣었을 때 미래 궤적이 어떻게 달라지는지 반복적으로 비교해야 한다.
- 정책 학습, counterfactual rollout, what-if 분석, planner evaluation, imagination rollout에 모두 직접적으로 유용하다.
- 단순 `t-1` 복원만으로는 충분하지 않고, 임의 시점 `t_k`에서의 branch rollout이 가능해야 실험 효율이 올라간다.

### 설계 해석
- 저장 대상은 "운동모델 객체"라기보다 "운동모델이 결정론적으로 다음 상태를 계산하는 데 필요한 전체 상태"다.
- 따라서 인터페이스는 아래와 같은 개념이 적합하다.
  - `capture_snapshot(t_k) -> Snapshot`
  - `restore_snapshot(snapshot)`
  - `step(control_input, dt)`
  - `rollout_from(snapshot, control_sequence, horizon)`

### Snapshot에 포함해야 하는 항목
- simulation clock / step index
- vehicle 6-DoF state
- angular / translational derivatives or integrator cache if needed
- actuator states
- controller/filter internal states
- environment states that affect future transition
- contact / collision / failure mode flags
- RNG state
- multi-agent shared state if the branch is global

### 설계 권고
- 스냅샷은 immutable 데이터 구조로 둔다.
- 런타임 객체는 mutable이어도 되지만, snapshot은 직렬화 가능해야 한다.
- 한 기체 단위 snapshot과 환경 전체 snapshot을 구분한다.
- branch rollout은 "snapshot + control sequence + seed"로 완전 재현 가능해야 한다.
- 필요하면 저장 주기를 조절해 메모리/성능을 맞춘다.

### 주의할 점
- 스냅샷 저장만 있고 control reinjection 인터페이스가 없으면 활용성이 크게 떨어진다.
- 객체 참조 기반 저장은 병렬 rollout과 직렬화에서 문제가 생기기 쉽다.
- hidden state가 snapshot에 빠지면 복원 후 trajectory mismatch가 발생한다.

## AGENTS.md 반영 포인트
- `t-1` 표현을 `arbitrary saved time point`로 일반화
- `control reinjection`과 `counterfactual branch rollout`을 명시
- snapshot 요구사항에 control-relevant hidden state를 추가
- deterministic replay뿐 아니라 "same snapshot + different control" 실험을 지원한다고 명시

## 판단 근거
- 사용자의 목표는 world-model 학습과 고정 시간 기준 rollout 검증이다.
- 이는 단순 replay보다 더 강한 요구인 "state-conditioned branching"을 포함한다.
- 따라서 설계 문서도 rollback 중심 표현에서 branchable simulation state 중심 표현으로 바꾸는 것이 맞다.

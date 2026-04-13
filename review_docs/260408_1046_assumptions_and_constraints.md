# Assumptions and Constraints

## Constraints
- Performance: 기준 시나리오에서 활성화되는 전체 운동모델 스택(아군 6-DoF, 적/위협 기동, 표적/환경 전이, snapshot/state-management 오버헤드 포함)에 대해 실시간 대비 시뮬레이션 시간 배속이 `60x` 이상이어야 한다.
- Memory: 단일 머신 실행 시 프로세스가 사용 가능한 시스템 RAM의 `85%`를 초과하지 않아야 하며, GPU 사용 시 사용 가능한 VRAM의 `90%`를 초과하지 않아야 한다.
- Accuracy: 월드모델 평가 우선순위는 `1-step / n-step prediction error`가 1순위, `latent rollout consistency`가 2순위, `정책 학습 수렴`이 3순위여야 한다.
- Throughput: 병렬 rollout 수와 초당 env step 수는 고정값으로 강제하지 않고, 시작 시 하드웨어를 감지하여 안전한 병렬도를 자동 산정해야 한다.
- Regulations / Compliance: 이번 단계는 연구/학습용 시뮬레이션 환경 설계 범위이며, 실기체 운용 인증이나 군 운용 승인 범위는 포함하지 않는다.

## Boundary Conditions
- Input minimum: `1` agent, `1` scenario seed, 구조화 상태벡터만 포함한 관측으로도 환경 reset/step이 가능해야 한다.
- Input maximum: 기본 설계 기준은 `4` agents이며, 단일 머신 자원 한도 내에서 하드웨어 적응형 batched rollout을 지원해야 한다.
- Extreme scenarios:
  - GPU가 없거나 비활성화된 경우에도 CPU-only fallback 초기화가 가능해야 한다.
  - 사용 가능한 메모리가 부족한 경우 rollout 병렬도를 자동으로 축소해야 한다.
  - 관측 feature 일부가 비정상 값(`NaN`, `Inf`, 범위 초과)을 포함할 경우 episode를 실패 원인과 함께 종료하거나 안전한 기본값으로 방어해야 한다.
  - snapshot restore 이후 다른 control sequence를 주입하면 독립된 branch rollout이 생성되어야 한다.

## Assumptions to be validated

| # | Assumption | Validation Method | Status |
|---|-----------|-------------------|--------|
| A1 | `60x` 시간 배속은 상태벡터 기반 관측과 단순 지형/위협 feature 구성에서, 기준 시나리오의 전체 운동모델 스택을 활성화한 상태로 단일 GPU 머신에서 달성 가능하다. | 대표 시나리오 benchmark 실행 후 wall-clock 대비 sim-time 비율 측정 | Unvalidated |
| A2 | 하드웨어 적응형 rollout auto-sizing만으로도 다양한 PC 환경에서 안정적으로 OOM 없이 실행 가능하다. | 서로 다른 CPU/GPU/RAM 프로파일에서 stress test 수행 | Unvalidated |
| A3 | 단순화된 6-DoF 모델과 파라미터화된 공력 계수 구조만으로도 world-model 학습에 필요한 주요 동역학은 충분히 표현 가능하다. | prediction error 및 rollout consistency 실험으로 검증 | Unvalidated |
| A4 | 정밀 공력 계수 튜닝을 위한 초기 설정값 또는 참조 계수 자료를 JSBSim 등 오픈 모델이나 공개 파라미터 자료에서 확보할 수 있다. | 기체 후보 선정 후 오픈 모델/자료 조사 및 configuration 반영 여부 확인 | Unvalidated |
| A5 | 기본 관측을 상태벡터 + 단순 지형/위협 feature로 제한해도 이미지 관측 없이 초기 world-model 학습 성공 여부를 판단할 수 있다. | 구조화 관측 기반 학습 실험으로 검증 | Unvalidated |

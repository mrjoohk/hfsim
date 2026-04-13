# AGENTS.md 설계 방향 분석 메모

## 요청 요약
- `GLOBAL_RULES.md`를 준수한다.
- 월드모델 학습용 물리기반 임무환경 프로젝트의 설계 방향을 검토한다.
- 아래 3가지 추가 지침을 반영한다.
  - 비행체 운동모델은 6-DoF로 검토한다.
  - 시각 `t-1`의 운동모델 객체 상태를 저장해 고정 시간 기준 rollout/재현을 가능하게 한다.
  - `IF-SCENARIO`는 학습 성공 검증에 유리한 시나리오 생성 최적화 방향으로 설계한다.
  - 멀티에이전트는 4기로 시작한다.
- 최종 산출물은 300줄 이하 `AGENTS.md`이며, 상세는 참조 파일 경로 중심으로 연결한다.

## 검토 결과

### 1. 6-DoF 운동모델 채택
- 권고: 채택
- 이유:
  - 사용자가 운동모델 정확도를 중요시했고, 고속 기동/자세 변화/3차원 회피를 다루려면 6-DoF가 구조적으로 적합하다.
  - 이후 공대지/공대공 전술기동, 편대 재배치, world model latent transition의 물리 일관성 확보에 유리하다.
  - 다만 초기 단계에서는 고충실 공력 전영역 모델이 아니라 학습 검증 목적에 맞춘 "단순화된 6-DoF"가 적절하다.
- 설계 권장:
  - 강체 6-DoF 상태를 표준 내부 상태로 유지한다.
  - 공력/추력/제어면 모델은 파라미터화된 간소 모델로 시작한다.
  - 고주파 내부 integration step과 저주파 agent step을 분리한다.

### 2. `t-1` 운동모델 객체 저장
- 권고: 채택하되, "객체 전체 스냅샷"과 "순수 상태 벡터 저장"을 분리한다.
- 이유:
  - 학습/검증에서 고정 시간 rollback, branch rollout, deterministic replay가 매우 중요하다.
  - 하지만 mutable 객체 전체를 직접 저장하면 메모리 사용량과 직렬화 비용이 급증하고, 병렬 rollout 성능이 저하될 수 있다.
- 설계 권장:
  - `StateSnapshot`을 1급 개념으로 둔다.
  - snapshot에는 시간 `t`, 6-DoF 상태, actuator/internal integrator state, RNG state, mode flag를 포함한다.
  - 런타임 객체는 `restore(snapshot)`으로 재구성한다.
  - 학습용 고정 시간 rollout은 "환경 스냅샷 + 에이전트별 스냅샷" 단위로 관리한다.

### 3. `IF-SCENARIO`의 역할
- 권고: 학습 적합성 최적화 모듈로 정의
- 이유:
  - 현재 목표는 realism 극대화보다 "월드모델 학습 성공 여부 검증"이다.
  - 따라서 scenario generator는 실제 전장 재현기보다 curriculum/orchestration 도구에 가까워야 한다.
- 설계 권장:
  - 난이도 계층화: 쉬운 추적/회피/표적접근 시나리오에서 시작해 점진 확장
  - 학습친화 샘플링: 관측 가능성, event density, controllability가 높은 분포 우선
  - 실패 유도 샘플링: world model error가 커지는 조건을 찾아 재주입
  - 희귀 이벤트는 초기에는 제한적으로, 학습 안정화 후 점진 증가

### 4. 멀티에이전트 4기 시작
- 권고: 채택
- 이유:
  - 4기는 편대/군집 최소 의미를 가지면서도 상태공간 폭증을 아직 통제할 수 있는 타협점이다.
  - 환경 throughput, scenario 조합 수, credit assignment 난이도 측면에서도 초기 검증 규모로 적절하다.
- 설계 권장:
  - 1기/2기/4기 모드를 모두 지원하되, 4기를 기본 검증 모드로 둔다.
  - 단일 코드베이스에서 agent count를 config로 제어한다.

## 프로젝트 설계 방향 핵심

### 최상위 목표
- 목적은 "월드모델이 학습 가능한 물리기반 환경"을 빠르게 구현하고 검증하는 것이다.
- 초점은 고충실도 전장 디지털트윈 완성이 아니라, 물리 일관성, 재현성, 병렬성, time acceleration 확보에 둔다.

### 아키텍처 원칙
- 내부 동역학은 6-DoF를 유지한다.
- 환경 상태는 snapshot/restore 가능한 결정론 구조로 설계한다.
- simulator core와 learner를 분리해 병렬 rollout throughput을 높인다.
- scenario는 realism-first가 아니라 learnability-first로 설계한다.
- 4기 멀티에이전트를 기본 목표로 하되, 단일/2기 모드로 디버깅 가능해야 한다.

### 우선 비기능 요구
- deterministic replay
- fixed-horizon rollout
- fast-forward / time acceleration
- batched parallel rollout
- low-overhead snapshotting
- experiment reproducibility

### 피해야 할 방향
- mutable 객체 전체를 매 step 깊은 복사하는 구조
- 초기부터 센서 렌더링/포토리얼 비전 파이프라인에 의존하는 구조
- 6-DoF 채택을 이유로 과도한 공력 정밀화에 빠지는 구조
- scenario generator가 임의 랜덤화만 수행하고 학습 난이도를 제어하지 못하는 구조

## AGENTS.md에 반드시 들어가야 할 메시지
- 이 저장소의 기본 목표와 우선순위
- 6-DoF + snapshot/restore 원칙
- scenario generation의 목적이 learnability optimization임을 명시
- 4-agent 기본 설정과 config-driven 확장 방침
- 상세 설계는 별도 문서를 참조하도록 경로 중심 안내

## 참조가 필요한 파일 경로
- `C:\Users\USER\workspace\HF_Sim\GLOBAL_RULES.md`
- `C:\Users\USER\workspace\HF_Sim\.codex\skills\core-engineering\SKILL.md`
- `C:\Users\USER\workspace\HF_Sim\ref_docs\RFP 정리.md`
- `C:\Users\USER\workspace\HF_Sim\ref_docs\국내외 연구개발 동향.md`
- `C:\Users\USER\workspace\HF_Sim\ref_docs\제안 기술 주요기능 정리.md`

## 판단 근거
- RFP/제안 문서는 고속 자율기동, 위협 회피, 군집 운용, world model 기반 예측/학습, 병렬 rollout 인프라를 함께 요구한다.
- 사용자는 이번 단계 목표를 "학습 성공 검증"으로 명시했으므로, realism과 learnability 사이에서 후자를 우선해야 한다.
- 6-DoF는 전술기동 표현력 확보에 유리하지만, snapshot 기반 상태관리 없이는 fixed-time rollout과 병렬 학습 효율이 저하될 가능성이 높다.

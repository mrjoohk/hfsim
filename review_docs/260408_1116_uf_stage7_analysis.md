# UF-Designer Stage 7 설계 분석 메모

## 요청 요약
- `output_docs/if_decomposition.md`를 입력으로 Stage 7 `uf.md`를 작성한다.
- 산출물은 `review_docs`에 검토용으로 먼저 생성한다.

## 핵심 판단
- 현재 IF decomposition의 leaf node `30개`를 그대로 UF Block으로 내리는 것이 적절하다.
- 추가 분해 없이도 각 후보가 SRP를 유지한다.
- 체인 연속성 경고를 줄이기 위해 인접 UF 간 입력/출력 타입명을 명시적으로 정렬해야 한다.
- 구조화 타입 이름을 너무 넓게 쓰면 구현 지시력이 약해지므로, `NormalizedExecutionRequest`, `EntityStateSet`, `ObservationFeatureSet` 같은 도메인 타입명을 사용한다.

## 작성 방침
- Goal은 모두 단일 동사구로 쓴다.
- I/O는 타입 + 단위/shape + range를 함께 명시한다.
- Edge Case는 최소 3개 이상 넣는다.
- Verification Plan은 구체적 테스트 함수 경로와 `>= 90%` coverage를 넣는다.
- 마지막에 IF별 체인 점검 결과를 별도 섹션으로 적는다.

## 판단 근거
- 이 단계 산출물은 바로 `uf-implementor`로 넘어갈 수 있어야 하므로, 구현자가 함수 수준 책임을 바로 이해할 수 있는 정도의 구체성이 필요하다.
- 반대로 알고리즘 요약은 1~2줄로 제한해 설계 문서가 구현 상세에 매몰되지 않도록 유지해야 한다.

# UF 문서 정합성 재구성 분석 메모

## 요청 요약
- `uf.md`의 문서 정합성을 다듬는다.
- 문서 길이로 인한 편집/검토 문제 가능성을 검토한다.
- 필요하면 IF별 분할 문서를 작성한다.
- 완료 후 `uf-chain-validator` 기준으로 다시 설계 검증을 수행한다.

## 핵심 판단
- 문제의 본질은 길이 자체보다, 긴 문서를 부분 수정하면서 UF 순서와 I/O 의미가 섞인 것이다.
- 따라서 `canonical uf.md`는 유지하되, 편집성과 검토성을 위해 `IF별 split 문서`를 병행하는 것이 가장 적절하다.

## 권장 구조
- `uf.md`: tool compatibility를 위한 canonical 단일 문서
- `uf_split/uf_if01.md` ~ `uf_split/uf_if05.md`: 사람 중심 검토/수정용 분할 문서

## 수정 원칙
- UF block 순서는 `UF-01-*` → `UF-02-*` → `UF-03-*` → `UF-04-*` → `UF-05-*`
- IF-04와 IF-05는 validator 회피용 억지 타입 변경이 아니라, context type이 실제로 전달하는 정보와 알고리즘/edge case 설명이 일치해야 한다.
- chain continuity section도 새 타입 기준으로 다시 기록한다.

## 판단 근거
- downstream tool은 여전히 `uf.md`를 기대할 가능성이 높아 canonical 문서를 유지하는 편이 안전하다.
- 반면 30개 UF block 단일 문서는 재편집 시 오류 가능성이 높으므로 split docs를 병행하면 유지보수성이 올라간다.

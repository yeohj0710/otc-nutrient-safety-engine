# 사람 문헌 판정 지침

## 판정 순서

1. `priority_118_review_packet.csv`로 양식을 교정한다.
2. 첫 100건을 주검토자와 제2검토자가 독립 판정한다.
3. 불일치 원인을 합의하고 이유 코드를 보완한다.
4. 새 50건으로 재교정한다.
5. `title_abstract_full_queue.csv` 15,890건 전체를 판정한다.

## 제목·초록 판정값

- `include_candidate`: 전문 입수 대상으로 진행
- `exclude`: 제목·초록에서 명확한 제외 사유 확인
- `uncertain`: 초록 정보만으로 판단 불가; 전문 입수 대상으로 진행

## 제목·초록 제외 이유 코드

- `NOT_HUMAN`
- `NOT_ORAL_EXPOSURE`
- `NOT_TARGET_INGREDIENT`
- `NO_SAFETY_OUTCOME`
- `DIET_ONLY_NOT_SEPARABLE`
- `EFFICACY_ONLY`
- `NON_RESEARCH_PUBLICATION`
- `DUPLICATE_PUBLICATION_CANDIDATE`
- `OTHER_WITH_NOTE`

기계 제안만으로 제외하지 않는다. `computational_proposal`은 검토 순서 정보다.

## 전문 판정

전문 포함·제외에는 실제 검토자, 검토일, 원문 위치, 하나의 주 제외 사유를 기록한다. 원문을 확보하지 못한 경우 `exclude` 대신 retrieval 상태와 시도 경로를 남긴다.

## 금지

- 자동 분류를 사람 판정으로 복사
- 초록만 보고 전문 검토 완료 표시
- 미보고 값을 0으로 입력
- locator 없는 근거 추출
- 검토자·검토일을 임의 생성

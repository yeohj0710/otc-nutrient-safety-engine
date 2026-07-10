# 근거-규칙 변환 및 데이터 모델

## 1. 설계 목표

사용자가 보는 모든 문장은 다음 경로로 역추적되어야 한다.

`화면 문장 → rule_id → evidence_id → study/report → 원문 구절·표·페이지 → 추출자·검토자 → 버전`

이 경로가 끊긴 규칙은 배포할 수 없다.

## 2. 규칙 상태

- `draft_human`
- `draft_ai`
- `evidence_verified`
- `content_reviewed`
- `scenario_validated`
- `released`
- `deprecated`

`released` 이전 상태는 사용자 화면에서 기본적으로 숨긴다.

## 3. 필수 규칙 필드

```text
rule_id
clinical_node_id
scope_version
population_criteria
medication_criteria
ingredient_id
ingredient_form
dose_operator
dose_value
dose_unit
duration_operator
duration_days
coingredient_criteria
outcome_id
action_class
severity
message_short
message_explanation
questions_to_ask
uncertainty_statement
certainty_grade
jurisdiction
evidence_ids
source_quote_ids
reviewer_ids
status
valid_from
review_due
deprecated_by
```

## 4. 행동 등급

- `urgent_referral`: 즉시 전문적 평가가 필요한 경고 신호. 본 연구 범위에서는 매우 제한적으로 사용
- `avoid_or_hold_for_review`: 복용 시작·지속 전 전문가 검토 필요. 근거와 적용 범위가 명확해야 함
- `monitor_or_discuss`: 용량·검사·증상·병용 약물을 확인하고 상담
- `information_needed`: 판단에 필수 입력이 없음
- `no_reviewed_rule`: 현재 검토된 규칙이 없음. `safe`와 다름

## 5. 용량과 단위

- 원문 단위와 정규화 단위를 모두 저장
- IU 변환은 성분·형태별 공식과 출처를 버전 관리
- 제품 1회량이 아니라 실제 일일량을 계산
- 식이 섭취와 보충제 섭취를 구분
- 복합 제품의 성분별 총량을 합산하되 중복 원료를 추적
- 범위 경계값에서 부동소수점 오차를 허용하지 않도록 단위 테스트

## 6. 규칙 생성 절차

1. 포함 연구의 검증된 추출 레코드 선택
2. 근거 구절과 결과별 GRADE 확인
3. 규칙 적용 대상과 제외 대상을 명시
4. 용량·기간·병용 조건이 원문에 없으면 생성하지 않음
5. 후보 메시지를 작성하되 인과 강도를 근거보다 높이지 않음
6. 약사 검토자가 내용·표현·범위를 승인
7. 독립 시나리오에서 평가
8. released 상태로 전환

## 7. 상충 규칙

같은 입력에서 서로 다른 행동 등급이 반환되면 다음 순서로 해결한다.

1. 관할권·최신성
2. 직접 대상자 근거
3. 결과 중요도
4. 근거 확실성
5. 더 보수적인 경고가 아니라 더 잘 뒷받침된 규칙

충돌 해결 과정과 탈락 규칙을 로그에 남긴다.

## 8. 화면 표시

각 결과 카드에는 최소한 다음을 표시한다.

- 무엇을 확인해야 하는지
- 왜 그런지 한두 문장
- 적용되는 용량·상황
- 근거 확실성
- 핵심 출처와 원문 위치
- 마지막 검토일
- 입력이 부족한 항목
- 진단·처방을 대신하지 않는다는 범위 설명

후보문헌 수, 전체 검색 hit 수, 엔진 내부 규칙 수를 사용자에게 품질 지표처럼 표시하지 않는다.

# 규칙 전문가 검토 지침

## 목적

KDRI 기준 후보와 research_v3 규칙 초안 6건의 수치·급원 범위·조건·예외·사용자 문구를 약사 또는 적절한 임상 전문가가 확인한다. 자동화 도구가 검토자를 대신하지 않는다.

## 판정 순서

1. `source_file_sha256`가 보존 원본 manifest와 같은지 확인한다.
2. `locator`의 실제 PDF 페이지·인쇄 페이지·표 행을 연다.
3. 최소 필요 근거 문장을 `evidence_quote`에 직접 입력한다.
4. 임계값, 단위, 대상 집단, 급원 범위를 확인한다.
5. 코드 조건과 예외가 원문 범위를 넓히거나 줄이지 않는지 확인한다.
6. 사용자 문구가 “기준 이하=안전” 또는 임의 중단을 유도하지 않는지 확인한다.
7. 각 `*_correct`·`*_safe`·`source_locator_verified`를 `true` 또는 `false`로 기록한다.
8. `overall_decision`을 `approve`, `revise`, `reject` 중 하나로 기록한다.

`revise`·`reject`이면 `required_revision`이 필수다. `approve`는 모든 검사항목이 `true`이고 근거 문장이 있을 때만 유효하다.

## 검토자 기록

- `reviewer_id`: 연구 내 가명 식별자
- `reviewer_role`: 약사, 임상약학 전문가, 영양 기준 전문가 등 실제 역할
- `reviewed_at`: ISO 8601
- 이견이 있으면 두 번째 검토자와 adjudication 필드를 채운다.

## 검증

```powershell
python scripts/research/validate_expert_rule_review.py `
  --packet research_v3/rules/expert_rule_review_packet.csv `
  --output research_v3/audit/expert_rule_review_validation.json
```

검토가 끝나도 자동으로 `rules.csv`의 상태를 바꾸지 않는다. 승인 보고서를 확인하고 별도 변경 기록을 만든 뒤에만 `released` 승격을 수행한다.

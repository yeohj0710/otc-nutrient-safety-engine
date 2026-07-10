# 목표 저장소 아키텍처

## 1. 분리해야 하는 네 개의 계층

### 연구 원자료 계층

검색 export, 원문 접근 로그, 사람 판정, 추출, RoB, GRADE를 보관한다. 앱 코드가 이 파일을 직접 읽어 임상 문장을 만들지 않는다.

### 연구 분석 계층

근거 지도, 집중 합성, AI 평가, 시나리오 검증, metrics manifest를 생성한다. 모든 결과는 입력 해시와 분석 스크립트를 갖는다.

### 근거 규칙 계층

검증된 evidence ID와 source quote에서 승인된 규칙만 생성한다. 규칙 데이터는 앱과 논문이 공유하는 단일 릴리스 산출물이다.

### 사용자 애플리케이션 계층

정규화된 입력을 결정론적 규칙에 전달하고, 규칙 상태·불확실성·출처를 표시한다. 앱 화면의 카운트와 성능 수치를 하드코딩하지 않는다.

## 2. 권장 구조

```text
research_v2/
  project_identity.json
  DECISIONS.md
  CHANGELOG_RESEARCH.md
  HUMAN_ACTION_REQUIRED.md
  audit/
  config/
  protocol/
  search/
  screening/
  full_text/private/
  extraction/
  risk_of_bias/
  synthesis/
  ai_eval/
  rules/
  validation/
  thesis/
packages/
  evidence-schema/
  rule-engine/
apps/
  web/
scripts/
  research/
  release/
```

현재 저장소 구조를 무리하게 바꾸기보다 이 책임 경계를 유지하는 것이 중요하다.

## 3. 데이터 흐름

```text
raw exports
  -> normalized records
  -> deduplicated records/study families
  -> adjudicated screening
  -> verified extraction + source quotes
  -> RoB + GRADE
  -> evidence map / focused synthesis
  -> human-reviewed rule candidates
  -> released ruleset
  -> independent scenario validation
  -> metrics manifest
  -> app + thesis
```

역방향 의존을 금지한다. 앱 예시나 논문 문장이 연구 데이터 또는 규칙을 결정해서는 안 된다.

## 4. 버전 객체

최소 다음 버전을 별도로 관리한다.

- protocol version
- search version
- screening freeze
- evidence freeze
- ruleset version
- scenario dataset version
- app release version
- thesis version

최종 릴리스 메타데이터에는 이 버전들의 조합과 git commit을 기록한다.

## 5. 규칙 엔진 인터페이스

입력은 원문 문자열이 아니라 확인된 구조화 객체를 기본으로 한다.

```json
{
  "age": 67,
  "sex": "male",
  "medications": [{"id": "warfarin", "confirmed": true}],
  "supplements": [
    {
      "ingredient_id": "vitamin_k",
      "dose_value": 120,
      "dose_unit": "mcg/day",
      "duration": "new_start",
      "confirmed": true
    }
  ],
  "conditions": [],
  "jurisdiction": "KR"
}
```

출력은 단일 위험 점수가 아니라 규칙별 결과와 필요한 추가 질문을 포함한다.

```json
{
  "ruleset_version": "evidence-freeze-v1/rules-v1",
  "status": "matched_reviewed_rule",
  "matches": [
    {
      "rule_id": "...",
      "action_class": "monitor_or_discuss",
      "message_short": "...",
      "uncertainty_statement": "...",
      "evidence_ids": ["..."],
      "source_quote_ids": ["..."]
    }
  ],
  "missing_information": [],
  "out_of_scope_fields": []
}
```

## 6. 자연어 입력

LLM 또는 사전 기반 파서는 다음 JSON 후보만 만든다.

1. 인식한 약물·성분·용량
2. 해석하지 못한 문자열
3. 모호성 후보
4. 사용자 확인이 필요한 항목

사용자가 확인하기 전에는 임상 규칙을 실행하지 않는다. 약어 `EPA`처럼 짧고 다의적인 문자열은 단독 부분문자열 매칭을 금지한다.

## 7. 안전 상태 모델

- `matched_reviewed_rule`: 검토된 규칙이 일치
- `information_needed`: 판정에 필요한 입력 누락
- `no_reviewed_rule`: 범위 안이지만 일치하는 검토 규칙 없음
- `out_of_scope`: 연구 범위 밖
- `system_error`: 규칙 로드·검증 실패

`no_reviewed_rule`과 `out_of_scope`를 `safe`로 표시하지 않는다.

## 8. CI/CD 관문

배포 전 자동으로 확인한다.

- 타입·단위·스키마 테스트
- rule/evidence/source quote 참조 무결성
- 금지된 Kwon marker 검사
- ruleset checksum
- metrics manifest와 화면 수치 일치
- 독립 시나리오 성능 파일 존재와 기준 충족
- `validate_release.py` 통과

실패 시 앱 build가 성공해도 연구 릴리스는 실패다.

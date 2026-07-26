# v4.0 전 과정 AI 문헌 근거층 프로토콜

## 적용 범위

이 프로토콜은 `research_v3/otc/literature/`에서 새로 생성하는 v4.0 문헌 근거층과 AI 평가 산출물에만 적용한다. 기존 프로토콜과 영양성분 계보 산출물은 이전 연구 기록으로 계속 보존하며 소급 수정하지 않는다.

## 연구 구조

연구는 서로 다른 권한을 가진 두 층으로 구성한다.

1. 식약처 허가원문 층은 제품, 유효성분, 함량, 복용 조건과 규칙 판정을 결정한다. 분석 집합은 제품 13개, 고유 성분 28개, 계산용 제품-성분 연결 47개, 허가원문에서 검증한 복용 조건 32개다.
2. PubMed 문헌 층은 허가원문 판정을 설명하고 보강하는 참고 근거다. 문헌은 규칙 판정을 변경하거나 임상 권고를 만들 권한이 없다.

사실 주장과 근거 주장을 합치지 않는다. 예를 들어 1일 최대량 초과 여부는 허가원문과 산술로 판정하고, 과량 복용과 위해의 연관성은 PubMed 문헌으로 제시한다. 두 근거가 충돌하면 `conflict`로 보존한다.

## AI 자율 절차

AI가 PICOS 연구질문 정의, PubMed 검색식 작성, 검색 결과 선별, 문헌-규칙 연결, AI 참조표준 채점과 규칙엔진 맹검 독립평가를 수행한다. v4.0 체인에 포함되는 사람 판정은 0건이다. 사람 판정 자료는 이전 계보로 보존하되 v4.0 입력, 참조표준, 정답 또는 판정 근거로 연결하지 않는다.

문헌 선별 라벨은 `retain`, `deprioritize`, `uncertain`이다. 초록이 없는 문헌도 선별하며 `evidence_basis=title_only`, `confidence=low` 상한을 적용한다. 선별 프롬프트는 실행 전에 고정하고 전문, 해시, 모델, 입력 해시, 배치 ID와 배치 해시를 기록한다. 요청한 모든 행이 정확히 한 번 판정됐을 때만 `coverage=1.0`과 `run_complete=true`를 기록한다.

## AI 참조표준과 맹검 독립평가

선별기 계측용 AI 참조표준은 선별 프롬프트와 다른 PICOS 요소별 프롬프트로 세 번 독립 채점한 뒤 다수결로 만든다. 선별 결과는 참조표준 채점 입력에 포함하지 않는다. 세 판정이 모두 다르면 `unresolved`로 남긴다.

규칙엔진 평가 사례는 실제 13개 제품의 허가 구성과 16개 규칙 유형에서만 생성한다. 사례 생성 단계에서는 정답 라벨을 만들지 않는다. 맹검 판정 단계에서는 엔진 예측, 기존 Codex 예상 답안, 기존 사람 라벨을 읽지 않는다. 무작위 순서에서 세 번 독립 판정한 뒤 라벨을 잠그고 나서만 엔진 예측을 연결한다.

AI 참조표준 또는 AI 맹검평가에서 얻은 지표는 출처가 이름에 드러나야 한다. 다음 이름을 사용한다.

- `sensitivity_vs_ai_reference`
- `specificity_vs_ai_reference`
- `agreement_vs_ai_reference`
- `ai_reference_standard`
- `ai_cross_checked`
- `reference_positive_classifier_positive`

논문과 UI는 평가자가 AI였다는 사실을 지표와 함께 표시한다. AI 참조표준 재현도는 사람 기준 진실 대비 정확도가 아니다.

## 상태 게이트

AM-OTC-001에 따라 연구 완료 조건은 AI 맹검 독립평가다. AI 참조표준 계측과 AI 맹검 독립평가가 모두 정상 완료되고 근거 파일 경로가 기록된 경우에만 다음 값을 설정할 수 있다.

```text
independent_blinding_ai = true
independent_evaluation_ai_complete = true
performance_claim_allowed = true
complete = true
release_ready = false
independent_blinding = false
```

하나라도 미달하면 `complete=false`를 유지하고 차단 사유를 보고한다. 종결을 위해 수치를 조정하지 않는다. `release_ready=false`와 사람 맹검을 뜻하는 `independent_blinding=false`는 항상 유지한다.

## 계보와 보존 규칙

- `research_v3/screening/title_abstract.csv`, `research_v3/screening/full_text.csv`, `research_v3/human_review_minimal/`, `research_v3/rules/EXPERT_REVIEW_GUIDE.md`, `expert_rule_review_*`, `research_v3/otc/validation/independent_scenarios.csv`의 `human_reference_label`은 수정하거나 v4.0 체인에 연결하지 않는다.
- `research_v3/search/provisional_pubmed_20260710/`은 이전 영양성분 계보로 보존하며 수정하지 않는다.
- 새 문헌 산출물은 `research_v3/otc/literature/` 아래에만 저장한다.
- 신신파스아렉스 원자료는 보존하고 분석과 런타임 제외 상태를 유지한다.
- released 규칙은 허가원문 `source_id`와 문장 또는 페이지 단위 `source_locator`가 모두 있어야 한다.
- 복용 조건 32개와 released 규칙 15개는 서로 다른 상태이며 합치지 않는다.
- 사람이 검토할 큐, 사람 승인 대기 상태, 사람이 채울 빈칸을 만들지 않는다.
- 임상 권고, PRISMA 최종 포함·제외 수, 메타분석, 사람 RoB·GRADE를 만들지 않는다.

## 재현성과 종료 산출물

NCBI E-utilities는 초당 세 번 이하로 호출한다. 검색식, 원시 XML, SHA-256, 응답 메타데이터와 검색 로그를 보존한다. 모든 숫자는 입력 파일과 코드에서 다시 계산한다. 최종 실행 상태는 `research_v3/logs/v40_run_report.json`에 기록한다.

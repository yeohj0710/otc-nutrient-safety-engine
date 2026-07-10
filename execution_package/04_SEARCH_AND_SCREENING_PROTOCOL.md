# 검색·선별 실행 프로토콜

## 1. 검색식 개발 순서

1. 각 노드의 핵심 PICO를 한 문장으로 고정한다.
2. 알려진 포함 문헌 3–5편을 seed set으로 지정한다.
3. MeSH/Emtree와 제목·초록 자유어를 수집한다.
4. 질환·약물, 보충제·성분, 안전성 결과의 세 블록을 만든다.
5. 연구설계 필터는 누락 위험이 있으므로 기본 검색에는 사용하지 않거나 별도 민감도 검색으로 둔다.
6. seed set이 검색되는지 확인한다.
7. PRESS 항목으로 검토한다.
8. 플랫폼별 문법으로 번역하고 번역 검증표를 남긴다.

## 2. 노드별 최소 개념

| 노드 | 대상/상황 | 노출 | 결과 |
|---|---|---|---|
| A1 | warfarin, vitamin K antagonist | vitamin K, phylloquinone, menaquinone, supplement, intake change | INR, time in therapeutic range, bleeding, thrombosis |
| A2 | anticoagulant, antithrombotic, warfarin, DOAC, antiplatelet | omega-3, fish oil, EPA, DHA, icosapent ethyl | major bleeding, hemorrhage, clinically relevant bleeding |
| R1 | nephrolithiasis, urolithiasis, hypercalciuria | calcium supplement, calcium carbonate/citrate | stone incidence/recurrence, urinary calcium |
| R2 | nephrolithiasis, hypercalciuria, renal stone | vitamin D, cholecalciferol, ergocalciferol, calcium co-use | hypercalcemia, hypercalciuria, stone |
| R3 | nephrolithiasis, hyperoxaluria | vitamin C, ascorbic acid, supplement | urinary oxalate, calcium oxalate stone |

검색식은 초안이다. Codex가 실제 데이터베이스의 색인어와 seed 문헌을 확인해 수정한 뒤 프로토콜에 고정한다.

## 3. 실행 로그의 필수 필드

- database_name
- platform
- search_run_id
- node_id
- exact_query
- date_time_utc
- coverage_start/end
- language/date/design limits
- hit_count
- exported_count
- imported_count
- raw_file_path
- raw_file_sha256
- operator
- notes/error

`hit_count`, `exported_count`, `imported_count`가 다르면 이유가 없이는 Gate 2를 통과하지 못한다.

## 4. Google Scholar와 일반 웹 검색

Google Scholar는 주 검색 데이터베이스가 아니라 인용 추적·회색문헌 보완으로 사용한다. 질의, 날짜, 정렬 방식, 검토한 결과 범위, 개인화 최소화 조치를 기록한다. Scholar hit 수를 PRISMA의 데이터베이스 식별 수에 단순 합산하지 않는다.

## 5. 중복 제거 검증

- 자동 중복 후보와 사람이 확정한 중복을 분리한다.
- 동일 연구의 학회초록·등록자료·정식 논문은 삭제하지 말고 study family로 연결한다.
- 무작위 50쌍을 검토해 거짓 중복 제거를 확인한다.
- 중복 제거 스크립트의 버전과 임계값을 보존한다.

## 6. 선별 라벨

제목·초록 단계:

- `include`
- `exclude`
- `uncertain`

전문 단계의 표준 제외 사유:

1. wrong_population
2. wrong_exposure
3. wrong_outcome
4. wrong_study_design
5. not_human
6. not_oral_supplement
7. exposure_not_separable
8. duplicate_report
9. abstract_only_insufficient_data
10. full_text_unavailable_after_attempts
11. not_primary_or_contextual_evidence
12. other_with_explanation

전문 제외에는 하나의 주 사유만 지정한다. 보조 사유는 별도 메모에 둔다.

## 7. AI 우선순위와 인간 판정

AI는 각 기록에 다음을 반환한다.

- decision_proposal
- confidence
- criterion-by-criterion 판정
- 근거가 된 제목·초록 구절
- 부족한 정보

AI 출력은 `ai_predictions.csv`에 저장한다. 사람은 AI 판정을 보지 않은 blinded 조건과 본 조건을 구분해 골드셋을 만든다. 전체 선별에서 AI는 정렬만 바꾸며, 제외를 확정하지 않는다.

## 8. 원문 입수 기록

원문을 찾지 못한 경우 최소한 다음을 시도한다.

- 기관 구독 링크
- DOI/PMID 기반 검색
- 저자 공개본·PMC·기관 저장소
- 도서관 상호대차 가능 여부
- 연구등록자료

시도일과 결과를 기록한다. 단순히 `접근 제한`이라고 쓰고 제외하지 않는다.

## 9. PRISMA 산출

PRISMA 수치는 선별 테이블에서 자동 계산한다. 문서에 숫자를 직접 입력하지 않는다. 다음 관계를 자동 검사한다.

- identified = database + register + other methods
- records_after_dedup = identified - duplicates_removed
- screened = records_after_dedup - removed_before_screening
- reports_sought = title_abstract_included
- reports_assessed = reports_sought - reports_not_retrieved
- studies_included는 report 수와 구분

## 10. 중단 기준

검색이 너무 넓다는 이유로 상위 N개만 남기지 않는다. 검색식의 정밀도가 낮으면 개념 블록을 수정하고 전체 검색을 다시 실행한다. 수정 전후 검색식과 seed recall을 모두 보존한다.

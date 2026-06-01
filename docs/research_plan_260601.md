# 연구계획서

## 기본 정보

| 항목 | 내용 |
| --- | --- |
| 연구 주제명 | 일반의약품형 고함량 영양성분의 안전성 근거 매핑과 개인맞춤 조회 시스템 구축 |
| 영문 주제명 | Development of an Ingredient-Centered Evidence Mapping and Personalized Query System for Safety Evaluation of Over-the-Counter Nutrient Preparations |
| 연구자 | 권혁찬 |
| 실습기간 | 2026년 3월 3일 ~ 2026년 6월 19일 |
| 실습장소 | 연세대학교 약학대학 |
| 논문양식 | 실험 및 분석논문 |
| 담당교수 | 장민정 교수님 |

## 1. 연구 배경

고함량 비타민·미네랄 제제는 건강기능식품뿐 아니라 일반의약품 형태로도 널리 판매된다. 동일하거나 유사한 성분이 식품, 건강기능식품, 일반의약품 제형으로 동시에 유통되기 때문에 소비자는 제품 분류보다 성분명과 함량만 보고 복용을 결정하는 경우가 많다. 이 과정에서 지용성 비타민, 칼슘, 철분, 마그네슘, 비타민 B6 등은 용량과 개인 조건에 따라 안전성 문제가 발생할 수 있다.

기존 연구가 항응고제 복용자 또는 신장 관련 고위험군처럼 환자·질환 맥락을 기준으로 영양소 안전성을 좁혔다면, 본 연구는 성분 자체를 분석 단위로 설정한다. 즉 특정 환자군에서 출발하지 않고, 일반의약품형 고함량 영양성분 중 안전성 기준과 문헌 근거를 구조화하기 좋은 성분군을 선별한다.

이 접근은 “개인맞춤 안전성 조회 시스템”이라는 본질은 공유하지만, 연구 질문의 초점이 다르다. 본 연구는 고함량 영양성분 복용자가 자신의 성분, 함량, 병용 약물, 기저 상태를 입력했을 때 용량 초과, 상호작용, 이상반응 신호를 근거와 함께 확인할 수 있는 시스템 구축을 목표로 한다.

## 2. 연구 목적

본 연구의 목적은 일반의약품 또는 건강기능식품 형태로 사용되는 고함량 영양성분의 안전성 근거를 성분 중심으로 수집·구조화하고, 개인 조건에 따라 주의사항과 근거 문헌을 조회할 수 있는 시스템을 구축·검증하는 것이다.

세부 목적은 다음과 같다.

- 일반의약품형 고함량 영양성분 중 안전성 근거가 충분하고 임상적 주의가 필요한 성분군을 선별한다.
- 성분별 PICOS, 검색식, 포함·제외 기준, outcome, 문헌 선별 기준을 정리한다.
- PubMed API 기반 검색 pipeline으로 검색식, hit 수, 후보 문헌, 원본 응답을 재현 가능하게 기록한다.
- LLM은 초록 분류와 PICO 요소 추출 보조로만 사용하고, 최종 포함 여부와 안전성 규칙은 사람이 원문과 기준 자료를 대조해 결정한다.
- 선별된 근거를 결정적 규칙 엔진과 연결하여 웹 기반 조회 prototype으로 구현한다.

## 3. Research Question

1. 일반의약품 또는 건강기능식품으로 중복 유통되는 고함량 영양성분 중, 용량 또는 개인 조건에 따라 안전성 주의가 필요한 성분은 무엇인가?
2. 고함량 지용성 비타민·미네랄 성분은 어떤 이상반응, 상호작용, 용량 기준과 연결되는가?
3. 성분 중심으로 수집한 문헌 근거를 개인 조건 기반 안전성 조회 시스템으로 어떻게 구조화할 수 있는가?

## 4. 연구 대상 성분

| 성분군 | 후보 성분 | 선정 이유 | 주요 outcome |
| --- | --- | --- | --- |
| 지용성 비타민·칼슘 | vitamin D, calcium, vitamin A, vitamin E, vitamin K | 고함량 제제가 흔하고 지용성/미네랄 특성상 과량 문제가 비교적 명확함 | hypercalcemia, hypercalciuria, nephrolithiasis, toxicity, bleeding-related signal |
| B군 복합제 | vitamin B6, vitamin B12, benfotiamine, B-complex | 일반의약품 고함량 활성형 비타민 제제가 많고 B6는 용량 기반 신경독성 논의가 있음 | neuropathy, neurotoxicity, high-dose adverse effect |
| 미네랄 보충제 | iron, magnesium, calcium, zinc | OTC/건기식 경계 성분이며 위장관 이상반응과 흡수 상호작용이 자주 보고됨 | constipation, diarrhea, nausea, absorption interaction, overdose |

## 5. PICOS

| 구분 | 내용 |
| --- | --- |
| P | 고함량 비타민·미네랄 보충제 또는 일반의약품형 영양성분을 복용하는 성인 |
| I | vitamin D, calcium, vitamin B6/B-complex, iron, magnesium 등 경구 영양성분 |
| C | 미복용군, 저용량군, 권장량 이하 복용군, 또는 해당 위험 조건이 없는 비교군 |
| O | 용량 초과 독성, 신경병증, 고칼슘혈증/고칼슘뇨증, 신결석, 위장관 이상반응, 흡수·약물 상호작용, 주의·금기 기준 |
| S | systematic review/meta-analysis, RCT, cohort, case report/series, guideline/fact sheet, adverse event dataset을 포함한 evidence mapping |

## 6. 연구 방법

### 6.1 성분 중심 타겟 선정

기존 `knowledge_pack.json`은 탐색 자료로 사용하되, 권혁찬 연구의 최종 근거는 새 검색 로그에서 출발한다. 성분별 검색 hit 수, 문헌 유형, 안전성 outcome의 명확성, 시스템 규칙화 가능성을 기준으로 1차 타겟을 확정한다.

### 6.2 체계적 문헌검색

PubMed를 1차 데이터베이스로 사용하고, 검색식은 성분 block, 제품/제형 block, 안전성 outcome block으로 구성한다. 검색일, 검색식, hit 수, 저장한 후보 논문 수, raw response 경로를 `search_runs.csv`에 남긴다. 후보 문헌은 `retrieved_records.csv`에 PMID, 제목, 초록, 연도, 저널, DOI, URL 형태로 저장한다.

### 6.3 Screening 및 근거 추출

title/abstract 단계에서 다음 기준으로 선별한다.

- 포함: 경구 보충제/일반의약품형 영양성분, 사람 대상 또는 임상적으로 직접 해석 가능한 안전성 근거, 용량·이상반응·상호작용·주의 기준을 포함한 문헌
- 제외: 동물/세포 연구만 포함, 식품 섭취만 다룸, 안전성 outcome 부재, 성분과 무관한 질환 중심 논문

최종 포함 문헌에서는 population, supplement, dose, comparator, outcome, safety signal, locator를 추출한다.

### 6.4 시스템 구현

Next.js 기반 조회 시스템은 기존 결정적 규칙 엔진을 유지한다. 차이는 presentation과 연구 문서화의 초점이다. 사용자는 성분명, 복용 약물, 질환 상태, 용량 정보를 입력하고, 시스템은 관련 규칙과 근거를 분류해 보여준다.

### 6.5 LLM 활용

LLM은 초록 내 문장을 P/I/O/S 또는 안전성 후보 문장으로 분류하는 보조 도구로 둔다. 최종 안전성 판단, 금기 여부, severity, threshold는 사람이 원문과 공공 기준을 대조한 뒤 결정한다.

## 7. 진행계획

| 기간 | 수행 내용 |
| --- | --- |
| 6월 1주 | 연구 주제 분리, 성분 중심 연구계획서 작성, PubMed 검색 pipeline 실행 |
| 6월 2주 | title/abstract screening 기준 정리, 후보 문헌 1차 분류 |
| 6월 3주 | evidence extraction table 작성, safety rule 연결 초안 작성 |
| 7월 | PubMed 검색식 보완, Embase/Cochrane/공공자료 확장 검토 |
| 8월 | 성분별 근거표와 규칙 엔진 보강 |
| 9월~10월 | 시스템 검증, 임상 시나리오 테스트 |
| 11월~12월 | 논문 본문 작성, 참고문헌 정리, 최종 제출 |

## 8. 참고문헌 후보

1. Moher D, Liberati A, Tetzlaff J, Altman DG. Preferred Reporting Items for Systematic Reviews and Meta-Analyses: The PRISMA Statement. PLoS Med. 2009;6(7):e1000097.
2. National Institutes of Health, Office of Dietary Supplements. Dietary Supplement Fact Sheets.
3. European Food Safety Authority. Tolerable Upper Intake Levels for Vitamins and Minerals.
4. National Center for Complementary and Integrative Health. Using Dietary Supplements Wisely.
5. PubMed 검색 결과: `data/systematic_search/search_runs.csv`, `retrieved_records.csv`.

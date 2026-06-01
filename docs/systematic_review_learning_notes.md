# Systematic Review 학습 정리

## 핵심 개념

- Systematic Review는 정해진 질문과 기준에 따라 문헌을 검색, 선별, 추출, 종합하는 절차다.
- 중요한 것은 “논문을 많이 찾았다”가 아니라 “어떤 검색식으로, 어디서, 언제, 몇 건을 찾았고, 왜 제외했는지”를 재현 가능하게 남기는 것이다.
- 권혁찬 연구는 full SR이라고 과장하기보다 PRISMA 흐름을 참고한 체계적 문헌검색 및 evidence mapping으로 표현하는 것이 안전하다.

## PRISMA 관점에서 남겨야 할 것

| 단계 | 기록 |
| --- | --- |
| Identification | database, search date, exact query, hit count, raw response |
| Screening | title/abstract 기준, include/exclude/maybe, exclusion reason |
| Eligibility | full-text 검토 여부, 전문 제외 사유 |
| Included | 최종 포함 문헌, outcome, dose, safety signal, evidence locator |

## Abstract/Keyword classifier 공부 포인트

- 문헌 초록은 보통 background, objective, methods, results, conclusion 문장으로 나뉜다.
- PICO 자동화에서는 문장 단위로 P/I/C/O/S 후보를 먼저 분류하고, 이후 entity extraction으로 성분, 용량, outcome을 뽑는 구조가 많다.
- 권혁찬 연구에서는 다음 분류가 실용적이다.
  - ingredient sentence: vitamin D, calcium, pyridoxine 등 성분 언급
  - exposure/dose sentence: high dose, daily intake, mg/day 등
  - outcome sentence: hypercalcemia, neuropathy, constipation 등
  - safety judgment sentence: adverse event, toxicity, contraindication, warning 등

## 본 연구 적용 방식

1. PubMed API로 후보 문헌을 가져온다.
2. 제목/초록 문장에서 ingredient, dose, outcome 키워드를 규칙 기반으로 1차 태깅한다.
3. LLM은 PICO 후보 추출 초안을 만들 수 있지만 최종 판단자는 아니다.
4. 사람이 원문/초록을 확인해 screening_log와 evidence_extraction을 확정한다.

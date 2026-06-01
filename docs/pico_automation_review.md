# PICO 검색 자동화 논문 리뷰 메모

## 읽을 논문 후보

| 주제 | 문헌 | 본 연구에서 볼 점 |
| --- | --- | --- |
| PICO 검색전략 효과 | The impact of PICO as a search strategy tool on literature search quality | PICO를 검색식 설계에 쓰되 recall이 낮아질 수 있는 한계 |
| PICO 추출 | Towards precise PICO extraction from abstracts of randomized controlled trials using a section-specific learning approach | 문장 분류 후 NER로 PICO를 뽑는 2단계 구조 |
| SR 자동화 도구 | Tools to support the automation of systematic reviews: a scoping review | abstract screening과 data extraction 자동화의 성숙도 차이 |
| 데이터 추출 자동화 | Data extraction methods for systematic review (semi)automation: Update of a living systematic review | 자동 추출은 보조이며 사람 검증 절차가 필요함 |
| GenAI PICO 추출 | Automated Mass Extraction of Over 680,000 PICOs from Clinical Study Abstracts Using Generative AI | 대량 초록에서 PICO를 뽑는 가능성과 검증 필요성 |

## 권혁찬 연구에 맞춘 결론

- PICO 자동화는 검색식을 대신 만들어주는 도구가 아니라, 검색 질문을 분해하고 후보 문헌을 구조화하는 보조 절차로 설명하는 것이 타당하다.
- 성분 중심 연구에서는 일반적인 PICO보다 PEO 또는 PICOS 변형이 더 자연스럽다.
  - P: 고함량 영양성분 복용자
  - I/E: vitamin D, B6, iron 등 성분 노출
  - C: 저용량/미복용/권장량 이하
  - O: toxicity, neuropathy, hypercalcemia, GI adverse event
  - S: SR/MA, RCT, cohort, case report, guideline
- 실제 구현은 규칙 기반 keyword classifier와 LLM 보조 extraction을 혼합하는 것이 현실적이다.

## 구현에 넣을 수 있는 classifier 초안

| 라벨 | 예시 키워드 |
| --- | --- |
| INGREDIENT | vitamin D, cholecalciferol, calcium, pyridoxine, vitamin B6, iron, magnesium, zinc |
| DOSE | high dose, daily, mg/day, IU/day, upper intake level, overdose |
| OUTCOME | hypercalcemia, hypercalciuria, nephrolithiasis, neuropathy, constipation, diarrhea |
| SAFETY | adverse, toxicity, interaction, contraindication, warning, risk |
| STUDY_TYPE | systematic review, meta-analysis, randomized, cohort, case report |

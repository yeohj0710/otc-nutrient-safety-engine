# 프로토콜 v5.0 — MECIR 기준 문헌층 검색 재설계

- 상태: 채택, 2026-07-28 작성·연구자 결정으로 채택 (AM-OTC-002)
- 선행 트랙: v4.0 (`protocol-v4.0-full-ai.md`, AM-OTC-001) — 동결 보존, 비교용
- 개정 사유: v4.0 문헌층 검색식이 Cochrane Handbook 4장과 MECIR 검색 표준을 위반함

## 1. 무엇만 바꾸는가

**문헌층 검색식 설계만 바꾼다.** 나머지는 v4.0 그대로다.

| 항목 | v4.0 | v5.0 |
|---|---|---|
| 허가원문 계층(제품·성분·함량·복용조건·규칙 판정) | 결정론적 권위 | **변경 없음. 건드리지 않는다** |
| 문헌 질문 5개(Q01–Q05)의 범위·성분·규칙 대응 | 확정 | **변경 없음** |
| 검색식 블록 구조 | 성분 AND 결과 AND Humans[Mesh] | **P AND I** 만 |
| 선별 라벨·이층 주장 분리 | 확정 | 변경 없음 |
| 근거 결합·문장 로케이터·사이트 | v4.0 파이프라인 | 코드 재사용 |

이 연구의 기여는 허가원문 해석기가 아니라 **AI 문헌 근거층**이다. 그 근거층의 입구인
검색식이 표준을 벗어나 있었으므로, 입구만 다시 만든다.

## 2. v4.0 검색식의 결함

### 2.1 결과(O) 블록을 AND로 걸었다

Cochrane Handbook 4장은 PICO 전 요소를 검색식에 넣는 것을 권하지 않는다. 결과는 제목·초록에
기술되지 않는 경우가 많고 색인도 일관되지 않아, O 블록을 AND로 걸면 적격 연구를 놓친다.
기본 구조는 **P + I** 이다.

질문별 위반 내역:

| 질문 | 관측 hit | AND로 걸린 결과어 |
|---|---|---|
| Q01 아세트아미노펜 | 2,709 | `hepatotox*`, `"liver injury"` |
| Q02 NSAID | 683 | `"Gastrointestinal Hemorrhage"[Mesh]`, `"Peptic Ulcer"[Mesh]` |
| Q03 감기·알레르기 | 1,533 | `sedat*`, `drows*`, `hypertension`, `cardiovascular` |
| Q04 소화효소 | **104** | `"Drug-Related Side Effects..."[Mesh]`, `allergy`, `bleeding` |
| Q05 외용제 | 713 | `poison*`, `toxic*`, `adverse`, `bleeding` |

### 2.2 Q04 는 블록을 셋으로 걸었다

```
(성분 블록) AND (oral OR dyspepsia OR gastrointestinal OR "pancreatic insufficiency")
            AND (이상반응 블록) AND Humans[Mesh]
```

세 겹의 AND 로 104건까지 좁혀졌다. 전체 5개 질문 중 가장 심각한 손실이다.

### 2.3 `AND Humans[Mesh]` 를 다섯 질문 전부에 썼다

MeSH 색인이 아직 부여되지 않은 레코드(in-process, publisher-supplied, ahead-of-print)는
`Humans[Mesh]` 로 걸면 전부 탈락한다. 최신 문헌 손실이 크다.

동물 연구를 줄여야 한다면 표준 형태는 다음과 같다. 기본값은 **필터를 아예 쓰지 않는 것**이다.

```
NOT (animals[mh] NOT humans[mh])
```

### 2.4 용어 확장이 부족했다

성분 블록이 Q01 3개, Q02 5개, Q05 6개에 그쳤다. 상품명·약어·계열명·철자 이형·절단형이
거의 없다. 28개 성분 중 상당수는 검색식에 아예 등장하지 않는다.

### 2.5 원인

PICOS 생성 프롬프트(`picos_definition.json`의 `prompt`)에 다음 두 줄이 있었다.

```
For each question give P, I, C, O, S, a narrow PubMed query using MeSH and title/abstract terms
...
Retrieve human clinical evidence and safety outcomes
```

`narrow` 지시와 `safety outcomes` 요건이 검색식 설계에 그대로 반영됐고, 여기에 문헌 코퍼스
상한 10,000행이 겹쳐 검색식을 좁히는 방향으로 작동했다. 이 인과는 v5.0 결과 보고에 기록한다.

## 3. v5.0 검색식 설계 규칙 (강제)

1. **블록은 P AND I 둘만.** C 블록 금지. O 블록 금지.
2. **각 검색어를 P / I / O 로 명시 분류하고, O 로 분류된 용어는 전부 삭제한다.**
   분류표를 질문마다 보고서에 남긴다. 이것이 이번 개정의 핵심 산출물이다.
   - I(노출) = 성분·계열·병용 노출·복용 형태. `과량복용`·`중복복용`은 노출이므로 I 에 남긴다.
   - P(인구·상황) = 규칙이 정의하는 위험 상황. 임신·수유, 간질환, 신질환, 소화성궤양 병력,
     음주, 항응고제 사용, 소아, 고령, 고혈압, 운전자.
   - O(결과) = 간손상, 출혈, 독성, 졸림, 이상반응, 사망. **전부 삭제.**
3. **`AND Humans[Mesh]` 금지.** 동물 배제가 필요하면 `NOT (animals[mh] NOT humans[mh])` 만 허용.
4. **연구설계 필터 금지.** 증례보고·증례군도 안전성 근거로 적격이므로 설계로 자르지 않는다.
5. **언어 제한 금지. 출판유형 제한 금지.**
6. 날짜 제한은 v4.0 과 동일 기준만 유지한다. 새로 좁히지 않는다.
7. 각 블록은 **MeSH OR 자유어** 병렬 구성. MeSH 단독 금지.
8. 자유어는 `[tiab]` 이상 범위를 쓴다. 필요하면 `[tw]`.
9. **성분 블록은 서로 다른 검색어 25개 이상.** 아래를 모두 포함한다.
   - 일반명(INN), 국내 상품명의 영문 표기, 약어, 계열명
   - 미국식·영국식 철자 이형 (acetaminophen/paracetamol, sulfa-/sulph-)
   - 절단(`*`) 형태
   - 폐용어·구용어
   - 해당 질문에 배정된 **모든 개별 성분**. 28개 성분 중 어느 하나도 누락하지 않는다.
     한글 표기만 있는 성분은 영문 INN 을 조사해 매핑하고, 매핑 근거를 기록한다.
10. 절단어는 PubMed 변형 상한(600) 경고가 뜨지 않는지 확인하고, 뜨면 더 긴 어간으로 교체한다.
11. 각 질문 검색식마다 다음을 기록한다.
    - 최종 질의문 원문, SHA-256
    - ESearch hit count, 실행 시각(UTC)
    - 블록별 용어 목록·개수·P/I/O 분류
    - 규칙 1–10 각각에 대한 자기 점검 결과(통과/위반)
    - v4.0 대비 hit count 변화

## 4. 정밀도에 대한 기대

체계적 문헌고찰 검색의 정밀도는 낮은 것이 정상이다. 관련 없는 레코드가 대량으로 들어오는 것은
설계 실패가 아니라 의도된 결과이며, 걸러내는 일은 검색식이 아니라 선별 단계가 맡는다.
**hit count 가 크다는 이유로 검색식을 좁히지 않는다. 문헌 코퍼스 10,000행 상한은 폐기한다.**

## 5. 수행 절차

산출물은 전부 `research_v3/otc/literature/v5/` 아래에만 쓴다.

### Phase A — 검색식 작성과 건수 탐침 (인출 없음)

- 질문 5개 각각에 대해 §3 규칙을 만족하는 질의문을 작성한다.
- ESearch 로 hit count 만 받는다. EFetch 를 실행하지 않는다.
- `literature/v5/probe_report.json` 에 질문별 건수, P/I/O 분류표, 규칙 자기 점검 결과를 쓴다.
- **여기서 멈추지 않고 Phase B 로 진행한다.** 건수가 크다는 이유로 되돌아가 좁히지 않는다.

### Phase B — 인출과 코퍼스 구축

- 질문별 전량 인출. 원본 XML 과 `checksum.sha256` 을
  `literature/v5/searches/<QID>/<RUNID>/` 에 보존한다.
- `literature/v5/evidence_map.csv` 로 정규화한다. 중복 제거는 DOI, 없으면 제목 완전일치.
- `literature/v5/corpus_manifest.json` 에 행수·고유 논문수·질문별 분포를 쓴다.

### Phase C — 선별

- **분류기 층:** 결정적 텍스트 분류기가 코퍼스 43,207개 `(논문, 질문)` 쌍 전량에
  `retain`, `deprioritize`, `uncertain` 라벨을 부여한다. 분류기 원본은
  `screening/classifier_decisions.csv`에 변경 없이 보존한다.
- **분류기 점검 층:** 전임상 전용, 사람 노출, 성분 귀속, 초록 부재 등 실제 문헌 사례를
  포함한 불변식 20건 이상을 검사한다. AI 참조 기준과 다른 사례도 숨기지 않고 기록한다.
- **직접 재판정 층:** 분류기 `uncertain` 전수와 미리 정한 경계·대조 사례를 합쳐 최대
  5,000건을 제목과 초록만 보고 다시 판정한다. 재판정 라벨은 같은 `(논문, 질문)` 쌍의
  분류기 라벨을 덮어쓴다.
- 재판정 입력에서는 분류기 라벨과 선정 이유를 제거한다. 레코드마다 판정, 기존 사유 코드,
  확신도, 근거 기반(`abstract`/`title_only`)을 기록한다.
- 재판정 입력과 출력은 200건 배치로 실제 보존한다. 병렬 처리는 **한 질문 안에서만** 하고,
  질문은 Q01부터 Q05까지 순서대로 처리한다. 앞 질문의 배치 계약 검사가 모두 끝난 뒤 다음
  질문을 시작한다.
- 새 재판정 실행은 배치별 실행 영수증에 generation ID, agent/task ID, provider/model,
  시작·완료 시각, 프롬프트·입력·출력 SHA-256, 선행 질문 완료 상태 SHA-256을 기록한다.
  실행 영수증이 없으면 특정 에이전트 귀속, 실제 질문 순서, 질문 내 병렬 처리 완료를
  독립 검증된 사실로 보고하지 않는다.
- 재판정 프롬프트는 시작 시 한 번 동결하고 SHA-256을 기록한다. 정식 판정 중에는 바꾸지 않는다.
- 질문 하나를 끝낼 때마다 `research_v3/logs/v50_progress.json`에 완료 건수와 남은 건수를 갱신한다.
- 목표 건수를 채우지 못하면 실제 처리 건수와 실패 배치를 그대로 보고한다.

### Phase D — 하류 산출물

- v4.0 파이프라인 코드를 v5 경로로 재사용해 규칙–문헌 결합을 재생성한다.
- 규칙–문헌 연결마다 문장 로케이터(`abstract:sentence:N`)와 인용 문장이 있어야 하며,
  `scripts/research/otc/build_supporting_literature.py` 의 원문 대조 검증을 통과해야 한다.
- 사이트 배포는 하지 않는다. `release_ready` 는 false 를 유지한다.

### Phase E — 보고

- `research_v3/logs/v50_run_report.json` 단일 원장에 전부 기록한다.
- v4.0 대비 질문별 hit count 변화표를 포함한다 (Q04 104 → ? 형태).
- §2.5의 설계 근거(`narrow` 지시와 `safety outcomes` 요건이 검색식을 좁혔다는 가설)를
  기록한다. 코퍼스 중첩 분석 없이 검색 결과 변화의 원인으로 확정하지 않는다.
- `amendments.csv` 에 AM-OTC-002 를 추가한다.

## 6. 금지 사항

- 허가원문 계층(`research_v3/otc/normalized/`, `research_v3/otc/rules/`)과 규칙 판정 로직을
  **읽기만 하고 절대 수정하지 않는다.** 이번 개정은 문헌층만 다룬다.
- `research_v3/otc/literature/` 안에서 `v5/` 를 제외한 기존 산출물(picos, searches, screening,
  evidence_map.csv, prompts)을 **수정·삭제하지 않는다.** v4.0 은 비교 기준으로 보존한다.
- `research_v3/search/provisional_pubmed_20260710/` 를 수정하지 않는다.
- 사람 판단 산출물(`research_v3/screening/`, `research_v3/human_review_minimal/`,
  전문가 검토 산출물, `human_reference_label`)을 v5 체인에 넣지 않는다.
- AI 참조표준 기반 지표는 반드시 출처를 이름에 넣는다: `sensitivity_vs_ai_reference`,
  `specificity_vs_ai_reference`, `agreement_vs_ai_reference`. 맨 "민감도" 금지.
- `independent_blinding`(사람)은 false 유지한다. 입력에서 분류기 라벨과 선정 이유를 뺀 사실은
  `adjudication_input_blinded_to_classifier_labels`로 기록한다. 실행자·모델·세대 영수증이 없으면
  `independent_blinding_ai`를 true로 기록하지 않는다.
- 영양성분 계보 수치를 OTC 결과에 합산하지 않는다.
- 신신파스아렉스는 원자료 보존, 분석 제외.
- 판매량 자료가 없으므로 "판매량 상위" 표현 금지. "대표 일반의약품 후보"만 쓴다.
- 메타분석, 통합 효과크기, RoB, GRADE, 임상 권고를 만들지 않는다.
- 문헌은 근거 주장만 지지하며 허가사항 사실이나 규칙 판정을 뒤집지 못한다.
- hit count 를 줄이려고 §3 규칙을 완화하지 않는다.

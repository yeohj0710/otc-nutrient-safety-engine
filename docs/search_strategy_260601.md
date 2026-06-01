# 260601 Search Strategy

## 목적

권혁찬 연구는 성분 중심이므로 검색식도 질환/환자군에서 시작하지 않고 `ingredient block`을 먼저 둔다. 이후 `product/context block`과 `safety outcome block`을 붙여 일반의약품형 고함량 영양성분의 안전성 근거를 찾는다.

## 검색 데이터베이스

- 1차: PubMed/MEDLINE via NCBI E-utilities
- 후속 후보: Embase RIS export, Cochrane Library, NIH ODS, NCCIH, EFSA, MFDS, openFDA CAERS

## 타겟별 PubMed 검색식

### 1. high_dose_vitd_calcium

```text
(vitamin D[Title/Abstract] OR cholecalciferol[Title/Abstract] OR calcium[Title/Abstract])
AND
(supplement*[Title/Abstract] OR "dietary supplement"[Title/Abstract] OR over-the-counter[Title/Abstract] OR OTC[Title/Abstract])
AND
(hypercalcemia[Title/Abstract] OR hypercalciuria[Title/Abstract] OR kidney stone*[Title/Abstract] OR nephrolithiasis[Title/Abstract] OR toxicity[Title/Abstract] OR adverse[Title/Abstract])
```

의도: 지용성 비타민 D와 칼슘 조합의 고칼슘혈증, 고칼슘뇨증, 신결석, 과량 독성 신호를 확인한다.

### 2. b6_bcomplex_neuropathy

```text
("vitamin B6"[Title/Abstract] OR pyridoxine[Title/Abstract] OR "B complex"[Title/Abstract] OR benfotiamine[Title/Abstract])
AND
(supplement*[Title/Abstract] OR "dietary supplement"[Title/Abstract] OR over-the-counter[Title/Abstract] OR OTC[Title/Abstract])
AND
(neuropathy[Title/Abstract] OR neurotoxicity[Title/Abstract] OR toxicity[Title/Abstract] OR adverse[Title/Abstract])
```

의도: 고함량 B군 복합제, 특히 B6 관련 신경병증/신경독성 신호를 확인한다.

### 3. mineral_gi_interaction

```text
(iron[Title/Abstract] OR ferrous[Title/Abstract] OR magnesium[Title/Abstract] OR calcium[Title/Abstract] OR zinc[Title/Abstract])
AND
(supplement*[Title/Abstract] OR "dietary supplement"[Title/Abstract] OR over-the-counter[Title/Abstract] OR OTC[Title/Abstract])
AND
(constipation[Title/Abstract] OR diarrhea[Title/Abstract] OR "drug interaction"[Title/Abstract] OR absorption[Title/Abstract] OR adverse[Title/Abstract])
```

의도: OTC/건기식 경계 미네랄 성분의 위장관 이상반응과 흡수·약물 상호작용 근거를 확인한다.

## Screening 기준

### 포함

- 사람 대상 연구, systematic review/meta-analysis, RCT, cohort, case report/series, guideline/fact sheet
- 경구 영양성분/보충제/일반의약품형 제제를 다룸
- 안전성 outcome, 용량, 이상반응, 상호작용, 주의·금기 기준 중 하나 이상이 확인됨

### 제외

- 동물/세포 연구만 포함
- 식품 섭취 패턴만 다루고 보충제/제제 맥락이 없음
- 효능 연구이며 안전성 outcome이 없음
- 성분 자체가 아닌 질환 역학만 다룸

## 산출물

- `data/systematic_search/search_runs.csv`
- `data/systematic_search/retrieved_records.csv`
- `data/systematic_search/screening_log.csv`
- `data/systematic_search/evidence_extraction.csv`
- `data/systematic_search/raw/pubmed/*`

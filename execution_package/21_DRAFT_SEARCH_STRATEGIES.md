# 데이터베이스 검색전략 초안

이 문서는 바로 실행할 수 있는 최종 검색식이 아니라, 정보전문가 또는 동료 검토 전에 사용할 개념 블록 초안이다. 검색 결과를 본 뒤 임의로 좁히지 말고, seed 회수·노이즈 원인·변경 이력을 기록한 뒤 프로토콜 수정 절차를 따른다. 검색 단계에는 원칙적으로 연구설계 필터와 언어 필터를 적용하지 않는다.

## 1. 공통 절차

1. 각 노드는 독립 검색으로 실행하고 `clinical_node_id`를 부여한다.
2. MeSH/Emtree와 자유어를 함께 쓴다.
3. 약물·성분의 일반명, 염, 제형, 약어를 검토한다.
4. 안전성 결과 블록을 사용한 검색과 사용하지 않은 민감도 검색을 비교한다.
5. 알려진 적격 후보가 누락되면 어떤 개념 블록 때문에 누락됐는지 분석한다.
6. PubMed 식을 Embase, CENTRAL, Scopus/Web of Science 문법으로 단순 치환하지 말고 각 플랫폼의 통제어·근접연산자로 다시 작성한다.
7. 최종 검색식은 행 단위로 `templates/01_search_strategy.csv`에 보존한다.

## 2. A1: 와파린-비타민 K

### PubMed 개념 초안

```text
(
  "Warfarin"[Mesh]
  OR warfarin[tiab]
  OR "vitamin K antagonist"[tiab]
  OR "vitamin K antagonists"[tiab]
  OR VKA[tiab]
  OR coumarin*[tiab]
)
AND
(
  "Vitamin K"[Mesh]
  OR "vitamin K"[tiab]
  OR phylloquinone[tiab]
  OR phytonadione[tiab]
  OR menaquinone*[tiab]
  OR MK-7[tiab]
  OR supplementation[tiab]
  OR supplement*[tiab]
)
AND
(
  "International Normalized Ratio"[Mesh]
  OR INR[tiab]
  OR "time in therapeutic range"[tiab]
  OR TTR[tiab]
  OR anticoagulat*[tiab]
  OR bleed*[tiab]
  OR hemorrhag*[tiab]
  OR thrombo*[tiab]
)
```

### 핵심 적격성 주의

식이 비타민 K 연구와 보충제 연구를 분리한다. 안정적인 섭취 유지에 대한 연구, 결핍 보정, 저용량 비타민 K 투여, 보충제 시작·중단을 서로 다른 노출로 코딩한다.

## 3. A2: 항응고·항혈전 치료-오메가-3

### PubMed 개념 초안

```text
(
  "Fatty Acids, Omega-3"[Mesh]
  OR omega-3[tiab]
  OR omega 3[tiab]
  OR n-3[tiab]
  OR fish oil*[tiab]
  OR eicosapentaenoic acid[tiab]
  OR docosahexaenoic acid[tiab]
  OR EPA[tiab]
  OR DHA[tiab]
  OR icosapent ethyl[tiab]
)
AND
(
  "Anticoagulants"[Mesh]
  OR "Platelet Aggregation Inhibitors"[Mesh]
  OR anticoagula*[tiab]
  OR antithrombotic*[tiab]
  OR antiplatelet*[tiab]
  OR warfarin[tiab]
  OR apixaban[tiab]
  OR rivaroxaban[tiab]
  OR dabigatran[tiab]
  OR edoxaban[tiab]
  OR aspirin[tiab]
  OR clopidogrel[tiab]
)
AND
(
  "Hemorrhage"[Mesh]
  OR bleed*[tiab]
  OR hemorrhag*[tiab]
  OR haemorrhag*[tiab]
  OR "major bleeding"[tiab]
  OR "clinically relevant non-major bleeding"[tiab]
)
```

### 보완 검색

고용량 정제 EPA의 대규모 임상시험에서 항혈전제 하위집단 또는 출혈 결과가 보고될 수 있으므로, 약물 블록을 제외한 `omega-3 AND bleeding` 보완 검색을 별도 실행한다. 직접 병용 연구와 일반 안전성 신호를 같은 효과 합성에 자동으로 섞지 않는다.

## 4. R1: 신장결석·고칼슘뇨증-칼슘 보충제

```text
(
  "Kidney Calculi"[Mesh]
  OR nephrolithiasis[tiab]
  OR urolithiasis[tiab]
  OR "kidney stone"[tiab]
  OR "kidney stones"[tiab]
  OR hypercalciuria[tiab]
)
AND
(
  "Calcium, Dietary"[Mesh]
  OR "Calcium Carbonate"[Mesh]
  OR "calcium supplement"[tiab]
  OR "calcium supplements"[tiab]
  OR supplemental calcium[tiab]
  OR calcium carbonate[tiab]
  OR calcium citrate[tiab]
)
AND
(
  recurren*[tiab]
  OR incidence[tiab]
  OR urinary calcium[tiab]
  OR urine calcium[tiab]
  OR stone*[tiab]
)
```

식이 칼슘과 보충제 칼슘을 구분할 수 없는 연구는 노출 직접성이 낮다. 복용 시점(식사와 함께/공복), 총 칼슘 섭취, 수분 섭취, 결석 성분을 추출한다.

## 5. R2: 신장결석·고칼슘뇨증-비타민 D ± 칼슘

```text
(
  "Vitamin D"[Mesh]
  OR vitamin D[tiab]
  OR cholecalciferol[tiab]
  OR ergocalciferol[tiab]
  OR calcifediol[tiab]
  OR 25-hydroxyvitamin D[tiab]
)
AND
(
  "Kidney Calculi"[Mesh]
  OR nephrolithiasis[tiab]
  OR urolithiasis[tiab]
  OR kidney stone*[tiab]
  OR hypercalciuria[tiab]
  OR hypercalcemia[tiab]
)
AND
(
  supplement*[tiab]
  OR dose[tiab]
  OR dosing[tiab]
  OR trial[tiab]
  OR cohort[tiab]
  OR incidence[tiab]
  OR recurren*[tiab]
)
```

비타민 D 단독과 칼슘 병용을 분리하고, 일일·주간·월간 bolus 용량을 공통 단위로 변환하되 원래 투여 간격을 보존한다.

## 6. R3: 신장결석·고옥살산뇨증-비타민 C

```text
(
  "Ascorbic Acid"[Mesh]
  OR vitamin C[tiab]
  OR ascorbic acid[tiab]
  OR ascorbate[tiab]
)
AND
(
  "Kidney Calculi"[Mesh]
  OR nephrolithiasis[tiab]
  OR urolithiasis[tiab]
  OR kidney stone*[tiab]
  OR hyperoxaluria[tiab]
  OR urinary oxalate[tiab]
  OR urine oxalate[tiab]
)
AND
(
  supplement*[tiab]
  OR intake[tiab]
  OR dose[tiab]
  OR incidence[tiab]
  OR recurren*[tiab]
  OR calcium oxalate[tiab]
)
```

성별, 기저 결석 병력, 만성신장질환, 총 식이 섭취, 용량·기간을 핵심 효과수정자로 사전 지정한다.

## 7. 공공·규범 자료 검색

공공자료는 임상 데이터베이스 검색과 분리한다. 기관명, 문서 제목, 버전·개정일, 관할권, 접근일, 적용 대상, 권고 강도를 기록한다. 검색 엔진 결과나 2차 요약 페이지 대신 원 기관 문서를 저장한다.

## 8. 검색 품질 검증

- 최소 3–5개의 seed 후보를 노드별로 정하고 회수 여부를 확인한다.
- 검색식 변경 전후 hit 수만 비교하지 말고 seed 회수와 무작위 노이즈 표본을 함께 검토한다.
- 한 데이터베이스의 누락을 다른 데이터베이스의 대량 hit 수로 보상했다고 주장하지 않는다.
- 검색 업데이트는 최종 분석 전 4주 이내에 실행한다.
- 보고에는 전체 식, 검색일, 플랫폼, 제한, hit/export/import 수를 제시한다.

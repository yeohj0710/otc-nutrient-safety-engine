# v5.0 OTC 문헌 경계 사례 의미 재판정 기준

이 문서는 v5.0 분류기 층에서 선정한 경계 사례를 Codex 에이전트가 제목과 초록을 직접 읽고 다시 판정하는 동결 기준이다. 각 `(record_id, question_id)`를 독립적으로 판정한다. 분류기 라벨, 다른 판정, 사람 참조표준, 외부 모델은 보지 않는다. 원문 인용이나 단계별 증명은 출력하지 않는다.

## 출력 계약

입력 순서를 유지하고 레코드마다 다음 여섯 필드만 JSONL 한 줄로 출력한다.

- `record_id`: 입력값 그대로
- `question_id`: 입력값 그대로
- `decision`: `retain`, `deprioritize`, `uncertain` 중 하나
- `reason_codes`: 다음 8종 중 하나 이상을 담은 배열
  - `population`
  - `exposure`
  - `outcome`
  - `human_signal`
  - `design_signal`
  - `animal_term_present`
  - `insufficient_abstract`
  - `off_topic`
- `confidence`: `high`, `medium`, `low` 중 하나
- `evidence_basis`: 초록이 있으면 `abstract`, 없으면 `title_only`

제목만 있는 레코드의 `confidence`는 항상 `low`다. 설명, 인용문, 게이트, 자유 형식 근거는 출력하지 않는다.

## 판정 기준

- `retain`: 사람이 범위 내 성분이나 허용 계열에 실제로 노출됐고, 범위 내 안전성 결과·위해·무위해·상호작용·과량 또는 중복 사용·용량 위험·위험 인구집단을 해석할 수 있다.
- `deprioritize`: 범위 내 실제 노출이나 안전성 결과가 명확히 없거나, 다른 성분·다른 경로만 다루거나, 효능·약동학·분석법·기전·제조·수의학·동물 전용·시험관 전용 연구다.
- `uncertain`: 관련 가능성은 있으나 제목과 초록만으로 `retain`과 `deprioritize`를 구분할 수 없다.

결과어가 있다는 이유만으로 `retain`하지 않는다. 결과가 범위 내 노출에 귀속돼야 한다. 성분명이 있다는 이유만으로 `retain`하지 않는다. 실제 투여·복용·사용·중독·상호작용 등 노출이 있어야 한다. 사람과 동물이 함께 언급되면 사람 결과가 실제로 보고됐는지 확인한다. 초록이 충분한데 다른 성분이나 다른 연구 목적이 명확하면 `uncertain` 대신 `deprioritize`를 쓴다.

## 질문별 범위

### Q01 아세트아미노펜

경구 또는 경로 미상 acetaminophen/paracetamol/APAP의 실제 사용, 과량·중복·고용량·짧은 간격, 간질환·음주·소아·고령 상황과 간손상·독성·이상반응·응급진료·사망을 포함한다. 정맥주사 전용 효능 연구는 제외한다.

### Q02 NSAID

경구 또는 경로 미상 ibuprofen, dexibuprofen, naproxen 또는 적용 가능한 NSAID 계열의 실제 노출, 중복 NSAID, 임신·수유, 신질환, 궤양 병력, 항응고·항혈소판제 병용과 출혈·신장·임신·상호작용 안전성 결과를 포함한다. 비경구 전용 노출은 제외한다.

### Q03 감기·알레르기

경구 또는 경로 미상 cetirizine, chlorpheniramine/chlorphenamine, phenylephrine, pentoxyverine/carbetapentane, guaifenesin, caffeine 또는 적용 가능한 항히스타민·비충혈제거·진해·거담 계열의 실제 노출을 포함한다. 운전·기계 조작, 고혈압·심혈관질환, 진정제·중추신경 억제제 병용과 진정·정신운동·심혈관·상호작용·오남용 안전성 결과가 범위다.

### Q04 소화효소·소화제

경구 또는 경로 미상 pancreatin/pancrelipase/pancrealipase/PERT, Pancellase, Panprosin, Crease-PEG, Prozyme 6, 소화효소 제품, simethicone/simeticone, ursodeoxycholic acid/ursodiol/UDCA, bromelain 또는 적용 가능한 소화제 계열의 실제 노출과 사람 이상반응·알레르기·출혈·상호작용·장기 또는 반복 사용 안전성을 포함한다. 내인성 효소, 바이오마커, 분석법, 세포주, 산업용 효소는 제외한다.

### Q05 외용제

국소 methyl salicylate/wintergreen oil, menthol, camphor, Mentha arvensis/canadensis oil, thymol 또는 적용 가능한 외용 진통·자극 제품의 실제 사용을 포함한다. 반복·과다 사용, 소아, 항응고·항혈소판제 병용과 살리실산 독성·국소 반응·소아 중독·출혈·상호작용이 범위다. 경구 peppermint oil, 좀약, 향료, 세정 용도는 제외한다.

## 사유 코드 선택

- 판정에 실제로 기여한 긍정 신호만 `population`, `exposure`, `outcome`, `human_signal`, `design_signal`로 기록한다.
- 동물·시험관 용어가 제외나 불확실 판정에 기여하면 `animal_term_present`를 기록한다.
- 초록 부재나 부족이 판정에 기여하면 `insufficient_abstract`를 기록한다.
- 질문 범위를 명확히 벗어나면 `off_topic`을 기록한다.
- `deprioritize`에도 범위 내 성분이 단순 언급됐다면 `exposure`를 함께 쓸 수 있지만, 실제 노출로 오해하지 않는다.

# AI 보조 문헌고찰·라벨링 연구 프로토콜

## 1. 연구 목적

AI를 사용했다는 사실 자체가 연구 기여가 아니다. 사람의 판정과 비교해 어디에서 도움이 되고 어디에서 실패하는지 측정해야 한다. 본 연구는 AI를 세 단계에서 평가한다.

1. 제목·초록 선별 우선순위
2. 원문에서 구조화 필드와 근거 구절 추출
3. 근거에서 규칙 후보 생성 및 누락·충돌 탐지

최종 포함, 비뚤림 위험, GRADE, 규칙 승인, 임상 메시지는 사람이 결정한다.

## 2. 골드 스탠더드

### 선별 골드셋

- 최소 300건을 층화 표집한다.
- 포함 연구를 최소 60건 확보하도록 양성 기록을 과표집한다.
- 두 검토자가 AI 출력을 보지 않고 독립 판정한다.
- 불일치는 제3 검토 또는 합의로 해결한다.
- 100건 개발/교정, 200건 held-out 평가를 기본으로 한다.
- 같은 연구 family가 개발셋과 평가셋에 나뉘지 않도록 group split한다.

### 추출 골드셋

- 노드와 연구설계를 고르게 포함한 원문 30–50편 또는 전체 포함 연구
- 핵심 필드: population, medication, ingredient, formulation, dose, duration, comparator, outcome definition, events/total, effect estimate, uncertainty, locator
- 두 사람이 수치·단위·locator를 확인한 adjudicated table을 기준으로 한다.

## 3. 평가 조건

- 모델명과 정확한 버전 또는 API snapshot
- 실행일시와 지역
- system/user prompt 원문과 SHA-256
- temperature, top_p, seed 등 제공 가능한 매개변수
- 입력 텍스트 해시
- 원시 JSON 응답
- 재시도 횟수와 오류
- 비용·토큰은 운영 지표로만 보고

모델이 업데이트되면 같은 모델로 간주하지 않는다. 버전이 바뀐 결과를 섞지 않는다.

## 4. 비교 조건

최소 세 조건을 비교한다.

1. 단순 키워드/정규식 기준선
2. LLM zero-shot 또는 고정 few-shot
3. LLM + 명시적 포함기준 + 근거구절 강제 JSON

가능하면 active-learning ranking 또는 전통 분류기 기준선을 추가한다. 연구의 목표는 최고 점수 경쟁이 아니라 오류 특성과 안전한 사용 경계를 밝히는 것이다.

## 5. 선별 지표

- recall/sensitivity for include
- specificity
- precision/PPV
- NPV
- F1
- balanced accuracy
- confusion matrix
- 95% Wilson confidence intervals
- WSS@95 또는 같은 재현율에서 사람이 먼저 읽지 않아도 되는 비율
- 노드·연구설계·초록 길이별 하위집단 성능

정확도 하나만 보고하지 않는다. 양성 비율이 낮으면 높은 정확도가 무의미할 수 있다.

## 6. 추출 지표

- 범주형 필드 exact match 및 macro-F1
- 수치 필드: 값, 단위, 분모, 시점 각각의 정확도
- 허용 오차를 적용한 numeric match와 엄격 exact match를 모두 보고
- locator accuracy: 페이지·표·문단 위치가 실제 근거를 가리키는 비율
- unsupported extraction rate: 원문에 없는 값의 비율
- omission rate: 골드 필드 중 누락 비율
- human correction time은 선택적 운영 지표

## 7. 규칙 후보 생성 평가

AI가 생성한 규칙 후보는 다음 오류 유형으로 평가한다.

- population overgeneralization
- dose threshold invention
- association-to-causation leap
- source mismatch
- outdated normative threshold
- contraindication inflation
- uncertainty omission
- message too strong
- duplicate/conflicting rule

규칙 후보는 `draft_ai` 상태로만 저장되며, 인간 검토 없이 앱에 노출하지 않는다.

## 8. 안전장치

- 근거 구절과 locator 없이는 추출값을 수락하지 않는다.
- 모델이 `not reported`를 선택할 수 있게 한다.
- 문헌마다 독립 실행하고 다른 문헌의 내용을 섞지 않는다.
- 같은 모델의 자기검증만으로 정확성을 확정하지 않는다.
- 원문 텍스트가 길면 검색된 passage와 주변 문맥을 함께 제공하되, 페이지 경계를 보존한다.
- 저작권이 있는 원문 전체를 공개 저장소나 외부 프롬프트 로그에 노출하지 않는다.
- PHI·환자정보를 입력하지 않는다.

## 9. 논문에서의 보고

- AI가 수행한 일과 사람이 수행한 일을 표로 분리
- 모델과 프롬프트를 부록에 제시
- 골드셋 구성과 분할 방법 제시
- 모든 성능 지표와 신뢰구간 제시
- 실패 사례를 최소 10개 유형화
- 연구 결과 작성에 AI를 사용했다면 별도 사용 내역과 인간 검증 절차를 공개

## 10. AI 사용의 통과 조건

held-out 포함 재현율이 기준을 충족하지 못하면 AI는 선별 순서 추천에도 제한적으로만 사용한다. 추출 locator 정확도가 낮으면 AI 추출값은 연구 데이터가 아니라 후보 표시로만 사용한다. 성능을 개선하기 위해 평가셋을 프롬프트에 노출하면 새 held-out 셋을 만들어야 한다.

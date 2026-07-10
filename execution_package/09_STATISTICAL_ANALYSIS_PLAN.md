# 통계분석계획서

## 1. 분석 집단

- `screening_gold_dev`: 프롬프트·기준 교정용
- `screening_gold_test`: 최종 성능 보고용, 개발 중 접근 금지
- `extraction_gold_test`: 원문 필드 성능용
- `scenario_gold_test`: 규칙 엔진 독립 평가용
- `evidence_map_set`: 최종 포함 연구
- `focused_synthesis_set`: 집중 노드의 사전 기준 충족 연구

같은 연구 family 또는 동일 시나리오 변형이 개발셋과 평가셋에 동시에 들어가지 않게 한다.

## 2. 기술통계

- 검색원별 식별·중복·선별·포함 수
- 노드별 연구설계·국가·대상자·용량·결과 분포
- AI 데이터셋의 양성 비율과 텍스트 길이
- 규칙 수보다 released 규칙의 근거 확실성과 검토 상태 분포
- 시나리오의 노드·난도·행동 등급 분포

## 3. 합의도

- percent agreement
- Cohen κ
- 범주 불균형이 큰 경우 Gwet AC1을 보조
- 95% bootstrap 또는 적절한 신뢰구간

## 4. 분류 성능

정의:

```text
sensitivity = TP / (TP + FN)
specificity = TN / (TN + FP)
precision   = TP / (TP + FP)
NPV         = TN / (TN + FN)
F1          = 2 * precision * sensitivity / (precision + sensitivity)
```

- 이항 비율의 95% CI는 Wilson 방법
- 다중 행동 등급은 macro-F1과 클래스별 지표
- 같은 문헌/시나리오에 반복 측정이 있으면 cluster bootstrap 고려
- 모델 간 차이는 paired bootstrap 또는 McNemar test를 조건에 맞게 사용

## 5. 추출 성능

- 필드별 분모를 공개
- `not reported`를 오답과 누락으로 구분
- 숫자와 단위가 모두 맞아야 strict match
- 값만 맞는 relaxed match를 보조
- locator가 틀리면 근거 추적 정확도는 실패
- hallucination/unsupported rate 별도

## 6. 메타분석

집중 노드가 조건을 충족할 때만 수행한다.

- 주 효과척도와 우선 시점 사전 고정
- 랜덤효과 REML 기본
- Hartung-Knapp 보정은 연구 수와 분산 추정 안정성을 고려
- τ², I², Q, 예측구간
- leave-one-out와 높은 RoB 제외 민감도 분석
- 사전 하위집단만 확인적, 나머지는 탐색적
- 단위 변환과 데이터 변환 코드 공개

## 7. 결측

- 누락 이유를 구조화
- 저자 문의 여부 기록
- 효과치 재계산이 불가능한 연구를 임의 값으로 보완하지 않음
- 합성 제외와 연구 전체 제외를 구분

## 8. 전문가 평가

- I-CVI: 3 또는 4점으로 평가한 전문가 비율
- S-CVI/Ave: I-CVI 평균
- 패널 규모별 기준과 modified kappa를 사전에 기록
- 1차에서 기준 미달인 항목은 수정 후 2차 평가; 1·2차를 섞어 최종 수치만 제시하지 않음

## 9. 다중비교와 해석

이 연구의 중심은 성능 추정과 신뢰구간이다. 많은 하위집단 p값을 성공 근거로 사용하지 않는다. 탐색적 분석은 명시하고 효과 크기·불확실성을 중심으로 해석한다.

## 10. 분석 재현성

- 고정 환경 파일과 package lock
- random seed
- 원자료 체크섬
- 한 명령으로 표·그림·metrics manifest 생성
- 수동으로 편집한 결과 표 금지

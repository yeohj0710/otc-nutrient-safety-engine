# 독립 평가 실행 지침

## 역할 분리

1. 시나리오 작성자: 실제 사용 상황을 작성한다. 규칙 JSON과 개발 시나리오를 보지 않는다.
2. 독립 판정자: 각 상황의 기대 위해 항목을 정하고 서명한다. 구현 결과를 보지 않는다.
3. 데이터 관리자: `locked_before_test=true`로 잠그고 파일 SHA-256와 잠금 시각을 기록한다.
4. 실행자: 잠금 뒤 엔진 예측을 별도 파일로 생성한다.
5. 분석자: 잠긴 정답과 예측을 결합해 지표를 계산한다.

한 사람이 여러 역할을 맡으면 독립 평가로 주장하지 않는다.

## 최소 포함 상황

- 비타민 D: 경계값, 초과, 미만, 칼슘 병용·결석 관련 상담 필요 상황
- 비타민 B6: 복합제품 합산, 장기복용·감각 이상 상황
- 철: 원소 철 합산, 의료진 감독 치료, 위장관 증상 상황
- 마그네슘: 자연식품 제외, 보충제·제산제·완하제 급원, 신기능 관련 상황
- 아연: 복합제품 합산, 장기복용·구리 결핍 관련 상황
- 칼슘: 성별·19–29세·30세 이상 프로필, 경계값, 초과값
- 정상 단일 입력, 누락 입력, 미지원 성분

현재 규칙은 상한섭취량 초과만 다루므로 증상·질환 상황의 기대값을 억지로 초과 규칙에 맞추지 않는다. 미지원 위험은 오류 분석에서 별도로 보고한다.

## 파일 규칙

- 정답: `independent_scenarios.csv`
- 예측: 정답 파일과 같은 열 구조를 사용하되 `gold_hazards_json` 열에 엔진 예측 배열을 넣은 별도 파일
- 개인식별정보와 실제 환자 자료 금지
- `adjudicator_id`는 연구 내 가명 식별자 사용
- `adjudicated_at`은 ISO 8601
- JSON 배열은 규칙 ID 목록. 위해 없음은 `[]`

## 실행

```powershell
python scripts/research/evaluate_research_v3_independent.py `
  --scenarios research_v3/validation/independent_scenarios.csv `
  --predictions research_v3/validation/independent_predictions.csv `
  --output research_v3/validation/independent_results.json
```

시나리오가 0건이면 결과는 `not_evaluated`다. 잠금·판정자 정보가 없으면 `invalid`다. 자동 생성 자료를 사람 정답처럼 채우지 않는다.

## 보고 지표

- 민감도, 특이도, 양성예측도, 음성예측도, 정확도
- 각 비율의 Wilson 95% 신뢰구간
- TP, TN, FP, FN
- critical false negative
- 오류 유형과 지원 범위 밖 상황

성분 정규화 정확도, 제품 검색 성공률, 이해도, 과업 성공률, 소요시간, 오해율은 별도 실험이 필요하다. 이 스크립트가 계산하지 않은 값을 0 또는 1로 채우지 않는다.

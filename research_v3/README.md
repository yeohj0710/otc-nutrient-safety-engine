# research_v3

권혁찬(2021194024) 졸업논문의 국내 일반의약품 연구 계보다.

## 활성 연구

국내 실제 일반의약품의 제품명, 유효성분, 함량과 복용 조건을 구조화하고, 함께 복용하는 제품의 중복 성분·동일 약리군·용량·간격·연령·질환·병용약 위험 신호를 근거와 함께 조회하는 시스템을 개발·평가한다.

기존 비타민·무기질 연구는 `superseded`다. 영양성분 검색 결과, 규칙, 시나리오, 승인과 성능 수치를 활성 OTC 연구에 합산하지 않는다.

## 현재 데이터 범위

- 후보·허가 원문 마스터: 제품 16개, 고유 성분 31개, 제품-성분-규격 106행
- 분석·사이트 집합: 제품 13개, 고유 성분 28개, 계산 연결 47개
- 제품별 허가 복용 조건: 32개
- 안전성 규칙: released 15개, draft 1개
- released source/locator 연결률: 15/15(100%)
- 신신파스아렉스: 원문 보존, 분석·사이트 제외

## 평가 경계

13개 시나리오의 외부 확인 결과는 엔진과 모두 일치했지만 Codex 예상 답안이 평가자에게 노출되었다. 블라인드 독립평가가 아니므로 다음 상태를 유지한다.

- `independent_blinding=false`
- `performance_claim_allowed=false`
- `independent_evaluation_complete=incomplete`
- `complete=false`
- `release_ready=false`

## 주요 경로

- 제품·성분·복용 조건: `research_v3/otc/normalized`
- 안전성 규칙: `research_v3/otc/rules`
- 평가 자료: `research_v3/otc/validation`
- 감사 자료: `research_v3/otc/audit`
- 논문: `research_v3/thesis`
- 연구계획서: `research_v3/protocol`
- 핵심 보고서: `research_v3/reports`
- 재현 명령: `research_v3/REPRODUCE.md`

## 완료 상태

완료 조건 16개 중 15개를 충족하였다. 유일한 미완료 조건은 예측 비노출 블라인드 독립평가다. production 배포와 canonical 문서 승격은 연구 완료와 별개의 운영·문서 상태다.

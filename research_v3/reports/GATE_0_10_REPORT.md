# Gate 0-10 상태 보고서

기준일: 2026-07-15  
활성 방향: `korean_otc_product_safety`  
릴리스 상태: `release_ready=false`

| Gate | 상태 | 현재 증거 | 남은 조건 |
|---|---|---|---|
| 0 연구자·방향 | 통과 | 권혁찬·2021194024, OTC 방향, 영양성분 계보 superseded, 활성 혼입 감사 0건 | 없음 |
| 1 대표 OTC 선정 | 통과 | 보건복지부 지정 13품목, 식약처 허가 자료원, 규칙 범위 후보 분리, 판매량 상위 주장 금지 | 범위 확장 시 대표성 자료 추가 |
| 2 제품 데이터 | 통과 | 후보 16개, 현행 허가 14개, 분석 13개, 사이트 성분 28개, 계산 연결 47개 | 없음 |
| 3 허가 근거 재현성 | 통과 | 원시 HTML·PDF, URL, 수집 시각, SHA-256, 페이지·문단 locator | 임상문헌 전수검색은 현재 연구 범위 밖 |
| 4 정규화·추출 | 통과 | 복합제 분해, 액상제 환산, 사람 잠금 표준명 31/31, 사이트 집합 28/28 | 독립 이중검토 아님을 유지 |
| 5 규칙 근거 | 통과 | 16개 규칙 중 released 15개, draft 1개, released source/locator 15/15 | draft 장기복용 규칙 보완 |
| 6 독립 평가 | 미완료 | 비블라인드 외부 확인 13건, FP 0, FN 0, critical FN 0 | 예측 비노출 독립 평가 필요 |
| 7 사이트 사용성 | 통과 | 제품명 중심 입력, 제품별 성분·함량 자동 로드, 허가 복용 조건 32개, 반응형 UI | 실제 사용자 과업 연구는 후속 |
| 8 논문 정합성 | 통과 | 분석 13·28·47과 후보 16·31·106 분리, 평가 한계·사이트 설계 반영 | 없음 |
| 9 문서 품질 | 통과 | 논문 20쪽·연구계획서 12쪽 전 페이지 렌더 확인, 접근성 발견 사항 각 0건, Pretendard PDF 포함 확인 | 없음 |
| 10 소프트웨어·배포 | 통과 | 연구 테스트 106개, 앱 테스트 53개, lint, typecheck, production build 통과, 정적 경로 156개, production 배포 READY | 없음 |

Production URL: <https://otc-nutrient-safety-engine.vercel.app>

## 독립평가 관문

`review_method=codex_prefilled_external_human_confirmation`이고 `independent_blinding=false`다. 따라서 다음 상태를 유지한다.

- `independent_evaluation_complete=incomplete`
- `performance_claim_allowed=false`
- `complete=false`
- `release_ready=false`

## 신신파스아렉스 처리

신신파스아렉스는 오류가 반복되는 미해결 계산 후보로 남기지 않는다. 원자료와 49개 규격 행은 계보 증거로 보존하고, 분석·사이트 대상에서는 명시적으로 제외한다. 제외 제품 유입은 자동 감사에서 0건이어야 한다.

# 현재 상태 - 2026-07-27 v4.0 부분 실행

> 이번 실행은 PubMed 검색까지 완료했고 AI 선별은 300/5,724행에서 중단했습니다. AI 참조표준과 규칙엔진 맹검평가는 실행하지 않았으므로 `complete=false`, `performance_claim_allowed=false`, `release_ready=false`입니다.

## 핵심 수치

- 허가원문 결정층: 제품 13개, 성분 28개, 계산 연결 47개, 복용 조건 32개
- 규칙: 전체 16개, released 15개
- AI PICOS: 5개
- PubMed: 질문별 hit 합계 5,742건, 고유 PMID 5,724개
- 문헌 형태: 초록 보유 5,424개, 제목만 300개
- AI 선별: 300행, 커버리지 5.24%
- 판정 분포: retain 13, deprioritize 270, uncertain 17

## 방법 요약 - 두 층을 섞지 않음

식약처 허가원문은 제품, 성분, 함량, 복용 조건과 규칙 판정을 결정합니다. PubMed 문헌은 위해 연관성을 설명하는 참고 근거입니다. 문헌이 허가 판정을 바꾸지 않습니다. 사람 판정 자료는 이전 계보로 보존하고 v4.0 입력이나 정답으로 연결하지 않았습니다.

## 선별 성능과 맹검평가

현재 성능 수치는 없습니다. 선별기의 AI 참조표준 채점과 규칙엔진 AI 맹검 독립평가를 시작하지 않았습니다. 기존 페이지의 “사람 맹검 독립평가 미완료” 조건은 AM-OTC-001에서 AI 평가로 대체됐지만, AI 평가 자체가 아직 끝난 것은 아닙니다.

## 상태 경계와 한계

- `independent_blinding_ai=false`: AI 맹검평가 미실행
- `independent_evaluation_ai_complete=false`: 평가 미실행
- `performance_claim_allowed=false`: 성능 주장 근거 없음
- `complete=false`: P2, P3, P4 미완료
- `release_ready=false`: 임상 배포 준비와 연구 종결은 별개
- 사람 판정 0건, PubMed 단일 자료원, 선별 커버리지 5.24%

## 코드·배포

P0과 P1은 Git 커밋으로 보존했습니다. P2는 append-only 체크포인트 3개까지 저장했습니다. 이번 실행에서는 사이트 코드를 바꾸거나 배포하지 않았습니다. 다음 실행에서 P2 100% 완료 뒤 P3과 P4를 진행합니다.

## 공식 문서 위치

- `research_v3/protocol/protocol-v4.0-full-ai.md`
- `research_v3/otc/literature/picos/picos_definition.json`
- `research_v3/otc/literature/evidence_map.csv`
- `research_v3/otc/literature/screening/screening_manifest.json`
- `research_v3/logs/v40_run_report.json`

## 결론

AI 자율 질문 설계와 PubMed 코퍼스 구축은 끝났습니다. 전체 AI 선별과 독립평가가 남았습니다. 완료하지 않은 수치는 추정하지 않고 null로 남깁니다.

Reference basis: Toss `loan-101` explanatory article family.

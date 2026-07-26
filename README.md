# 국내 일반의약품 안전성 조회 연구

이 저장소는 국내 일반의약품을 제품명으로 입력해 중복 성분, 최대용량, 복용 간격, 연령, 질환과 병용약 위험 신호를 찾는 연구용 시스템이다.

## 두 근거층

- 식약처 허가원문은 제품, 성분, 함량, 복용 조건과 규칙 판정을 결정한다.
- PubMed 문헌은 위해 연관성을 설명하는 참고 근거다. 문헌은 허가 판정을 바꾸지 않는다.

현재 허가원문 분석 집합은 제품 13개, 성분 28개, 계산 연결 47개, 복용 조건 32개다. released 규칙 15개는 source와 locator를 가진다.

## v4.0 상태

AI가 PICOS 질문 5개를 만들고 PubMed에서 고유 PMID 5,724개를 수집했다. 로컬 AI 선별은 300행(5.24%)까지 끝났다. 전체 선별과 AI 참조표준·맹검평가가 미완료이므로 `complete=false`, `performance_claim_allowed=false`, `release_ready=false`다.

## 주요 경로

- 허가원문 연구 데이터: `research_v3/otc/`
- AI PICOS: `research_v3/otc/literature/picos/picos_definition.json`
- PubMed 코퍼스: `research_v3/otc/literature/evidence_map.csv`
- AI 선별 체크포인트: `research_v3/otc/literature/screening/`
- 규칙: `research_v3/otc/rules/rules.csv`
- 실행 보고서: `research_v3/logs/v40_run_report.json`

## 코드와 배포

- GitHub: https://github.com/yeohj0710/otc-nutrient-safety-engine
- 기존 공개 주소: https://otc-nutrient-safety-engine.vercel.app
- 이번 실행에서는 사이트를 변경·검증·배포하지 않았다.

## 검증 명령

```powershell
.\.venv-research\Scripts\python.exe -m pytest tests\research -q
npm run typecheck
npm run lint
npm test
npm run build
```

배포는 별도 승인 범위다. 이 실행에서는 배포하지 않는다.

이 시스템은 연구용 프로토타입이며 의료진의 진단이나 복약 결정을 대체하지 않는다.

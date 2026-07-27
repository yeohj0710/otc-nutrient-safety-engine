# 국내 일반의약품 안전성 조회 연구

이 저장소는 국내 일반의약품을 제품명으로 입력해 중복 성분, 최대용량, 복용 간격, 연령, 질환과 병용약 위험 신호를 찾는 연구용 시스템이다.

## 두 근거층

- 식약처 허가원문은 제품, 성분, 함량, 복용 조건과 규칙 판정을 결정한다.
- PubMed 문헌은 위해 연관성을 설명하는 참고 근거다. 문헌은 허가 판정을 바꾸지 않는다.

허가원문 분석 집합은 제품 13개, 성분 28개, 계산 연결 47개, 복용 조건 32개다. 규칙 16개 중 released 15개는 source와 locator를 가진다.

## v4.0 상태

AI가 PICOS 질문 5개를 만들고 PubMed에서 고유 PMID 5,724개를 수집했다. 코퍼스 전체를 선별해 커버리지 1.0을 달성했고 사람 판정은 0건이다. 선별의 AI 참조표준 대비 F1은 0.8484, 규칙엔진의 AI 참조표준 대비 특이도는 1.0000, 민감도는 0.5702다.

상태는 `complete=true`, `performance_claim_allowed=true`이며, 성능 수치를 인용할 때는 **AI 참조표준 대비**라는 사실과 평가자가 사람이 아니라는 사실을 함께 적어야 한다. `independent_blinding=false`, `release_ready=false`다.

## 주요 경로

- 허가원문 연구 데이터: `research_v3/otc/`
- AI PICOS: `research_v3/otc/literature/picos/picos_definition.json`
- PubMed 코퍼스: `research_v3/otc/literature/evidence_map.csv`
- 문헌 선별: `research_v3/otc/literature/screening/`
- AI 참조표준: `research_v3/measurement/screener_vs_ai_reference.json`
- 규칙엔진 맹검평가: `research_v3/otc/validation/ai_independent_evaluation.json`
- 규칙과 문헌 근거: `research_v3/otc/rules/`
- 실행 보고서: `research_v3/logs/v40_run_report.json`

## 코드와 배포

- GitHub: https://github.com/yeohj0710/otc-nutrient-safety-engine
- 공개 주소: https://otc-nutrient-safety-engine.vercel.app
- 사용자 지시로 production 에 배포했다. 공개 주소는 https://otc-nutrient-safety-engine.vercel.app 이고 배포 ID 는 dpl_HMaDTKgkxYzRrt1pTzjCSfPS3Ti9 다. 사이트 배포는 연구 상태 플래그 release_ready 와 별개이며 release_ready 는 임상 배포 승인 절차를 뜻하므로 false 를 유지한다.

## 검증 명령

```powershell
.\.venv-research\Scripts\python.exe -m pytest tests\research -q
npm run typecheck
npm run lint
npm test
npm run build
```

최근 실행에서 연구 시험 192개, 앱 시험 73개가 통과했고 정적 경로 156개를 생성했다.

이 시스템은 연구용 프로토타입이며 의료진의 진단이나 복약 결정을 대체하지 않는다.

# 국내 일반의약품 안전성 조회 연구

이 저장소는 국내 일반의약품을 제품명으로 입력해 중복 성분, 최대용량, 복용 간격, 연령,
질환과 병용약 위험 신호를 찾는 연구용 시스템이다.

## 먼저 구분할 두 연구 상태

- 제출한 최종 연구는 v5.0이다. 정본은 `research_v3/`이며 수정하지 않는다.
- v5.1은 v5.0 정본을 기준으로 안전 범위와 화면 표시를 점검하는 로컬 확장이다.
  v5.1은 제출 최종본이나 임상 배포본이 아니다.

버전별 정본과 수치는 `docs/version_map.md`에서 확인한다.

## 두 근거층

- 식약처 허가원문은 제품, 성분, 함량, 복용 조건과 규칙 판정을 결정한다.
- PubMed 문헌은 위해 연관성을 설명하는 참고 근거다. 문헌은 허가 판정을 바꾸거나 규칙을
  release하지 않는다.

허가원문 분석 집합은 제품 13개, 성분 28개, 계산 연결 47개, 복용 조건 32개다. 규칙
16개 중 released 15개는 source와 locator를 가진다.

## v5.0 제출 최종 상태

v5.0은 질문별 PubMed 검색 결과 43,249건을 수집했다. 문헌정보 중복을 정리한 뒤 질문별 선별
단위는 43,207건, 고유 논문은 42,822편이었다. 최종 판정은 retain 7,875건, deprioritize
34,965건, uncertain 367건이다. 5,000건을 재판정했고 채점 arm은 894행이다. 문헌은 규칙
16개 중 9개에 10건을 연결했다.

채점 arm의 `agreement_vs_ai_reference`는 86.93%, `sensitivity_vs_ai_reference`는 46.92%,
`specificity_vs_ai_reference`는 95.84%, Cohen κ는 0.493이다. 이 값은 사람 기준 임상 정확도가
아니라 AI 참조표준 대비 결과다. v5.0 semantic adjudication selection의
`independent_blinding_ai=false`이며 `release_ready=false`다.

## 로컬 v5.1 안전 확장

v5.1 기준선은 commit `6dbdad518e2fa7b2ed7b9a8048e0c47dba5b6ae9`이다. v5.1은 제품
13개, released 규칙 15개와 허가 복용 조건 32개를 유지한다. 안전 규칙이 없는 10개 제품 중
9개는 용량만, 1개는 용량·간격만 확인한다. 나머지 3개는 질환·병용약 등 제한된 조건도
확인한다.

허가문구 후보–규칙 연결 360건은 고유 논문 수나 검증 완료 근거 수가 아니다. 고유 원문 위치는
328곳이다. 연결 360건 중 15건은 v5.0에서 사람 전문가인 약사가 검토한 기존 released 규칙의
운영 근거다. 나머지 345건은 비활성이다. 비활성 후보는 `needs_expert_review` 33건,
`provisional` 308건, 제외 제품의 `rejected` 4건이다. v5.1에서 새로 활성화한 규칙이나 후보는
없고 `release_ready=false`다.

v5.0에서 결과에 사용한 문헌 링크 10건은 v5.1에서 정확한 직접 일치 1건, 범위를 함께 밝혀야
하는 직접 문헌 4건, 배경 문헌 5건으로 나눴다. v5.0에서 거절한 링크 10건은 결과 화면에서
제외한다. v5.1은 논문 검색·스크리닝 모수를 바꾸지 않는다. 문헌은 어느 분류에서도 규칙
release 권한을 갖지 않는다.

## 보존된 v4.0 비교 기록

v4.0에서 AI가 PICOS 질문 5개를 만들고 PubMed 고유 PMID 5,724개를 수집했다. 코퍼스 전체를
선별해 커버리지 1.0을 달성했고 사람 판정은 0건이다. 선별의 AI 참조표준 대비 F1은 0.8484,
규칙엔진의 AI 참조표준 대비 특이도는 1.0000, 민감도는 0.5702다.

v4.0 기록의 상태는 `complete=true`, `performance_claim_allowed=true`다. 성능 수치를 인용할
때는 **AI 참조표준 대비**라는 사실과 평가자가 사람이 아니라는 사실을 함께 적어야 한다.
`independent_blinding=false`, `release_ready=false`다. 당시 검증에서는 연구 시험 192개와 앱
시험 73개가 통과했고 정적 경로 156개를 생성했다. 이 수치를 현재 v5.1 검증 결과로 쓰지 않는다.

## 주요 경로

- v5.0 제출 정본과 실행 원장: `research_v3/`, `research_v3/logs/v50_run_report.json`
- v5.0 MECIR 문헌층: `research_v3/otc/literature/v5/`
- v5.1 프로토콜과 상태 계약: `research_v51/protocol/README.md`
- v5.1 근거 후보와 운영 범위: `research_v51/evidence/`
- v5.1 전문가 검토 큐: `research_v51/review/`
- v5.1 문헌 분류: `research_v51/literature/link_classification.csv`
- v5.1 기계 감사와 지원 행렬: `research_v51/audit/`
- v5.1 최종 보고서: `research_v51/reports/FINAL_REPORT.md`
- 재현 명령 안내: `REPRODUCE.md`

## 코드와 배포

- GitHub: https://github.com/yeohj0710/otc-nutrient-safety-engine
- 공개 주소: https://otc-nutrient-safety-engine.vercel.app
- 사용자 지시로 production에 배포했다. 배포 ID는 `dpl_A1YDFPUijJCXWnVKdojUxP4pEZvn`이다.
  사이트 배포와 임상 배포 승인은 다르므로 `release_ready=false`를 유지한다.
- 로컬 v5.1 작업은 push, PR 생성 또는 production 배포를 하지 않는다.

## 검증

버전별 실행 순서와 네트워크가 필요한 검사는 `REPRODUCE.md`를 따른다. 코드 전체 검증 명령은
다음과 같다.

```powershell
.\.venv-research\Scripts\python.exe -m pytest -q
npm run typecheck
npm run lint
npm test
npm run build
```

이 시스템은 연구용 프로토타입이며 의료진의 진단이나 복약 결정을 대체하지 않는다.

Reference basis: tossfeed-easy-finance

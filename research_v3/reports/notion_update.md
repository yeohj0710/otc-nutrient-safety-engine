# 현재 상태 - v4.0 최종

> PubMed 코퍼스 5,724행을 전부 선별해 커버리지 1.0을 달성했고, AI 참조표준 채점과 규칙엔진 AI 맹검 독립평가까지 끝났습니다. `complete=true`, `performance_claim_allowed=true`입니다. 다만 성능 수치는 **AI 참조표준 대비** 값이며 사람 평가가 아닙니다. `independent_blinding=false`, `release_ready=false`를 유지합니다.

## 핵심 수치

- 허가원문 결정층: 제품 13개, 성분 28개, 계산 연결 47개, 복용 조건 32개
- 규칙: 전체 16개, released 15개
- AI PICOS: 5개 · 질문별 hit 합계 5,742건 · 고유 PMID 5,724개
- 문헌 형태: 초록 보유 5,424개, 제목만 300개
- 선별: 5,724행, 커버리지 1.0, 배치 115개, 사람 판정 0건
- 판정 분포: retain 2,240 · deprioritize 3,423 · uncertain 61
- 선별의 AI 참조표준 대비: 민감도 0.8482 · 특이도 0.9047 · F1 0.8484 (층화 표본 300건)
- 규칙엔진의 AI 참조표준 대비: 특이도 1.0000 · 정밀도 1.0000 · 민감도 0.5702 · F1 0.7263 (채점 210건)
- 위양성 0건 · 위음성 49건
- 문헌 근거: 규칙 16/16개 연결, 링크 20건, 논문 19편, 보존한 충돌 4건

## 방법 요약 - 두 층을 섞지 않음

식약처 허가원문은 제품, 성분, 함량, 복용 조건과 규칙 판정을 결정합니다. PubMed 문헌은 위해 연관성을 설명하는 참고 근거이며 허가 판정을 바꾸지 못합니다. 사람 판정 자료는 이전 계보로 보존하고 v4.0 입력이나 정답으로 연결하지 않았습니다.

문헌 선별은 에이전트가 배치 카드를 직접 읽고 직접 기록했습니다. 지역 언어모델을 띄우지 않았고 외부 LLM API를 호출하지 않았으며 하위 에이전트에 위임하지 않았습니다.

## 성능 수치를 읽는 법

- 모든 지표는 **AI 참조표준 대비 재현도**입니다. 절대적 진실 대비 정확도가 아닙니다.
- 분류기와 참조표준을 같은 에이전트가 수행했으므로 평가자 독립성이 부분적입니다. 절차적 맹검(무라벨 사례, 별칭 카드, 라운드별 무작위 순서, 잠금 후 예측 연결)은 갖췄습니다.
- 라운드 간 일치도가 높은 것은 같은 평가자가 같은 규칙을 재적용했기 때문이며 평가자 간 신뢰도가 아닙니다.

## 위음성이 몰린 지점

위양성은 0건으로, 허가 근거 없이 경고하는 경우는 관찰되지 않았습니다. 위음성 49건은 8개 규칙 유형에 몰려 있습니다(pregnancy_lactation 9건, sedative_medication 7건, anticoagulant_antiplatelet 6건). 모두 규칙이 대표 제품 하나에만 묶여 있어 같은 주의가 적힌 다른 제품에서 발동하지 않는 경우이며, 판정 논리의 오류가 아니라 규칙 바인딩 범위의 공백입니다.

## 상태 경계

- `independent_blinding_ai=true`: AI 맹검평가 완료
- `performance_claim_allowed=true`: AI 참조표준 대비라는 사실을 병기하는 조건부 허용
- `complete=true`
- `independent_blinding=false`: 사람 블라인드 평가는 수행되지 않음
- `release_ready=false`: 임상 배포 승인 절차는 연구 범위 밖

## 한계

AI 참조표준 대비 재현도라는 점, 분류기와 참조표준의 부분적 독립성, PubMed 단일 자료원, 판매량 자료 부재(제품 13개는 대표 일반의약품 후보), 복용 조건 32개가 허가원문 검증까지만 완료됐다는 점입니다.

## 검증

연구 시험 192개와 앱 시험 73개가 통과했고 lint·타입 검사·빌드도 통과했습니다. 정적 경로는 156개입니다.

사용자 지시로 production 에 배포했습니다. 공개 주소는 https://otc-nutrient-safety-engine.vercel.app 이고 배포 ID 는 dpl_HMaDTKgkxYzRrt1pTzjCSfPS3Ti9 입니다. 사이트 배포는 연구 상태 플래그 release_ready 와 별개이며, release_ready 는 임상 배포 승인 절차를 뜻하므로 false 를 유지합니다.

## 공식 문서 위치

- `research_v3/protocol/protocol-v4.0-full-ai.md`
- `research_v3/otc/literature/picos/picos_definition.json`
- `research_v3/otc/literature/screening/screening_manifest.json`
- `research_v3/measurement/screener_vs_ai_reference.json`
- `research_v3/otc/validation/ai_independent_evaluation.json`
- `research_v3/otc/rules/literature_link_manifest.json`
- `research_v3/logs/v40_run_report.json`

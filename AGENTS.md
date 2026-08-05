<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## 어떤 버전이 최종인가

`docs/version_map.md`를 기준으로 판단한다. 이 저장소의 **제출 최종 연구는 v5.0**이고,
`nutrition-safety-engine`의 여형준 영양성분 연구는 v4.0이 최종이다. 이 저장소의
`research_v3/logs/v40_run_report.json`은 v5.0이 대체한 선행 트랙이다. 두 저장소의 수치를
파일명만 보고 섞지 않는다.

로컬 v5.1은 제출 최종본이 아니라 안전 범위 확장 트랙이다. v5.0 정본은 `research_v3/`,
v5.1 산출물은 `research_v51/`에 둔다.

## 프로젝트 탐색

저장소를 처음 탐색할 때는 `docs/project_map.md`를 먼저 읽는다.

- 메인 페이지: `app/page.tsx`
- 메인 클라이언트 UI: `src/components/rule-explorer-client.tsx`
- OTC 조회 UI: `src/components/otc-product-safety-client.tsx`
- 결과 카드 UI: `src/components/rule-card.tsx`
- 기존 안전 엔진: `src/lib/safety-engine/index.ts`
- OTC 규칙 엔진: `src/lib/otc/engine.ts`
- 지식 로더와 정규화: `src/lib/knowledge/`
- 이전 데이터 원본: `data/knowledge_pack.json`
- 현재 OTC 런타임: `src/generated/otc-runtime.json`
- 이전 런타임 인덱스: `src/generated/knowledge-index.json`
- v5.1 프로토콜: `research_v51/protocol/README.md`
- 프로젝트 지도: `docs/project_map.md`

## v5.0 제출 정본 경계

- 연구 질문은 국내 일반의약품의 제품명 기반 안전성 조회다.
- 식약처 허가자료가 제품, 성분, 함량, 복용 조건과 규칙 판정의 결정 근거다.
- PubMed는 AI가 선별한 별도 설명 근거층이다. 문헌은 허가 사실이나 released 규칙 논리를
  덮어쓰지 않는다.
- v5.0 문헌층은 규칙 16개 중 9개에 링크 10건을 연결한다. 미연결 규칙은
  `OTC-RULE-003` max_daily_dose, `009` gi_bleeding_ulcer, `010` sedation_driving,
  `011` alcohol, `013` sedative_medication, `015` maximum_duration, `016` urgent_referral이다.
- 미연결 사유는 `research_v3/otc/literature/v5/downstream/literature_link_manifest.json`에
  기록돼 있다. 후보 거절 6건(고유 논문 5편)은 `not_in_v5_corpus`이고, 4건은
  `no_retain_decision_for_rule_question`이다. `015` 후보 두 편은 Q01에서 retain이지만 규칙이
  허용하는 질문은 Q03·Q04다.
- 미연결은 검색 기간 공백이 아니다. 실제 필터는 Q01~Q03 2010/01/01 이후,
  Q04~Q05 2000/01/01 이후이며 해시한 질의문에 포함된다. v5.0 코퍼스의 출판연도는
  2000~2026이고, 미연결 후보 9편은 모두 해당 규칙의 허용 질문 기간 안에 있다.
  AM-OTC-003의 2022-01-01 원인 설명은 `AM-OTC-004`가 정정했다. 이 공백은 결과로 보고하고
  문헌층 자체를 연구 기여로 쓰지 않는다.
- 허가 근거와 문헌 근거는 별도 필드에 둔다. 충돌은 `conflict`로 보존한다.
- 규칙–문헌 링크는 문장 locator(`abstract:sentence:N`)와 인용 문장을 가져야 한다.
  `scripts/research/otc/build_supporting_literature.py`가 빌드마다 코퍼스 초록과 대조한다.
- v5.0 문헌 정본은 `research_v3/otc/literature/`에 있으며 읽기 전용이다.
  `research_v3/search/provisional_pubmed_20260710/`도 수정하지 않는다.
- `research_v3/screening/`, `research_v3/human_review_minimal/`, 전문가 검토 산출물과
  `human_reference_label`은 보존된 사람 판단 계보에 속한다. v4.0 또는 v5.0 실행 체인에 넣지 않는다.
- AI 참조표준 지표는 `sensitivity_vs_ai_reference`, `specificity_vs_ai_reference`,
  `agreement_vs_ai_reference`, `ai_reference_standard`, `ai_cross_checked`처럼 출처를 이름에
  포함한다. 출처 없는 ‘민감도’라고 쓰지 않는다.
- `independent_blinding`은 사람 맹검을 뜻하며 false다. AI 맹검은
  `independent_blinding_ai`로 기록하고 계층별로 해석한다. v4.0 문헌 선별은 true이고 근거는
  `research_v3/otc/validation/ai_independent_evaluation.json`이다. v5.0 semantic adjudication
  selection은 실행 영수증이 없어 false다. `V50-PC-001`과
  `research_v3/logs/DECISIONS_v50.md`가 이를 정정했다.
- v4.0 선별 기록은 5,724/5,724행, 커버리지 1.0, 사람 판정 0건이다. 성능 수치는 평가자가
  AI 참조표준이라는 사실과 함께 쓴다.
- `release_ready=false`다. 사이트 배포는 임상 배포 승인이 아니다. 사이트는 연구자의 지시로
  2026-07-30 production에 배포했다. `AM-OTC-004`가 이전의 일괄 배포 금지 문구를 이 원칙으로
  바꿨다. 이후 배포도 연구자가 명시적으로 요청할 때만 한다.
- `tools/search_pipeline/embase_adapter.py`를 삭제하지 않는다.
- 신신파스아렉스의 출처 기록은 보존하되 분석과 런타임에서는 제외한다.
- released 규칙은 source와 locator를 모두 가져야 한다. 복용 조건 32개와 released 규칙
  15개는 서로 다른 상태다.
- Python 체계적 검색 파이프라인은 Next.js 런타임과 분리한다. 코드는
  `tools/search_pipeline/`, 보존 산출물은 `data/systematic_search/`에 있다.
- `data/knowledge_pack.json`과 이전 영양성분 검색 결과는 대체된 탐색 자료로만 취급한다.

## 로컬 v5.1 안전 확장 경계

- 기준선은 commit `6dbdad518e2fa7b2ed7b9a8048e0c47dba5b6ae9`이다. `research_v3/`와
  저장소 밖 v5.0 논문 정본을 수정하지 않는다.
- v5.1 연구 산출물은 `research_v51/`에 둔다. v5.1 문헌 분류나 새 문헌 산출물도
  `research_v51/literature/`에 둔다. 이것이 위 v5.0 문헌 경로 규칙의 명시적 예외다.
- 현재 `verified_primary` 15건은 v5.0의 `human_expert_verified`, `supports_release=true`,
  released 규칙과 약사 검토 메타데이터를 모두 상속한 운영 근거다.
- 나머지 후보 연결 345건은 모두 비활성이다. 구성은 `needs_expert_review` 33건,
  `provisional` 308건, 제외 제품의 `rejected` 4건이다. 일반적인 근거 라벨
  `verified_primary`만으로 미래 후보를 승인하거나 활성화하지 않는다.
- 새 후보를 활성화하려면 사람의 명시적 승인, 안정적인 rule ID, 허가 source·version·locator,
  적용 범위, 사용자 문구와 정상·경계·비대상·오탐 방지 테스트가 모두 필요하다.
- released 규칙 15개와 `ADMIN-*` 허가 복용 조건 32개를 다른 ID와 판정 근거로 유지한다.
  과거 `supportedRuleTypes` 26건을 released 규칙 연결 수로 해석하지 않는다.
- v5.1 문헌 분류는 정확한 직접 일치 1건, 범위 한정 직접 문헌 4건, 배경 문헌 5건이다.
  v5.0에서 거절한 10건은 결과 UI에서 제외한다. 어떤 문헌도 규칙 release 권한이 없다.
- v5.1에서 새로 활성화한 규칙이나 후보는 없다. `release_ready=false`를 유지한다.
- v5.1은 로컬 브랜치와 로컬 커밋까지만 허용한다. 연구자가 명시적으로 승인하기 전에는
  push, PR, production 배포, 공개 게시 또는 G 드라이브 정본 교체를 하지 않는다.

## 검증

사이트를 바꾼 뒤 `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`를 실행한다.
v5.1 경계와 산출물 검증 순서는 `REPRODUCE.md`를 따른다. 배포는 연구자가 명시적으로 요청할
때만 한다.

# Project map

## 사용자 화면

- `app/page.tsx`: 제품명 중심 조회 화면
- `app/sources/page.tsx`: 허가원문 출처 브라우저
- `app/rules/[id]/page.tsx`: 규칙 상세
- `src/components/otc-product-safety-client.tsx`: 제품 선택, 입력 폼, 판정 카드
- `src/components/rule-card.tsx`: 위험 신호와 근거 카드
- `src/lib/site.ts`: 사이트명과 설명

## 결정 엔진

- `src/lib/otc/engine.ts`: 허가원문 기반 OTC 판정 규칙
- `src/lib/otc/presentation.ts`: 판정 근거와 참고 문헌의 표시 분리
- `src/lib/safety-engine/index.ts`: 이전 계보 결정 규칙
- `src/lib/knowledge/`: 런타임 지식 인덱스 로더와 정규화
- `src/types/knowledge.ts`: Zod 스키마와 핵심 타입

## 연구 데이터

- `research_v3/otc/normalized/`: 제품 13개, 성분 28개, 계산 연결 47개, 복용 조건 32개
- `research_v3/otc/rules/rules.csv`: 전체 규칙 16개, released 15개
- `research_v3/otc/rules/supporting_literature.csv`: 규칙×논문 링크 20건(문장 단위 locator 필수)
- `research_v3/otc/rules/literature_link_manifest.json`: 규칙별 연결 현황과 충돌 4건
- `research_v3/otc/literature/picos/`: AI 자율 PICOS 질문 5개
- `research_v3/otc/literature/searches/`: PubMed 원시 XML, 메타데이터와 SHA-256
- `research_v3/otc/literature/evidence_map.csv`: 고유 PMID 5,724개 코퍼스
- `research_v3/otc/literature/screening/`: 배치 115개와 판정 체크포인트, 커버리지 1.0
- `research_v3/measurement/ai_reference/`: 층화 표본 300건과 라운드별 판정
- `research_v3/otc/validation/ai_independent_cases/`: 무라벨 사례
- `research_v3/otc/validation/ai_independent_evaluation/`: 라운드 카드, 잠금 라벨, 예측 감사

## 보존 계보

- `data/knowledge_pack.json`: 이전 영양성분 탐색 자료. 활성 OTC 성과에 합산하지 않음
- `data/systematic_search/`: 이전 검색 파이프라인 산출물
- `research_v3/otc/rules/supporting_literature_pre_v40.csv`: v4.0 검색 밖에서 큐레이션된 문헌
- `src/generated/knowledge-index.json`: 현재 Next.js 런타임 인덱스

## 실행 스크립트

- `tools/v40_literature_pipeline.py`: PICOS 생성, ESearch, EFetch와 코퍼스 정규화
- `tools/agent_screening.py`: 선별 배치 생성·카드 렌더링·적재·커버리지 검증
- `tools/ai_reference_standard.py`: P3-A 층화 표본, 라운드 카드, 가중 지표
- `tools/ai_independent_cases.py`: P3-B 무라벨 사례 생성
- `tools/ai_independent_eval.py`: P3-B 카드 렌더링, 라벨 잠금, 지표 산출
- `scripts/research/otc/predict-ai-independent.ts`: 잠금 검증 후 엔진 예측 기록
- `tools/build_rule_literature_links.py`: 문헌 링크 검증과 매니페스트
- `tools/build_v40_reporting.py`: 논문·문서·지표 재생성
- `tools/build_v40_run_report.py`: 실행 보고서 생성
- `tools/search_pipeline/`: 보존된 Python 검색 파이프라인

## 검증

```powershell
.\.venv-research\Scripts\python.exe -m pytest tests\research -q
npm run typecheck
npm run lint
npm test
npm run build
```

최근 실행: 연구 시험 192개, 앱 시험 73개 통과, 정적 경로 156개.

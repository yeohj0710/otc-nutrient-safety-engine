# Project map

## 사용자 화면

- `app/page.tsx`: 제품명 중심 조회 화면
- `app/sources/page.tsx`: 허가원문 출처 브라우저
- `app/rules/[id]/page.tsx`: 규칙 상세
- `src/components/rule-explorer-client.tsx`: 제품 선택과 입력 폼
- `src/components/rule-card.tsx`: 위험 신호와 근거 카드
- `src/lib/site.ts`: 사이트명과 설명

## 결정 엔진

- `src/lib/safety-engine/index.ts`: 허가원문 기반 결정 규칙
- `src/lib/knowledge/index.ts`: 런타임 지식 인덱스 로더
- `src/lib/knowledge/normalize.ts`: 연구 데이터를 런타임 구조로 변환
- `src/types/knowledge.ts`: Zod 스키마와 핵심 타입

## 연구 데이터

- `research_v3/otc/normalized/`: 제품 13개, 성분 28개, 계산 연결 47개
- `research_v3/otc/rules/`: 전체 규칙 16개, released 15개
- `research_v3/otc/literature/picos/`: AI 자율 PICOS 질문
- `research_v3/otc/literature/searches/`: PubMed 원시 XML, 메타데이터와 SHA-256
- `research_v3/otc/literature/evidence_map.csv`: 고유 PMID 5,724개 코퍼스
- `research_v3/otc/literature/screening/`: 로컬 AI 선별 체크포인트와 부분 매니페스트

## 보존 계보와 런타임 산출물

- `data/knowledge_pack.json`: 이전 영양성분 탐색 자료. 활성 OTC 성과에 합산하지 않음
- `data/systematic_search/`: 이전 검색 파이프라인 산출물
- `src/generated/knowledge-index.json`: 현재 Next.js 런타임 인덱스

## 실행 스크립트

- `tools/v40_literature_pipeline.py`: PICOS 생성, ESearch, EFetch와 코퍼스 정규화
- `tools/screen_v40_literature_local.py`: 로컬 Qwen 선별과 append-only 체크포인트
- `tools/build_v40_reporting.py`: 논문·문서·지표 재생성
- `tools/search_pipeline/`: 보존된 Python 검색 파이프라인

## 검증

```powershell
.\.venv-research\Scripts\python.exe -m pytest tests\research -q
npm run typecheck
npm run lint
npm test
npm run build
```

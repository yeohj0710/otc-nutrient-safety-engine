# Project Map

권혁찬 연구용 repo 진입 지도입니다.

## 앱

- `app/page.tsx`: 메인 조회 화면
- `app/sources/page.tsx`: 출처 브라우저
- `app/rules/[id]/page.tsx`: 규칙 상세
- `src/lib/site.ts`: 사이트명과 설명
- `src/components/rule-explorer-client.tsx`: 입력 폼, 예시, 결과 필터

## 엔진

- `src/lib/safety-engine/index.ts`: 결정적 규칙 엔진
- `src/lib/knowledge/index.ts`: knowledge index loader
- `src/lib/knowledge/normalize.ts`: 원본 데이터를 runtime index로 정규화
- `src/types/knowledge.ts`: Zod schema와 핵심 타입

## 데이터

- `data/knowledge_pack.json`: 기존 탐색 근거 pack. 권혁찬 연구에서는 scoping data로만 사용
- `data/systematic_search/search_runs.csv`: 새 PubMed 검색 로그
- `data/systematic_search/retrieved_records.csv`: 후보 문헌 목록
- `data/systematic_search/screening_log.csv`: title/abstract screening 결과
- `data/systematic_search/evidence_extraction.csv`: 근거 추출 표

## 검색 pipeline

- `tools/search_pipeline/cli.py`: 검색 CLI
- `tools/search_pipeline/pubmed_adapter.py`: PubMed API 호출
- `tools/search_pipeline/storage.py`: CSV 저장
- `tools/search_pipeline/dedup.py`: 중복 표시

## 연구 문서

- `docs/research_plan_260601.md`
- `docs/search_strategy_260601.md`
- `docs/lab_briefing_260601.md`
- `docs/systematic_review_learning_notes.md`
- `docs/pico_automation_review.md`

## 작업 후 확인

```bash
npm run prepare:knowledge
npm run typecheck
npm run test
npm run build
```

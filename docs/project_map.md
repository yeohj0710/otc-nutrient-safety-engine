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
- `src/lib/otc/schema.ts`: v5.1 런타임 데이터 계약
- `src/lib/otc/presentation.ts`: 판정 근거와 참고 문헌의 표시 분리
- `src/generated/otc-runtime.json`: 제품, released 규칙, `ADMIN-*` 복용 조건 런타임
- `src/generated/otc-supporting-literature.json`: v5.1 표시 정책을 적용한 참고 문헌
- `src/lib/safety-engine/index.ts`: 이전 계보 결정 규칙
- `src/lib/knowledge/`: 이전 런타임 지식 인덱스 로더와 정규화
- `src/types/knowledge.ts`: 이전 지식 인덱스의 Zod 스키마와 핵심 타입

## v5.0 제출 정본 — 읽기 전용

- `research_v3/otc/normalized/`: 제품 16행(분석 13), 성분 31행(계산 28), 제품–성분
  106행(계산 선택 47), 복용 조건 32행
- `research_v3/otc/rules/rules.csv`: 전체 규칙 16개, released 15개
- `research_v3/otc/literature/v5/`: v5.0 MECIR 검색, 분류기 선별, semantic adjudication과 최종 결정
- `research_v3/otc/validation/screening_ai_reference_v50/`: 43,207건 모집단의 완전분할 층화
  설계, 실제 맹검·채점 표본 894행, 잠금 라벨과 영수증
- `research_v3/otc/synthesis/screener_vs_ai_reference_v50.json`: v5.0 채점 arm의 설계가중 비교 결과
- `research_v3/logs/v50_run_report.json`: v5.0 최종 수치와 해시의 단일 원장
- `research_v3/logs/v50_*`: v5.0 실행 원장, 판단 기록과 채점 결과

## 보존된 v4.0 비교 자료

- `research_v3/otc/rules/supporting_literature.csv`: 규칙×논문 링크 20건(문장 단위 locator 필수)
- `research_v3/otc/rules/literature_link_manifest.json`: 규칙별 연결 현황과 충돌 4건
- `research_v3/otc/literature/picos/`: AI 자율 PICOS 질문 5개
- `research_v3/otc/literature/searches/`: PubMed 원시 XML, 메타데이터와 SHA-256
- `research_v3/otc/literature/evidence_map.csv`: 고유 PMID 5,724개 코퍼스
- `research_v3/otc/literature/screening/`: 배치 115개와 판정 체크포인트, 커버리지 1.0
- `research_v3/measurement/ai_reference/`: 층화 표본 300건과 라운드별 판정
- `research_v3/otc/validation/ai_independent_cases/`: 무라벨 사례
- `research_v3/otc/validation/ai_independent_evaluation/`: 라운드 카드, 잠금 라벨, 예측 감사

## 로컬 v5.1 안전 확장

- `research_v51/protocol/README.md`: v5.0 보호 경계, 후보 상태, 문헌 권한과 로컬 작업 범위
- `research_v51/evidence/evidence_units.csv`: 중복을 정리한 허가 근거 단위 328건
- `research_v51/evidence/evidence_rule_links.csv`: 상태, 공식 원문 위치·문맥과 문서 개정
  메타데이터를 가진 후보–규칙 연결 360건
- `research_v51/evidence/active_rule_applicability.csv`: 기존 released 규칙 15개의 제한된 적용 범위
- `research_v51/review/expert_review_queue.csv`: 비활성 전문가 검토 후보 33건
- `research_v51/review/expert_review_packet.md`: 제품·성분, 문서 개정 정보, 완결 공식 원문,
  채택·수정·거절 판단과 구체적 필수 회귀 테스트 검토지
- `research_v51/literature/link_classification.csv`: 직접 1건, 범위 한정 직접 4건, 배경 5건과 UI 제외 10건
- `research_v51/audit/baseline_manifest.json`: v5.0 기준선과 보호 대상 해시
- `research_v51/audit/source_freshness_snapshot.json`: 식약처 원격 문서 20개의 의미 동일성 감사
- `research_v51/audit/product_support_matrix.csv`: 제품 9개 용량 전용, 1개 용량·간격 전용,
  3개 제한적 확장 안전 지원
- `research_v51/audit/active_rule_matrix.csv`: released 규칙별 적용 범위와 출처 버전
- `research_v51/audit/final_metrics.json`: v5.0 기준선과 로컬 v5.1의 기계 집계
- `research_v51/audit/CODE_REVIEW.md`: 독립 결함 검토, 수정 범위와 재검토 결과
- `research_v51/audit/BROWSER_QA.md`: 깨끗한 production build의 데스크톱·모바일 QA
- `research_v51/audit/CHECKPOINT.md`: 최종 수치, 해시, 검증 환경과 공개 전 남은 결정
- `research_v51/reports/FINAL_REPORT.md`: 기준선, 근거, 보류, 지원 범위, 문헌, 테스트와 커밋의 최종 보고

## 보존 계보

- `data/knowledge_pack.json`: 이전 영양성분 탐색 자료. 활성 OTC 성과에 합산하지 않음
- `data/systematic_search/`: 이전 검색 파이프라인 산출물
- `research_v3/otc/rules/supporting_literature_pre_v40.csv`: v4.0 검색 밖에서 큐레이션된 문헌
- `src/generated/knowledge-index.json`: 이전 Next.js 런타임 인덱스

## 실행 스크립트

- `tools/v40_literature_pipeline.py`: v4.0 PICOS 생성, ESearch, EFetch와 코퍼스 정규화
- `tools/agent_screening.py`: v4.0 선별 배치 생성·카드 렌더링·적재·커버리지 검증
- `tools/ai_reference_standard.py`: v4.0 P3-A 층화 표본, 라운드 카드, 가중 지표
- `tools/ai_independent_cases.py`: v4.0 P3-B 무라벨 사례 생성
- `tools/ai_independent_eval.py`: v4.0 P3-B 카드 렌더링, 라벨 잠금, 지표 산출
- `scripts/research/otc/predict-ai-independent.ts`: v4.0 잠금 검증 후 엔진 예측 기록
- `tools/build_rule_literature_links.py`: v4.0 문헌 링크 검증과 매니페스트 생성
- `tools/build_v40_run_report.py`: v4.0 실행 보고서 생성
- `tools/v50_scoring/`: v5.0 완전분할 층화 표본, 채점 하네스, 잠금 후 비교 보고
- `scripts/research/otc/build_v51_evidence_review.py`: v5.1 근거 단위, 후보 상태와 검토 큐 생성
- `scripts/research/otc/validate_v51_shortlist_triage.py`: 33건 의미 분류 계약 검증
- `scripts/research/otc/build_v51_review_packet.py`: 전문가 검토지와 감사 파일 생성
- `scripts/research/otc/build_runtime.py`: 제품, released 규칙과 `ADMIN-*` 복용 조건 런타임 생성
- `scripts/research/otc/build_v51_literature_classification.py`: v5.0 링크 20건의 v5.1 표시 정책 생성
- `scripts/research/otc/build_supporting_literature.py`: 표시 정책을 검증해 참고 문헌 런타임 생성
- `scripts/research/otc/audit_v51_boundaries.py`: `research_v3/`와 외부 논문 정본 보호 감사
- `scripts/research/otc/audit_v51_source_freshness.py`: 식약처 원격 문서 의미 동일성 감사
- `scripts/research/otc/build_v51_final_audit.py`: 제품·규칙·근거·문헌 상태의 기계 집계
- `tools/build_v40_reporting.py`: 보존된 v4.0 논문·문서·지표 생성기
- `tools/search_pipeline/`: 보존된 Python 검색 파이프라인

## 검증

버전별 순서와 네트워크 조건은 `REPRODUCE.md`를 따른다.

```powershell
.\.venv-research\Scripts\python.exe -m pytest -q
npm run typecheck
npm run lint
npm test
npm run build
```

보존된 v4.0 run report의 최근 실행은 연구 시험 192개, 앱 시험 73개, 정적 경로 156개다.
이 숫자는 현재 v5.1 검증 건수가 아니며 v5.0 기준선 감사값도 아니다.

Reference basis: tossfeed-easy-finance

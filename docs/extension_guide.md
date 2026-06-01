# Extension Guide

작업 시작 전에 전체 파일 위치는 `docs/project_map.md`를 먼저 참고하면 빠릅니다.

관련 파일:
- 기본 원본: `data/knowledge_pack.json`
- 레거시 분리 원본: `data/source_registry.json`, `data/evidence_chunks.json`, `data/ingredients.json`, `data/safety_rules.json`
- 정규화: `src/lib/knowledge/normalize.ts`
- 엔진: `src/lib/safety-engine/index.ts`
- 타입: `src/types/knowledge.ts`

데이터 로딩 원칙:
- `knowledge_pack.json`이 있으면 그 파일만 읽습니다.
- `knowledge_pack.json`이 깨져 있으면 fallback 하지 않고 실패합니다.
- 분리 JSON은 `knowledge_pack.json`이 없을 때만 레거시 호환용으로 사용합니다.

## 1) 새 규칙을 추가할 때 최소 체크리스트
- source가 먼저 등록되었는가?
- 근거 위치(locator)가 명확한 chunk가 있는가?
- ingredient alias가 충분한가?
- threshold_scope가 명확한가?
  - all_sources
  - supplements_only
  - fortified_foods_only
  - preformed_only
  - EPA_DHA_combined
- hard-stop인지 monitor인지 severity가 과도하지 않은가?
- review_status를 starter_validated / starter_hypothesis 중 무엇으로 둘지 정했는가?

## 2) 권장 evidence hierarchy
1. 한국 규정/섭취기준
2. 정부 fact sheet / guideline
3. EFSA scientific opinion / UL summary
4. systematic review / meta-analysis
5. RCT
6. case series / case report
7. post-marketing signal
8. licensed clinical database

## 3) 관할권 충돌 처리
예시:
- 미국 UL과 EFSA UL이 다를 수 있음
- supplement-only UL과 all-source UL이 다를 수 있음

권장 정책:
- 저장은 병렬로 다 한다
- 런타임에서 `jurisdiction_preference` 와 `strictest_mode_for_conflicts`로 선택한다
- 단, scope가 다른 기준은 서로 직접 비교하지 않는다

## 4) 문헌 청크 작성 팁
좋은 chunk:
- locator가 명확함
- 한국어 요약이 짧고 명확함
- structured_claim으로 숫자/조건이 구조화됨

나쁜 chunk:
- “안전 관련 부분 전반”
- locator 없음
- 여러 주장 섞임
- 엔진이 바로 못 쓰는 서술만 있음

## 5) DB 확장 추천
추가 테이블:
- disease_catalog
- medication_catalog
- lab_threshold_rules
- product_catalog
- product_ingredient_map
- post_marketing_signals
- curation_log
- rule_change_history

## 6) 운영 시 필요한 감사 로그
엔진이 실제 서비스에 들어가면 아래 로그를 남기는 것이 좋음
- evaluation_id
- user snapshot hash
- candidate stack snapshot
- matched_rule_ids
- suppressed_rule_ids
- final decision
- manual override 여부
- human reviewer
- reference bundle snapshot

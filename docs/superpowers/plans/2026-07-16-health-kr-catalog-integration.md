# 약학정보원 OTC 카탈로그 통합 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `C:\dev\pharmacy-product-catalog`의 776개 판매 SKU와 약학정보원 연결 필드를 OTC 연구의 검색·분류·후보 선별·데이터 품질 평가에 재현 가능하게 연결한다.

**Architecture:** 외부 JSON·CSV·공개 동기화본을 각각 바이트로 한 번 읽고 동일 스냅샷에서 파싱과 SHA-256을 계산한다. `official_match_status=confirmed`이며 안정적인 공식 식별자와 필수 연구 필드가 있는 일반의약품만 연구용 검색·분류 입력으로 사용하고, 전체 원문·가격은 OTC 저장소에 복사하지 않는다. 약학정보원 연결은 식약처 허가 검증을 대체하지 않으므로 기존 13개 안전성 런타임과 released 규칙, 독립평가 지표는 변경하지 않는다.

**Tech Stack:** Python 3.12 표준 라이브러리, pytest, 기존 Next.js 16/TypeScript 회귀 검증

---

## 파일 구조

- Create: `scripts/research/otc/health_kr_catalog.py` — 스키마 검증, 식별자 정규화, 연구 사용 가능 여부, 분류, 동일성분·제형 그룹, 결정론적 검색·안전 제외
- Create: `scripts/research/otc/import_health_kr_catalog.py` — 외부 스냅샷을 한 번 읽고 최소 파생 CSV와 요약·감사 JSON 생성
- Create: `tests/research/test_health_kr_catalog.py` — 단위 테스트와 실제 생성 산출물 회귀 테스트
- Create: `research_v3/otc/selection/catalog_health_kr_status_index.csv` — 776개 source ID의 상태·공식 식별자·사용 경계만 보존
- Create: `research_v3/otc/selection/catalog_health_kr_research_candidates.csv` — confirmed 연구 후보의 최소 식별·분류·그룹 필드
- Create: `research_v3/otc/selection/catalog_health_kr_same_ingredient_groups.csv` — 안정적인 성분 코드와 제형 그룹 집계
- Create: `research_v3/otc/selection/catalog_health_kr_conflict_review.csv` — 원문 매칭 충돌의 source ID·이유를 최소 필드로 보존
- Create: `research_v3/otc/selection/catalog_health_kr_summary.json` — 실제 건수, 결측률, 충돌, provenance
- Create: `research_v3/otc/audit/catalog_health_kr_integration.json` — import·격리·가격 비관여·red flag 검증 결과
- Modify: `scripts/research/otc/build_metrics.py` — 약학정보원 수치를 별도 catalog 계층으로만 연결
- Modify: `tests/research/test_otc_metrics.py` — 기존 OTC 지표 불변과 catalog 계층 수치 연결 확인
- Modify: `research_v3/REPRODUCE.md` — 재현 명령과 공개 제한 추가
- Modify: `research_v3/DECISIONS.md` — 약학정보원과 식약처 근거의 역할 분리 기록
- Modify: `research_v3/HUMAN_ACTION_REQUIRED.md` — review_required와 런타임 승격 조건 갱신

### Task 1: 스냅샷 스키마와 식별자 경계

- [ ] **Step 1: 실패 테스트 작성**

`tests/research/test_health_kr_catalog.py`에 다음 조건을 작성한다.

```python
def test_confirmed_requires_stable_official_identity():
    row = fixture_row(official_match_status="confirmed", official_product_key="")
    with pytest.raises(ValueError, match="confirmed_missing_stable_identity"):
        validate_records([row])

def test_unconfirmed_rows_never_become_research_candidates():
    for status in ("review_required", "not_found", "not_applicable"):
        row = fixture_row(official_match_status=status)
        assert research_use_status(row) == "excluded_unconfirmed"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research/test_health_kr_catalog.py -q`

Expected: `ModuleNotFoundError: scripts.research.otc.health_kr_catalog`

- [ ] **Step 3: 최소 구현**

`health_kr_catalog.py`에 다음 공개 인터페이스를 구현한다.

```python
ALLOWED_MATCH_STATUSES = {"confirmed", "review_required", "not_found", "not_applicable"}

def validate_records(records: list[dict]) -> dict: ...
def stable_official_key(record: dict) -> str: ...
def research_use_status(record: dict) -> str: ...
```

confirmed 행은 `official_product_key`, `official_item_seq`, `official_source_url`, `official_source_type`, `official_section_evidence`를 필수로 검증한다. 이름 유사도는 식별자로 사용하지 않는다.

- [ ] **Step 4: 단위 테스트 통과 확인**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research/test_health_kr_catalog.py -q`

Expected: PASS

### Task 2: 분류와 동일성분·제형 그룹

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_group_uses_ingredient_codes_and_dosage_form():
    first = fixture_row(ingredient_codes=["I001", "I002"], official_dosage_form="정제")
    second = fixture_row(ingredient_codes=["I002", "I001"], official_dosage_form="정제")
    third = fixture_row(ingredient_codes=["I001", "I002"], official_dosage_form="시럽")
    assert ingredient_form_group_id(first) == ingredient_form_group_id(second)
    assert ingredient_form_group_id(first) != ingredient_form_group_id(third)

def test_classification_uses_official_fields():
    row = fixture_row(official_category="해열, 진통, 소염제")
    assert classify_product(row) == "analgesic_antiinflammatory"
```

- [ ] **Step 2: 그룹과 분류 구현**

```python
def ingredient_codes(record: dict) -> tuple[str, ...]: ...
def ingredient_form_group_id(record: dict) -> str: ...
def classify_product(record: dict) -> str: ...
```

성분 그룹은 `official_additional_data.health_kr_raw.ingredient_details[].ingredient_code`의 정렬된 집합과 정규화 제형으로 SHA-256 ID를 만든다. 성분명 문자열과 가격은 그룹 키에 넣지 않는다.

- [ ] **Step 3: 테스트 통과 확인**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research/test_health_kr_catalog.py -q`

Expected: PASS

### Task 3: 결정론적 연구 검색과 안전 제외

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_red_flag_returns_no_candidates_and_referral(): ...
def test_pregnancy_and_age_dur_exclude_candidates(): ...
def test_contraindication_and_interaction_terms_exclude_candidates(): ...
def test_price_never_changes_clinical_ranking(): ...
```

- [ ] **Step 2: 검색 구현**

```python
@dataclass(frozen=True)
class SafetyProfile:
    age_years: float | None = None
    pregnant: bool = False
    lactating: bool = False
    conditions: tuple[str, ...] = ()
    medications: tuple[str, ...] = ()
    red_flags: tuple[str, ...] = ()

def search_research_candidates(records: list[dict], query: str, profile: SafetyProfile) -> dict: ...
```

검색 점수는 제품명, 성분, 효능·효과, 공식 분류, 제형만 사용한다. 임신 DUR, 소아·고령 DUR, 금기, 상호작용이 입력 조건과 일치하면 후보에서 제외한다. red flag가 하나라도 있으면 후보는 0건이며 disposition은 `refer_to_pharmacist_or_clinician`이다. 가격은 결과 표시용 원본 변수로만 읽고 점수·필터·동점 해소에 사용하지 않는다.

- [ ] **Step 3: 테스트 통과 확인**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research/test_health_kr_catalog.py -q`

Expected: PASS

### Task 4: 재현 가능한 import와 최소 파생 산출물

- [ ] **Step 1: importer 테스트 작성**

임시 JSON·CSV·공개 동기화본을 만들고 세 파일의 행 순서·source ID·상태가 일치하지 않으면 import가 실패하는지 확인한다. 출력 CSV에 `price`, `displayed_price_krw`, 효능·용법·주의사항 원문이 없는지 확인한다.

- [ ] **Step 2: importer 구현**

`import_health_kr_catalog.py`는 각 파일을 바이트로 한 번만 읽는다. 같은 바이트로 파싱과 SHA-256을 처리하고 다음 함수를 제공한다.

```python
def build_import(queue_path: Path, csv_path: Path, public_path: Path) -> dict: ...
def write_import(result: dict, selection_output: Path, audit_output: Path) -> None: ...
```

요약에는 total/imported/status별 건수, 연구 검색 사용 가능, 안전성 런타임 승격 가능, 고유 공식 품목, 중복 공식 품목 링크, 매핑 실패, 충돌, 주요 필드 결측률을 기록한다.

- [ ] **Step 3: 실제 776건 import 실행**

Run:

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/import_health_kr_catalog.py --catalog-root C:\dev\pharmacy-product-catalog
```

Expected: source total과 네 상태의 합이 같고, public JSON 해시가 data JSON 해시와 같으며, `runtime_promotion_allowed=0`이다.

### Task 5: 기존 후보·metrics·문서 연결

- [ ] **Step 1: metrics 실패 테스트 작성**

`test_otc_metrics.py`에서 catalog 통합 수치가 별도 키로 존재하고 기존 `products_total=16`, `analysis_products=13`, `runtime_products=13`, `rules_released=15`, `release_ready=false`가 유지되는지 확인한다.

- [ ] **Step 2: build_metrics 연결**

`catalog_health_kr_summary.json`을 읽어 `catalog_health_kr_*` 메트릭을 추가한다. 기존 OTC 제품·성분·규칙·성능 분모에는 합산하지 않는다.

- [ ] **Step 3: 재현·결정·사람 작업 문서 갱신**

약학정보원 confirmed의 용도, MFDS 승격 금지, 가격 비관여, review_required 수동 검토, 공개·재사용 제한을 명시한다.

- [ ] **Step 4: metrics 재생성**

Run: `.venv-research\Scripts\python.exe scripts/research/otc/build_metrics.py`

Expected: `release_ready=false`와 독립평가 경계가 유지된다.

### Task 6: 전체 검증

- [ ] **Step 1: 연구 테스트**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research -q`

Expected: 모든 테스트 PASS

- [ ] **Step 2: 앱 테스트·정적 검사·빌드**

Run:

```powershell
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

Expected: 모든 명령 exit code 0

- [ ] **Step 3: 최종 불변식 확인**

- 외부 원본 파일이 변경되지 않았다.
- 전체 원문과 가격 필드가 OTC 저장소 산출물에 복사되지 않았다.
- review_required, not_found, not_applicable은 연구 후보로 사용되지 않았다.
- 약학정보원 confirmed 자료가 기존 MFDS 검증 제품 수, released 규칙 수와 성능 지표를 늘리지 않았다.
- `complete=false`, `release_ready=false`, `independent_blinding=false`, `performance_claim_allowed=false`가 유지된다.
- 사용자 요청에 따라 커밋·푸시·배포를 수행하지 않는다.

# Private Catalog Candidate Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the private 776-SKU pharmacy catalog to the OTC research as a non-authoritative candidate population without copying prices or promoting unverified products.

**Architecture:** A standalone Python bridge reads the external catalog in place, validates its schema and duplicate invariants, applies configuration-driven screening, and compares normalized names with the existing 13-product analysis set. It writes only aggregate audits and minimal candidate rows under `research_v3/otc/selection`; the product master, runtime, rules, metrics, and completion state remain unchanged.

**Tech Stack:** Python 3.11+, CSV/JSON, `difflib.SequenceMatcher`, pytest.

---

### Task 1: Lock privacy and matching contracts with tests

**Files:**
- Create: `tests/research/test_catalog_candidate_bridge.py`

- [ ] **Step 1: Write fixture-based tests**

```python
def test_bridge_never_exports_price_fields(tmp_path):
    result = build_bridge(catalog_path, queue_path, product_master_path, policy_path)
    assert "price" not in json.dumps(result, ensure_ascii=False).lower()

def test_exact_alias_and_fuzzy_rows_are_review_candidates(tmp_path):
    result = build_bridge(catalog_path, queue_path, product_master_path, policy_path)
    assert {row["match_method"] for row in result.intersections} == {
        "exact_normalized_alias",
        "fuzzy_normalized_alias",
    }
    assert all(row["promotion_allowed"] == "false" for row in result.intersections)
```

- [ ] **Step 2: Run the focused test and confirm it fails before implementation**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research/test_catalog_candidate_bridge.py -q`

Expected: import failure for `scripts.research.otc.catalog_candidate_bridge`.

### Task 2: Implement a configuration-driven private catalog bridge

**Files:**
- Create: `research_v3/otc/selection/catalog_screening_policy.json`
- Create: `scripts/research/otc/catalog_candidate_bridge.py`

- [ ] **Step 1: Define screening-only classifications**

```json
{
  "possible_otc_categories": ["진통", "호흡기", "소화기", "알레르기"],
  "category_indicates_non_otc": ["비타민", "영양제", "유산균", "코스메틱", "의료기기", "건강보조식품"],
  "candidate_form_tokens": ["정", "캡슐", "시럽", "현탁액", "연고", "크림", "겔", "파프"],
  "fuzzy_match_threshold": 0.9,
  "fuzzy_match_margin": 0.05
}
```

- [ ] **Step 2: Implement source validation, normalization, duplicate audit, matching, and minimal output**

```python
def build_bridge(catalog_path: Path, queue_path: Path, product_master_path: Path, policy_path: Path) -> BridgeResult:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    required = {"id", "name", "capacity", "category", "verification_status"}
    if any(not required <= row.keys() for row in catalog):
        raise ValueError("catalog_schema_invalid")
    # Prices are never copied into BridgeResult or generated files.
    return classify_and_match(catalog, queue_path, product_master_path, policy_path)
```

- [ ] **Step 3: Run the focused tests**

Run: `.venv-research\Scripts\python.exe -m pytest tests/research/test_catalog_candidate_bridge.py -q`

Expected: all focused tests pass.

### Task 3: Generate candidate-only artifacts and prove research-state isolation

**Files:**
- Create: `research_v3/otc/selection/catalog_existing_product_intersection.csv`
- Create: `research_v3/otc/selection/catalog_additional_otc_candidates.csv`
- Create: `research_v3/otc/selection/catalog_candidate_summary.json`
- Create: `research_v3/otc/audit/catalog_candidate_bridge.json`

- [ ] **Step 1: Run the bridge against the external catalog without copying its source files**

Run:

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/catalog_candidate_bridge.py `
  --catalog-root C:\dev\pharmacy-product-catalog
```

Expected: 776 source rows validated, 22 duplicate groups and 46 grouped SKUs confirmed, and candidate artifacts generated without price fields.

- [ ] **Step 2: Re-run runtime alignment and completion audits**

Run:

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/audit_runtime_alignment.py
.venv-research\Scripts\python.exe scripts/research/otc/audit_completion.py
```

Expected: runtime remains 13 products and completion remains false only for `independent_evaluation_complete`.

### Task 4: Document provenance, rights boundary, and reproduction

**Files:**
- Modify: `research_v3/otc/data_dictionary.md`
- Modify: `research_v3/REPRODUCE.md`
- Modify: `research_v3/DECISIONS.md`
- Modify: `research_v3/HUMAN_ACTION_REQUIRED.md`

- [ ] **Step 1: Document that the catalog is a private candidate population**

Record the source snapshot hashes, the lack of `DATA_GO_KR_SERVICE_KEY`, the absence of official matches, the prohibition on price use, and the requirement that only MFDS-confirmed items can enter the product master or runtime.

- [ ] **Step 2: Run focused and full research tests**

Run:

```powershell
.venv-research\Scripts\python.exe -m pytest tests/research/test_catalog_candidate_bridge.py -q
.venv-research\Scripts\python.exe -m pytest tests/research -q
```

Expected: all tests pass, while `complete=false`, `release_ready=false`, and `performance_claim_allowed=false` remain unchanged.

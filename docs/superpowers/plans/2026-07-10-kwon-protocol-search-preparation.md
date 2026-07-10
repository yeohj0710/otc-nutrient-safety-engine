# 권혁찬 Protocol and Search Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 권혁찬 K1-K5 연구의 승인 전 프로토콜·적격 기준·검색식·seed 후보를 만들고, PubMed 검색 pipeline이 전량 반입 또는 명시적 실패만 허용하도록 수정한다.

**Architecture:** 프로토콜과 검색식은 `draft_pre_approval` 상태로 보존한다. 검색 adapter는 먼저 전체 hit 수를 확인하고, PubMed ESearch 한계인 10,000건 이하일 때만 전량 UID를 요청한다. 10,000건을 넘으면 일부를 저장하지 않고 `requires_segmentation`으로 실패해 날짜 구간 분할 또는 EDirect 실행을 요구한다.

**Tech Stack:** Python 3.12, pytest, NCBI E-utilities, CSV/JSON, PRISMA 2020, PRISMA-S, Cochrane Handbook 6.5.1

---

### Task 1: 권혁찬 프로토콜 초안과 적격 기준

**Files:**
- Create: `research_v2/protocol/protocol_draft_v0.1.md`
- Create: `research_v2/protocol/eligibility.json`
- Modify: `research_v2/DECISIONS.md`

- [ ] **Step 1: 연구 유형과 질문 작성**

프로토콜에 아래 세 질문을 고정한다.

```text
1. K1-K5에서 성분 형태·일일 함량·기간과 연결된 주요 위해 결과는 무엇인가?
2. AI 보조 선별·추출은 held-out 골드셋에서 사전 성능 기준을 충족하는가?
3. 검증된 원문 근거로 만든 규칙은 독립 시나리오에서 위해를 놓치지 않고 출처를 완전하게 제시하는가?
```

- [ ] **Step 2: K1-K5 적격 기준 JSON 작성**

공통 포함: 성인 사람, 경구 제제, 성분·용량 식별 가능, 안전성 결과 존재. 공통 제외: 동물/세포, 식이만, 효능만, 원문 검증 불가. 각 노드는 `population`, `exposure`, `comparator`, `primary_outcomes`, `secondary_outcomes`, `eligible_designs`를 가진다.

- [ ] **Step 3: 승인 상태 명시**

프로토콜 header:

```yaml
version: 0.1
status: draft_pre_approval
registration_status: not_registered
approval_required: H-001
```

- [ ] **Step 4: 문서 검증**

Run:

```bash
python -m json.tool research_v2/protocol/eligibility.json > NUL
rg -n "여형준|2020194025|A1|A2|R1|R2|R3" research_v2/protocol -g "!reference/**"
```

Expected: JSON exit 0, identity/old-node 검색 0건.

### Task 2: PubMed 검색식과 seed 후보

**Files:**
- Create: `research_v2/search/pubmed_queries/K1.txt`
- Create: `research_v2/search/pubmed_queries/K2.txt`
- Create: `research_v2/search/pubmed_queries/K3.txt`
- Create: `research_v2/search/pubmed_queries/K4.txt`
- Create: `research_v2/search/pubmed_queries/K5.txt`
- Create: `research_v2/search/search_strategies.csv`
- Create: `research_v2/search/seed_candidates.csv`
- Create: `research_v2/search/search_strategy_review.md`
- Create: `research_v2/search/peer_review.csv`

- [ ] **Step 1: PubMed query 파일 작성**

각 식은 MeSH와 `[tiab]` 자유어를 함께 사용하고 성분·경구 제제·안전성 결과를 결합한다. 언어·연도·연구설계 필터는 적용하지 않는다.

- [ ] **Step 2: search strategy CSV 작성**

```csv
strategy_id,node_id,database,platform,version,status,query_file,controlled_vocabulary,proximity_reviewed,seed_set_version,review_status,notes
```

상태는 `draft_pre_peer_review`, review는 `awaiting_H-002`로 기록한다.

- [ ] **Step 3: seed 후보 작성**

```csv
seed_id,node_id,pmid,doi,title,design,reason_for_seed,source_url,eligibility_status,verified_at_utc
```

각 노드 3-5개 후보를 넣되 `eligibility_status=candidate_not_full_text_adjudicated`로 표시한다.

- [ ] **Step 4: reviewer 양식 작성**

```csv
review_id,strategy_id,reviewer_id,review_date_utc,question_number,criterion,rating,comment,required_change,resolution,status
```

### Task 3: 전량 반입 실패-폐쇄 테스트

**Files:**
- Modify: `tools/search_pipeline/pubmed_adapter.py`
- Modify: `tools/search_pipeline/schemas.py`
- Modify: `tools/search_pipeline/cli.py`
- Test: `tests/test_search_pipeline.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_full_retrieval_rejects_pubmed_result_over_10000(tmp_path: Path) -> None:
    adapter = PubMedAdapter(email="test@example.com", output_root=tmp_path)
    adapter._esearch = Mock(return_value={"esearchresult": {"count": "10001", "idlist": []}})
    with pytest.raises(RuntimeError, match="segment the query"):
        adapter.run(target_id="K1", query="vitamin D", max_records=None)


def test_full_retrieval_requests_every_uid_when_under_limit(tmp_path: Path) -> None:
    responses = [
        {"esearchresult": {"count": "3", "idlist": []}},
        {"esearchresult": {"count": "3", "idlist": ["1", "2", "3"]}},
    ]
    adapter = PubMedAdapter(email="test@example.com", output_root=tmp_path)
    adapter._esearch = Mock(side_effect=responses)
    adapter._efetch = Mock(return_value="<PubmedArticleSet />")
    result = adapter.run(target_id="K1", query="vitamin D", max_records=None)
    assert result.search_run.hit_count == 3
    assert result.search_run.exported_count == 3
```

- [ ] **Step 2: 테스트 실패 확인**

Run:

```bash
.venv-research/Scripts/python -m pytest tests/test_search_pipeline.py -v
```

Expected: 새 전량 반입 테스트 실패.

- [ ] **Step 3: SearchRun schema 확장**

`SearchRun`에 `exported_count`, `imported_count`, `raw_file_sha256`, `retrieval_mode`을 추가한다. `max_records`는 legacy 호환용으로 유지하되 새 전량 검색에서는 빈 값이 아니라 실제 hit 수를 기록한다.

- [ ] **Step 4: 두 단계 ESearch 구현**

```python
count_payload = self._esearch(query=query, max_records=0, sort=sort)
hit_count = int(count_payload["esearchresult"]["count"])
if max_records is None and hit_count > 10_000:
    raise RuntimeError("PubMed ESearch cannot return more than 10,000 UIDs; segment the query or use EDirect")
requested = hit_count if max_records is None else min(max_records, hit_count)
payload = self._esearch(query=query, max_records=requested, sort=sort)
```

요청 ID 수, parsed record 수, raw SHA-256가 다르면 status를 `failed_reconciliation`으로 두고 exit nonzero로 처리한다.

- [ ] **Step 5: CLI 기본값 변경**

`--max-records` 기본값을 `None`으로 바꾸고, 양의 값을 주면 `legacy_capped_debug` 모드로만 허용한다. 해당 모드는 Gate 2 검색 로그로 승격할 수 없다.

- [ ] **Step 6: 전체 테스트**

Run:

```bash
.venv-research/Scripts/python -m pytest tests -q
npm run test
npm run typecheck
```

Expected: all pass.

### Task 4: 검색 준비 검증과 관문 상태

**Files:**
- Create: `research_v2/search/preflight_report.json`
- Modify: `research_v2/audit/gate_status.json`
- Modify: `research_v2/HUMAN_ACTION_REQUIRED.md`

- [ ] **Step 1: preflight report 작성**

다음을 기록한다: query 파일 해시, 각 노드 seed 수, 구문 검토 상태, PubMed 10,000 한계 처리, NCBI email 존재 여부, H-001/H-002/H-003 상태.

- [ ] **Step 2: Gate 상태 갱신**

Gate 1은 `awaiting_human_action`, Gate 2는 `preflight_ready_not_executed`로 둔다. 승인·DB 접근 전 hit 수나 검색 완료 상태를 만들지 않는다.

- [ ] **Step 3: 검증**

Run:

```bash
.venv-research/Scripts/python -m pytest tests -q
python execution_package/scripts/check_project_identity.py --root .
git diff --check
```

Expected: all exit 0.

## Self-review

- Spec coverage: K1-K5, protocol draft, seed set, peer-review form, no top-N, 10,000 limit, human approvals covered.
- Placeholder scan: 미정 구현 항목 없음; 사람 판정은 명시된 상태값과 입력 양식으로 분리.
- Type consistency: `node_id`, `strategy_id`, `search_run_id`, `exported_count`, `imported_count`, `raw_file_sha256`를 모든 파일에서 동일 사용.

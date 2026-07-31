# OTC 안전 점검 엔진 v5.1 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v5.0 정본을 보존하면서 공식 허가 근거의 적용 범위를 벗어난 판정을 차단하고, 후보 근거·문헌·제품별 지원 범위를 검증 가능한 v5.1 산출물로 분리한다.

**Architecture:** `research_v3/`는 읽기 전용 기준선으로 유지하고 새 연구 산출물은 `research_v51/`에 기록한다. 런타임은 `ruleType` 전역 허용 대신 `ruleId`와 기계 판독 가능한 적용 조건을 사용한다. 허가원문은 판정을 결정하고 PubMed 문헌은 직접 일치 또는 배경 연구로만 표시한다.

**Tech Stack:** Python 3, TypeScript, React 19, Next.js 16 App Router, Vitest, pytest

---

### Task 1: v5.0 보존 경계와 기준선 고정

**Files:**
- Create: `research_v51/protocol/README.md`
- Create: `research_v51/audit/baseline_manifest.json`
- Create: `scripts/research/otc/audit_v51_boundaries.py`
- Test: `tests/research/test_v51_boundary_audit.py`

- [ ] **Step 1: 보호 경로 변경을 재현하는 실패 테스트 작성**

```python
def test_boundary_audit_rejects_a_changed_protected_file(tmp_path):
    result = audit_boundaries(repo_root=tmp_path)
    assert result["protected_paths_unchanged"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `.\.venv-research\Scripts\python.exe -m pytest tests\research\test_v51_boundary_audit.py -q`
Expected: 보호 감사 함수가 아직 없어 실패

- [ ] **Step 3: 보호 경로·핵심 SHA-256·기준선 수치 감사 구현**

```python
PROTECTED_PREFIXES = (
    "research_v3/otc/normalized/",
    "research_v3/otc/rules/",
    "research_v3/otc/literature/",
    "research_v3/logs/v50_",
    "research_v3/search/provisional_pubmed_20260710/",
)
```

- [ ] **Step 4: 기준선 감사 통과 확인**

Run: `.\.venv-research\Scripts\python.exe -m pytest tests\research\test_v51_boundary_audit.py -q`
Expected: PASS

- [ ] **Step 5: 연구 경계만 별도 커밋**

```powershell
git add research_v51/protocol/README.md research_v51/audit/baseline_manifest.json scripts/research/otc/audit_v51_boundaries.py tests/research/test_v51_boundary_audit.py
git commit -m "research: v5.1 보존 경계와 기준선을 고정한다"
```

### Task 2: 후보 허가 근거 360건과 shortlist 33건 구조화

**Files:**
- Create: `scripts/research/otc/build_v51_evidence_review.py`
- Create: `research_v51/evidence/evidence_units.csv`
- Create: `research_v51/evidence/evidence_rule_links.csv`
- Create: `research_v51/review/expert_review_queue.csv`
- Create: `research_v51/review/shortlist_semantic_triage.csv`
- Create: `research_v51/audit/evidence_inventory.json`
- Test: `tests/research/test_build_v51_evidence_review.py`

- [ ] **Step 1: 행 수와 상태 분할 실패 테스트 작성**

```python
assert len(rule_links) == 360
assert len(evidence_units) == 328
assert len(expert_queue) == 33
assert Counter(row["evidence_status"] for row in rule_links) == {
    "verified_primary": 15,
    "needs_expert_review": 33,
    "provisional": 308,
    "rejected": 4,
}
```

- [ ] **Step 2: 생성 전 실패 확인**

Run: `.\.venv-research\Scripts\python.exe -m pytest tests\research\test_build_v51_evidence_review.py -q`
Expected: 생성기 또는 산출물이 없어 실패

- [ ] **Step 3: 원문 위치와 규칙 연결을 분리하는 생성기 구현**

```python
unit_key = (row["item_sequence"], row["document_type"], row["source_locator"])
link_status = classify_without_promoting(row, shortlist_by_id, excluded_items)
```

- [ ] **Step 4: 모든 후보에 URL·locator·원문 SHA·접근일·성분·현재 코드 연결·중복 그룹·보류 이유 기록**

- [ ] **Step 5: 생성 결과와 정본 입력의 ID 완전성 확인**

Run: `.\.venv-research\Scripts\python.exe scripts\research\otc\build_v51_evidence_review.py`
Expected: `units=328 links=360 expert_queue=33`

Run: `.\.venv-research\Scripts\python.exe -m pytest tests\research\test_build_v51_evidence_review.py -q`
Expected: PASS

- [ ] **Step 6: 근거 인벤토리 커밋**

```powershell
git add scripts/research/otc/build_v51_evidence_review.py tests/research/test_build_v51_evidence_review.py research_v51/evidence research_v51/review research_v51/audit/evidence_inventory.json
git commit -m "research: v5.1 허가 근거 후보를 전수 분류한다"
```

### Task 3: ruleId 적용 범위와 안전한 비판정 구현

**Files:**
- Create: `research_v51/evidence/active_rule_applicability.csv`
- Modify: `src/lib/otc/schema.ts`
- Modify: `src/lib/otc/engine.ts`
- Modify: `scripts/research/otc/build_runtime.py`
- Modify: `src/generated/otc-runtime.json`
- Test: `__tests__/otc-engine.test.ts`
- Test: `__tests__/otc-product-flow.test.ts`
- Test: `tests/research/test_build_otc_runtime.py`

- [ ] **Step 1: 범위 누출 회귀 테스트 작성**

```ts
expect(evaluate("베아제정", "닥터베아제정").findings).not.toContainRule("duplicate_ingredient");
expect(evaluate("판콜에이내복액", "지르텍정").findings).not.toContainRule("duplicate_pharmacologic_class");
expect(evaluate("어린이부루펜시럽", { medications: ["와파린"] })).toContainRuleId("OTC-RULE-012");
expect(evaluate("어린이부루펜시럽", { medications: ["아픽사반"] })).toReturnCoverageGap();
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run __tests__/otc-engine.test.ts __tests__/otc-product-flow.test.ts`
Expected: 범위 밖 조합과 병용약 오탐 테스트 실패

- [ ] **Step 3: `releasedRules[]`와 `SafetyFinding.ruleId` 추가**

```ts
export type ReleasedRulePolicy = {
  ruleId: string;
  ruleType: string;
  scope: string;
  applicability: RuleApplicability;
  evidence: RuleEvidenceLink[];
};
```

- [ ] **Step 4: 활성 규칙 적용 조건을 v5.1 정책 CSV에서 빌드**

`OTC-RULE-001`은 `ING-acetaminophen`만 허용한다. `OTC-RULE-002`는 NSAID 조합에 `ING-ibuprofen`이 포함될 때만 허용한다. `OTC-RULE-006`은 임신 3기만 판정한다. `OTC-RULE-012`는 와파린·쿠마린 표현만 판정한다.

- [ ] **Step 5: 긴급 증상·근거 중복·단위 불일치 수정**

```ts
const normalizeTerm = (value: string) => value.normalize("NFKC").toLowerCase().replace(/[\s\-_.·]/g, "");
const matches = normalizeTerm(input).includes(normalizeTerm(bindingTerm));
```

정책·binding이 없으면 긴급 판정을 만들지 않는다. 긴급 finding에는 실제 매칭 제품만 넣는다. 근거 중복 키에는 URL을 포함한다. 단위가 다르면 계산을 건너뛰는 대신 coverage gap을 반환한다.

- [ ] **Step 6: focused 검증**

Run: `npx vitest run __tests__/otc-engine.test.ts __tests__/otc-product-flow.test.ts`
Expected: PASS

Run: `.\.venv-research\Scripts\python.exe -m pytest tests\research\test_build_otc_runtime.py -q`
Expected: PASS

- [ ] **Step 7: 규칙 범위 수정 커밋**

```powershell
git add research_v51/evidence/active_rule_applicability.csv src/lib/otc/schema.ts src/lib/otc/engine.ts scripts/research/otc/build_runtime.py src/generated/otc-runtime.json __tests__/otc-engine.test.ts __tests__/otc-product-flow.test.ts tests/research/test_build_otc_runtime.py
git commit -m "fix(otc): 규칙 적용 범위를 ruleId로 제한한다"
```

### Task 4: 문헌 직접성 분류와 표시 정책 구현

**Files:**
- Create: `scripts/research/otc/build_v51_literature_classification.py`
- Create: `research_v51/literature/link_classification.csv`
- Create: `research_v51/audit/literature_link_classification_audit.json`
- Modify: `scripts/research/otc/build_supporting_literature.py`
- Modify: `src/generated/otc-supporting-literature.json`
- Modify: `src/lib/otc/presentation.ts`
- Modify: `src/components/otc-product-safety-client.tsx`
- Test: `tests/research/test_build_v51_literature_classification.py`
- Test: `__tests__/otc-evidence-ux.test.ts`

- [ ] **Step 1: v5 링크 10건의 직접성 분할 테스트 작성**

```python
assert Counter(row["semantic_classification"] for row in emitted) == {
    "direct_match": 1,
    "background_context": 5,
    "mixed_scope": 4,
}
assert all(row["ui_policy"] == "exclude_from_result_ui" for row in rejected)
```

- [ ] **Step 2: 생성 전 실패 확인**

Run: `.\.venv-research\Scripts\python.exe -m pytest tests\research\test_build_v51_literature_classification.py -q`
Expected: FAIL

- [ ] **Step 3: 20개 legacy/v5 링크를 완전 분할하고 런타임 JSON에 link-level 정책 포함**

- [ ] **Step 4: 직접 문헌 선택은 `v5.0 검증 + semantic direct + 성분·제품·프로필 scope 일치`를 모두 요구**

```ts
const direct = link.v50Screened && link.uiPolicy === "direct" && linkScopeMatches(link, finding, profile);
```

- [ ] **Step 5: 배경 연구는 `현재 판정의 직접 근거 아님` 영역에만 표시**

- [ ] **Step 6: focused 검증**

Run: `.\.venv-research\Scripts\python.exe -m pytest tests\research\test_build_v51_literature_classification.py -q`
Expected: PASS

Run: `npx vitest run __tests__/otc-evidence-ux.test.ts`
Expected: PASS

- [ ] **Step 7: 문헌 분류 커밋**

```powershell
git add scripts/research/otc/build_v51_literature_classification.py scripts/research/otc/build_supporting_literature.py research_v51/literature research_v51/audit/literature_link_classification_audit.json src/generated/otc-supporting-literature.json src/lib/otc/presentation.ts src/components/otc-product-safety-client.tsx tests/research/test_build_v51_literature_classification.py __tests__/otc-evidence-ux.test.ts
git commit -m "fix(evidence): 직접 문헌과 배경 연구를 분리한다"
```

### Task 5: 제품별 지원 범위와 미지원 입력 표시

**Files:**
- Modify: `app/page.tsx`
- Modify: `src/components/otc-product-safety-client.tsx`
- Modify: `src/components/otc-product-safety.module.css`
- Modify: `src/lib/otc/presentation.ts`
- Test: `__tests__/otc-layout-contract.test.ts`
- Test: `__tests__/otc-product-flow.test.ts`

- [ ] **Step 1: 제품별 범위 표시 실패 테스트 작성**

```ts
expect(productSupportSummary(digestiveProduct).label).toBe("용량만 확인 가능");
expect(productSupportSummary(ibuprofenProduct).label).toContain("질환·병용약");
```

- [ ] **Step 2: 제품 카드와 선택 결과에 지원 범위 구현**

각 제품에 연결 규칙 수, 허가 조건 수, 지원하는 질환·병용약·긴급 증상 범위를 표시한다. 선택 제품 중 지원 제품이 0개인 입력은 `현재 선택에서는 판정에 사용되지 않음`이라고 입력 위치에서 알린다.

- [ ] **Step 3: 연구용 시제품과 임상 승인 아님을 첫 화면에 명시**

- [ ] **Step 4: focused 검증**

Run: `npx vitest run __tests__/otc-layout-contract.test.ts __tests__/otc-product-flow.test.ts`
Expected: PASS

- [ ] **Step 5: UI 범위 표시 커밋**

```powershell
git add app/page.tsx src/components/otc-product-safety-client.tsx src/components/otc-product-safety.module.css src/lib/otc/presentation.ts __tests__/otc-layout-contract.test.ts __tests__/otc-product-flow.test.ts
git commit -m "feat(site): 제품별 점검 범위를 정확히 표시한다"
```

### Task 6: 전문가 검토 패킷과 최종 보고서 작성

**Files:**
- Create: `research_v51/review/expert_review_packet.md`
- Create: `research_v51/reports/FINAL_REPORT.md`

- [ ] **Step 1: 33개 미검증 항목의 제안 규칙·제품·원문·조건·문구·선택란·쟁점·추가 테스트를 패킷으로 렌더링**

- [ ] **Step 2: 기준선과 최종 수치, 활성 규칙, 보류·기각, 제품별 범위, 문헌 직접성, 테스트, 커밋, push 전 확인 사항을 보고서에 기록**

- [ ] **Step 3: 사람 검토 상태 불변식 확인**

Run: `rg -n "전문가 검토 완료|expert_verified" research_v51`
Expected: 기존 v5.0 검증 primary의 계보 설명 외 신규 완료 표기 없음

- [ ] **Step 4: 문서 커밋**

```powershell
git add research_v51/review/expert_review_packet.md research_v51/reports/FINAL_REPORT.md
git commit -m "docs: v5.1 전문가 검토 패킷과 보고서를 작성한다"
```

### Task 7: 전체 검증과 로컬 인계

**Files:**
- Modify: `research_v51/reports/FINAL_REPORT.md`

- [ ] **Step 1: 연구 테스트**

Run: `.\.venv-research\Scripts\python.exe -m pytest tests\research -q`
Expected: 신규 실패 0

- [ ] **Step 2: 앱 검증 네 가지**

Run: `npm run typecheck`
Expected: PASS

Run: `npm run lint`
Expected: PASS

Run: `npm test`
Expected: PASS

Run: `npm run build`
Expected: PASS

- [ ] **Step 3: 대표 조합 브라우저 검증**

아세트아미노펜 중복은 판정하고, 소화제 중복·항히스타민 중복·비이부프로펜 NSAID 조합은 비판정과 지원 범위 안내를 표시해야 한다. 콘솔 오류, 데스크톱·모바일 잘림, 키보드 초점도 확인한다.

- [ ] **Step 4: 보호 감사와 상태 확인**

Run: `.\.venv-research\Scripts\python.exe scripts\research\otc\audit_v51_boundaries.py`
Expected: PASS

Run: `git status --short --branch`
Expected: `codex/v5.1-safety-expansion`, 의도한 파일 외 변경 없음

- [ ] **Step 5: 검증 결과만 최종 커밋**

```powershell
git add research_v51/reports/FINAL_REPORT.md
git commit -m "docs: v5.1 최종 검증 결과를 기록한다"
```

Push, PR, 배포, 공개 게시는 수행하지 않는다.

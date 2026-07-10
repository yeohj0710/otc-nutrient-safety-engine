# 권혁찬 Research v2 Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 여형준용으로 잘못 생성된 실행패키지를 권혁찬 연구에 맞게 포팅하고, `otc-nutrient-safety-engine` 안에 덮어쓰기 없는 `research_v2` 계보와 자동화된 Gate 0 감사 결과를 만든다.

**Architecture:** 제공 패키지는 `execution_package/`에 원본 계보와 함께 복사한 뒤 권혁찬 정체성·5개 성분 노드·검증 로직만 수정한다. 기존 앱·CSV·문서는 삭제하거나 결과로 승격하지 않고 `legacy_untrusted`로 분류한다. 활성 연구 자료는 `research_v2/`에만 생성하며 모든 감사 산출물은 파일 해시와 Git 정보를 포함한다.

**Tech Stack:** Python 3.12, pytest/unittest, JSON Schema, CSV, Git, existing Next.js 16 repository

---

## 범위 분할

이 계획은 P0만 구현한다. 전체 연구는 다음 독립 계획으로 나눈다.

1. P1: 권혁찬 프로토콜·5개 성분 노드·검색전략 동결
2. P2-P3: 전체 데이터베이스 검색·정규화·중복 제거·사람 선별
3. P4-P6: 전문 추출·RoB·GRADE·AI held-out 평가·근거 합성
4. P7-P8: 검증된 규칙·엔진·독립 시나리오·전문가 평가
5. P9-P10: metrics manifest·논문 DOCX/PDF·앱 릴리스

P0가 통과하기 전에는 위 단계의 연구 결과를 생성하지 않는다.

## 파일 구조

- Create: `execution_package/` — 제공 패키지의 권혁찬용 실행 복사본
- Modify: `execution_package/config/project_identity.json` — 권혁찬·학번·저장소·제목의 단일 기준
- Modify: `execution_package/config/clinical_nodes.json` — K1-K5 성분 중심 연구 노드
- Modify: `execution_package/scripts/bootstrap_research_v2.py` — 권혁찬 모드 부트스트랩
- Modify: `execution_package/scripts/check_project_identity.py` — fail-closed Gate 0
- Modify: `execution_package/scripts/validate_release.py` — 권혁찬 정체성 검사
- Create: `tests/research_v2/test_identity_gate.py` — 정체성 gate 회귀 테스트
- Create: `scripts/research/inventory_legacy.py` — repo·Google Drive 자료의 읽기 전용 목록과 SHA-256 생성
- Create: `tests/research_v2/test_inventory_legacy.py` — inventory 경로·해시·분류 검증
- Create: `research_v2/audit/repo_identity.json` — Gate 0 실제 실행 결과
- Create: `research_v2/audit/legacy_inventory.csv` — 기존 자료 감사 목록
- Create: `research_v2/DECISIONS.md` — 정체성 교정·범위 결정 기록
- Create: `research_v2/HUMAN_ACTION_REQUIRED.md` — 사람 승인·DB 접근 의존성
- Create: `research_v2/audit/gate_status.json` — Gate 0-10 상태

### Task 1: 실행패키지 복사와 원본 무결성 기록

**Files:**
- Create: `execution_package/`
- Create: `execution_package/SOURCE_PROVENANCE.json`

- [ ] **Step 1: 제공 패키지를 새 디렉터리에 복사**

Run:

```powershell
Copy-Item -LiteralPath "G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬_GPT-5.6_260710" -Destination "C:\dev\otc-nutrient-safety-engine\execution_package" -Recurse
```

Expected: `execution_package/PACKAGE_MANIFEST.json` 존재. 기존 repo 파일 변경 없음.

- [ ] **Step 2: manifest 자체검사 실행**

Run:

```powershell
python -c "import hashlib,json,pathlib; r=pathlib.Path('execution_package'); m=json.loads((r/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8')); bad=[x['path'] for x in m['files'] if hashlib.sha256((r/x['path']).read_bytes()).hexdigest()!=x['sha256']]; print({'checked':len(m['files']),'bad':bad}); raise SystemExit(bool(bad))"
```

Expected: `{'checked': 76, 'bad': []}`.

- [ ] **Step 3: 복사 출처 sidecar 작성**

`execution_package/SOURCE_PROVENANCE.json`:

```json
{
  "source_path": "G:\\내 드라이브\\여형준님\\24 전공심화실습(1)\\권혁찬_GPT-5.6_260710",
  "source_package_name": "여형준_졸업논문_재설계_Codex_실행패키지_20260710",
  "source_package_version": "2.0.0",
  "port_target": "권혁찬 연구",
  "port_reason": "사용자 교정: 해당 작업은 권혁찬 연구임",
  "original_manifest_preserved": true
}
```

- [ ] **Step 4: Commit**

```bash
git add execution_package
git commit -m "chore: vendor research v2 execution package"
```

### Task 2: 권혁찬 정체성 테스트를 먼저 작성

**Files:**
- Create: `tests/research_v2/test_identity_gate.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("execution_package/scripts/check_project_identity.py")


def run_gate(root: Path, config: dict[str, object]) -> tuple[int, dict[str, object]]:
    research = root / "research_v2"
    (research / "config").mkdir(parents=True)
    (research / "audit").mkdir(parents=True)
    (research / "config" / "project_identity.json").write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    (research / "project_identity.json").write_text(
        json.dumps({**config, "mode": "kwon_primary_research"}, ensure_ascii=False),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    report = json.loads((research / "audit" / "repo_identity.json").read_text(encoding="utf-8"))
    return result.returncode, report


def kwon_config() -> dict[str, object]:
    return {
        "student_name": "권혁찬",
        "student_id": "2021194024",
        "recommended_repo": "otc-nutrient-safety-engine",
        "study_slug": "kwon-high-dose-otc-nutrient-safety",
        "title_ko": "일반의약품형 고함량 영양성분의 함량 기준 안전성 평가와 근거 추적형 조회 도구의 개발 및 검증",
        "title_en": "Dose-based safety evaluation of high-dose nutrient ingredients and development and validation of a traceable query tool",
    }


def test_gate_accepts_kwon_repo_identity(tmp_path: Path) -> None:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/example/otc-nutrient-safety-engine.git"],
        check=True,
    )
    code, report = run_gate(tmp_path, kwon_config())
    assert code == 0
    assert report["pass"] is True


def test_gate_rejects_yeo_identity_leak(tmp_path: Path) -> None:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/example/otc-nutrient-safety-engine.git"],
        check=True,
    )
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "page.tsx").write_text("여형준 2020194025", encoding="utf-8")
    code, report = run_gate(tmp_path, kwon_config())
    assert code == 1
    assert "yeo_markers_in_active_paths" in report["failures"]
```

- [ ] **Step 2: 테스트가 현재 여형준용 스크립트에서 실패하는지 확인**

Run:

```bash
pytest tests/research_v2/test_identity_gate.py -v
```

Expected: 권혁찬 정상 repo 테스트 FAIL.

### Task 3: 권혁찬 config·5개 노드·Gate 0 구현

**Files:**
- Modify: `execution_package/config/project_identity.json`
- Modify: `execution_package/config/clinical_nodes.json`
- Modify: `execution_package/scripts/bootstrap_research_v2.py`
- Modify: `execution_package/scripts/check_project_identity.py`
- Modify: `execution_package/scripts/validate_release.py`
- Test: `tests/research_v2/test_identity_gate.py`

- [ ] **Step 1: 권혁찬 project identity 작성**

```json
{
  "student_name": "권혁찬",
  "student_id": "2021194024",
  "recommended_repo": "otc-nutrient-safety-engine",
  "disallowed_primary_repo_identity": "여형준",
  "study_slug": "kwon-high-dose-otc-nutrient-safety",
  "title_ko": "일반의약품형 고함량 영양성분의 함량 기준 안전성 평가와 근거 추적형 조회 도구의 개발 및 검증",
  "title_en": "Dose-based safety evaluation of high-dose nutrient ingredients and development and validation of a traceable query tool"
}
```

- [ ] **Step 2: K1-K5 노드 작성**

`clinical_nodes.json`에 아래 ID를 고정한다.

```json
[
  {"id":"K1","ingredient":"vitamin D with or without calcium","primary_outcomes":["hypercalcemia","hypercalciuria","nephrolithiasis"]},
  {"id":"K2","ingredient":"vitamin B6 or B-complex","primary_outcomes":["peripheral neuropathy","neurotoxicity"]},
  {"id":"K3","ingredient":"oral iron","primary_outcomes":["gastrointestinal adverse events","iron overload"]},
  {"id":"K4","ingredient":"supplemental magnesium","primary_outcomes":["diarrhea","hypermagnesemia"]},
  {"id":"K5","ingredient":"zinc","primary_outcomes":["gastrointestinal adverse events","copper deficiency"]}
]
```

- [ ] **Step 3: bootstrap 모드 교정**

`bootstrap_research_v2.py`에서 활성 identity의 mode를 다음 값으로 쓴다.

```python
config["mode"] = "kwon_primary_research"
```

- [ ] **Step 4: Gate 0 marker·remote 논리 교정**

```python
DISALLOWED_MARKERS = (
    "여형준",
    "2020194025",
    "항응고제 복용자와 신장결석 고위험군",
)

remote_matches = bool(remote and recommended_repo in remote)
```

패키지 자체와 `research_v2/audit`, `research_v2/legacy_untrusted`는 marker 검사에서 제외한다.

- [ ] **Step 5: 테스트 통과 확인**

Run:

```bash
pytest tests/research_v2/test_identity_gate.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add execution_package/config execution_package/scripts tests/research_v2/test_identity_gate.py
git commit -m "feat: port research identity gate to Kwon study"
```

### Task 4: 연구 구조 부트스트랩

**Files:**
- Create: `research_v2/**`

- [ ] **Step 1: 부트스트랩 실행**

Run:

```bash
python execution_package/scripts/bootstrap_research_v2.py --repo-root . --package-root execution_package
```

Expected: `research_v2/project_identity.json`, templates, logs created. 기존 파일 overwrite 0건.

- [ ] **Step 2: idempotency 확인**

같은 명령을 다시 실행한다.

Expected: 두 번째 출력의 `created`는 빈 배열이고 모든 기존 경로가 `preserved_existing`에 기록됨.

- [ ] **Step 3: 실제 Gate 0 실행**

Run:

```bash
python execution_package/scripts/check_project_identity.py --root .
```

Expected: exit 0, `research_v2/audit/repo_identity.json`의 `pass: true`.

### Task 5: Legacy inventory를 테스트 주도로 생성

**Files:**
- Create: `scripts/research/inventory_legacy.py`
- Create: `tests/research_v2/test_inventory_legacy.py`
- Create: `research_v2/audit/legacy_inventory.csv`

- [ ] **Step 1: 실패 테스트 작성**

```python
import csv
from pathlib import Path

from scripts.research.inventory_legacy import inventory


def test_inventory_records_sha256_and_classification(tmp_path: Path) -> None:
    source = tmp_path / "legacy"
    source.mkdir()
    (source / "old.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    rows = inventory([source], repo_root=tmp_path)
    assert len(rows) == 1
    assert len(rows[0]["sha256"]) == 64
    assert rows[0]["trust_status"] == "legacy_untrusted"
    assert rows[0]["disposition"] == "audit_only"
```

- [ ] **Step 2: 테스트 실패 확인**

Run:

```bash
pytest tests/research_v2/test_inventory_legacy.py -v
```

Expected: import failure.

- [ ] **Step 3: 최소 구현 작성**

```python
from __future__ import annotations

import hashlib
from pathlib import Path


def inventory(roots: list[Path], repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for root in roots:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            rows.append({
                "source_root": str(root),
                "path": str(path),
                "extension": path.suffix.lower(),
                "size_bytes": str(path.stat().st_size),
                "modified_utc": path.stat().st_mtime_ns.__str__(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "trust_status": "legacy_untrusted",
                "disposition": "audit_only",
                "reason": "predates research_v2 evidence lineage",
            })
    return rows
```

CLI는 repo tracked files와 아래 Google Drive 폴더를 읽기 전용으로 받는다.

```text
G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬
```

- [ ] **Step 4: inventory 생성**

Run:

```bash
python scripts/research/inventory_legacy.py --repo-root . --source "G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬" --out research_v2/audit/legacy_inventory.csv
```

Expected: 모든 행에 64자 SHA-256, `legacy_untrusted`, `audit_only` 존재.

- [ ] **Step 5: 테스트 통과 확인**

Run:

```bash
pytest tests/research_v2/test_inventory_legacy.py -v
```

Expected: 1 passed.

### Task 6: 결정·오류·사람 의존성 기록

**Files:**
- Modify: `research_v2/DECISIONS.md`
- Modify: `research_v2/CHANGELOG_RESEARCH.md`
- Modify: `research_v2/HUMAN_ACTION_REQUIRED.md`
- Create: `research_v2/audit/gate_status.json`
- Create: `research_v2/audit/baseline_test_report.json`

- [ ] **Step 1: 정체성 교정 결정 기록**

`DECISIONS.md`에 다음 사실을 기록한다.

```text
2026-07-10 / D-0001 / 결과 확인 전
기존 패키지의 여형준·2020194025·항응고제/신장결석 전제를 폐기한다.
기준 학생은 권혁찬(2021194024), 기준 저장소는 otc-nutrient-safety-engine이다.
연구 범위는 K1-K5 고함량 성분 노드이며 기존 CSV·규칙·논문은 legacy_untrusted다.
```

- [ ] **Step 2: baseline 오류 기록**

`baseline_test_report.json`에 다음 실측 결과를 쓴다.

```json
{
  "date": "2026-07-10",
  "git_head": "212510d",
  "node_tests": {"status": "pass", "test_files": 7, "tests": 33},
  "typecheck": {"status": "pass"},
  "python_tests": {"status": "fail", "error": "ModuleNotFoundError: No module named 'requests'"},
  "generated_file_changed": "src/generated/literature-candidates.json",
  "error_code": "ENV-DEPENDENCY-MISSING"
}
```

- [ ] **Step 3: 사람 작업 기록**

`HUMAN_ACTION_REQUIRED.md`에 각각 필요한 입력 형식과 차단 작업을 명시한다.

```text
- 지도교수의 K1-K5·주요 결과·집중 합성 선정 규칙 승인: 서명/이메일/회의록, Gate 1 차단
- PRESS 또는 동료 검색전략 검토: peer_review.csv, Gate 2 최종식 차단
- Embase/CENTRAL/인용색인 접근: RIS/CSV 전체 export, Gate 2 차단
- 제2검토자·조정자 판정: reviewer ID가 있는 CSV, Gate 3-5 차단
- 전문 패널 시나리오·내용타당도 평가: 서명된 독립 양식, Gate 8 차단
- IRB/면제 판단: 사람 대상 사용성 연구를 수행할 경우에만 Gate 8 일부 차단
```

- [ ] **Step 4: Gate 상태 기록**

```json
{
  "gate_0": {"status": "passed", "evidence": ["audit/repo_identity.json", "audit/legacy_inventory.csv"]},
  "gate_1": {"status": "blocked_human_action", "reason": "protocol approval not supplied"},
  "gate_2": {"status": "not_started"},
  "gate_3": {"status": "not_started"},
  "gate_4": {"status": "not_started"},
  "gate_5": {"status": "not_started"},
  "gate_6": {"status": "not_started"},
  "gate_7": {"status": "not_started"},
  "gate_8": {"status": "not_started"},
  "gate_9": {"status": "not_started"},
  "gate_10": {"status": "not_started"}
}
```

### Task 7: P0 최종 검증

**Files:**
- Modify: `research_v2/audit/gate_status.json`

- [ ] **Step 1: 전체 P0 테스트 실행**

Run:

```bash
pytest tests/research_v2 -v
python execution_package/scripts/check_project_identity.py --root .
python -m json.tool research_v2/audit/repo_identity.json > NUL
python -m json.tool research_v2/audit/gate_status.json > NUL
git diff --check
```

Expected: 모든 명령 exit 0.

- [ ] **Step 2: legacy 수치 비승격 검사**

Run:

```powershell
rg -n "33552|52701|435|172|180" research_v2 -g "!audit/**" -g "!legacy_untrusted/**"
```

Expected: 활성 연구 결과에서 0건.

- [ ] **Step 3: 최종 상태 확인**

Run:

```bash
git status --short
```

Expected: 계획된 P0 파일만 변경. 사용자 기존 변경 없음.

- [ ] **Step 4: Commit**

```bash
git add research_v2 scripts/research tests/research_v2 docs/superpowers/plans/2026-07-10-kwon-research-v2-bootstrap.md
git commit -m "feat: establish Kwon research v2 gate zero"
```

## Self-review

- Spec coverage: 학생·학번·repo 교정, legacy 격리, Gate 0 코드·실행, 감사 3종 파일 포함.
- Placeholder scan: 미정 상태를 실행 단계나 산출물로 남긴 항목 없음.
- Type consistency: `student_name`, `student_id`, `recommended_repo`, `study_slug`, `title_ko`, `title_en` 키를 config·gate·test에서 동일 사용.
- Out of scope: DB 검색·사람 선별·전문 평가·논문 집필은 P0 통과 전 수행하지 않음.

# v5.0 정본과 로컬 v5.1 재현 안내

모든 명령은 `C:\dev\otc-nutrient-safety-engine`에서 PowerShell로 실행한다. 이 문서는
구세대 `research_v2/` 실행 절차가 아니다.

연구용 Python 잠금 파일의 대상은 Python 3.12.13이다. 먼저 `py -3.12`가 정확히
Python 3.12.13을 가리키는지 확인한다. 이 검사가 실패하면 Python 3.12.13을 설치하기 전까지
잠금 환경을 재현했다고 판정하지 않는다.

```powershell
$actualResearchPython = py -3.12 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12.13이 필요합니다.' }
$actualResearchPython = ($actualResearchPython -join "`n").Trim()
if ($actualResearchPython -ne '3.12.13') {
  throw "Python 3.12.13이 필요합니다. 실제 버전: $actualResearchPython"
}
py -3.12 -m venv .venv-research
if ($LASTEXITCODE -ne 0) { throw '연구용 가상환경을 만들지 못했습니다.' }
.\.venv-research\Scripts\python.exe -m pip install -r requirements-research.lock
if ($LASTEXITCODE -ne 0) { throw '연구용 Python 의존성을 설치하지 못했습니다.' }
npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Node 의존성을 설치하지 못했습니다.' }
Get-Command pdftotext -ErrorAction Stop
```

현재 Windows `py` launcher에는 Python 3.14.2만 등록돼 있다. 최종 잠금 검증은 별도로 제공된
`C:\Users\hjyeo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`
3.12.13으로 `etc\v51-py312-lock-venv`를 만들고, 잠금 파일의 pytest 9.1.1을 설치해 수행했다.
다른 Python·pytest 버전으로 호환성 검증을 실행했다면 최종 보고서에 잠금 대상과 실제 버전을
함께 기록한다.

## v5.0 제출 최종본은 별도 정본이다

v5.0 정본은 `research_v3/`에 있고 최종 원장은
`research_v3/logs/v50_run_report.json`이다. v5.0의 제품·규칙·문헌·측정 결과를 재현하는 기존
절차는 `research_v3/REPRODUCE.md`를 따른다. v5.0 채점 arm의 별도 절차는
`research_v3/protocol/HANDOFF_v50_scoring.md`에 있다.

로컬 v5.1 작업 트리에서는 두 문서가 가리키는 v5.0 생성기를 다시 실행하지 않는다. v5.1은
commit `6dbdad518e2fa7b2ed7b9a8048e0c47dba5b6ae9`의 `research_v3/` tree를 비교 기준으로 읽기만
한다. 먼저 보호 경계를 확인한다.

```powershell
.\.venv-research\Scripts\python.exe scripts\research\otc\audit_v51_boundaries.py
.\.venv-research\Scripts\python.exe -m pytest tests\research\test_v51_boundary_audit.py -q
```

출력의 `valid=true`, `verification_complete=true`,
`external_verification.verified_artifacts=2`를 모두 확인한다. G 드라이브 제출 논문 2개를
확인하지 못하면 portable 저장소 검사만 통과한 것이며 최종 로컬 보고를 완료할 수 없다.

## 로컬 v5.1 산출물을 순서대로 만든다

아래 명령은 `research_v51/`과 현재 애플리케이션 런타임을 갱신한다. 사람 검토 필드는 자동으로
채우지 않으며 새 후보를 활성화하지 않는다.

```powershell
.\.venv-research\Scripts\python.exe scripts\research\otc\build_v51_evidence_review.py
.\.venv-research\Scripts\python.exe scripts\research\otc\validate_v51_shortlist_triage.py --check
.\.venv-research\Scripts\python.exe scripts\research\otc\build_v51_review_packet.py
.\.venv-research\Scripts\python.exe scripts\research\otc\build_runtime.py
.\.venv-research\Scripts\python.exe scripts\research\otc\build_v51_literature_classification.py
.\.venv-research\Scripts\python.exe scripts\research\otc\build_supporting_literature.py
```

생성 뒤 다음 계약이 유지돼야 한다.

- 기존 약사 검토를 상속한 운영 근거 15건
- 비활성 후보 345건: `needs_expert_review` 33건, `provisional` 308건, `rejected` 4건
- 후보–규칙 연결 360건의 문서 개정일 확인 355건과 개정일 미공개 사유 5건
- 전문가 패킷 33건의 제품·성분, 문서 유형·개정일·UTC 접근일, 완결 공식 원문과
  정상·경계·비대상·오탐 방지 회귀 시나리오
- 제품 13개, released 규칙 15개, `ADMIN-*` 허가 복용 조건 32개
- 새로 활성화한 규칙과 후보 0건
- `release_ready=false`

## 식약처 원격 문서가 같은 내용을 담는지 확인한다

다음 감사는 식약처 PDF URL 20개에 접속하므로 네트워크가 필요하다. PDF 원시 바이트가 아니라
공백을 제거하고 Unicode NFKC로 정규화한 추출 문서를 비교한다. 의미 차이 또는 접근 실패가
있으면 종료 코드 1을 반환한다.

```powershell
Get-Command pdftotext -ErrorAction Stop
.\.venv-research\Scripts\python.exe scripts\research\otc\audit_v51_source_freshness.py
.\.venv-research\Scripts\python.exe -m pytest tests\research\test_audit_v51_source_freshness.py -q
```

원격 PDF 바이트가 달라졌다는 이유만으로 source version을 교체하거나 규칙을 넓히지 않는다.
문서 내용이 달라졌다면 새 후보로 기록하고 사람 전문가의 확인을 받는다.

## 기계 집계를 갱신하고 고정 입력과 대조한다

근거와 런타임, 문헌 분류가 모두 안정된 뒤 최종 기계 집계를 만든다. 기본 실행은 저장소 안의
입력만 검사하므로 G 드라이브가 없는 환경에서도 재현할 수 있다. 최종 로컬 보고를 만들 때는
`--require-external`을 붙여 외부 제출 논문 2개까지 확인한다. `--check`는 현재 파일을 다시
계산한 값과 비교한다.

```powershell
.\.venv-research\Scripts\python.exe scripts\research\otc\build_v51_final_audit.py --require-external
.\.venv-research\Scripts\python.exe scripts\research\otc\build_v51_final_audit.py --check --require-external
```

G 드라이브를 사용할 수 없는 자동화 환경은 마지막 두 명령에서 `--require-external`을 빼고
portable 저장소 검증만 수행한다. 이 결과만으로 최종 로컬 보고가 완료됐다고 판정하면 안 된다.
`final_metrics.json`은 실행 모드와 무관한 portable 저장소 불변조건을 기록하므로 두 모드에서
바이트가 같다. 외부 정본 확인 완료 여부와 `final_local_report_ready`는 CLI 결과에서 확인한다.
portable 모드는 `false`이고, external 모드는 외부 정본 2/2가 통과할 때만 `true`다.

## v5.1 집중 테스트와 전체 애플리케이션 검증

```powershell
.\.venv-research\Scripts\python.exe -m pytest `
  tests\research\test_v51_boundary_audit.py `
  tests\research\test_build_v51_evidence_review.py `
  tests\research\test_validate_v51_shortlist_triage.py `
  tests\research\test_build_v51_review_packet.py `
  tests\research\test_build_otc_runtime_v51.py `
  tests\research\test_build_v51_literature_classification.py `
  tests\research\test_audit_v51_source_freshness.py `
  tests\research\test_build_v51_final_audit.py -q

.\.venv-research\Scripts\python.exe -m pytest tests\research -q
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

테스트 통과는 데이터 계약과 구현 재현성을 확인한다. 임상 정확도나 실제 사용자의 이해도를
증명하지 않는다.

## production 화면을 브라우저에서 확인한다

첫 번째 PowerShell에서 production 서버를 실행한다.

```powershell
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'production build에 실패했습니다.' }
npm.cmd start -- --hostname 127.0.0.1 --port 3101
if ($LASTEXITCODE -ne 0) { throw "production 서버 실행에 실패했습니다: exit $LASTEXITCODE" }
```

두 번째 PowerShell에서 같은 production URL을 Playwright CLI로 연다. 아래 명령은 QA에 사용한
Playwright CLI 0.1.17을 고정하고, Chromium 설치·화면 너비·키보드·결과 이동·콘솔을 확인한다.

```powershell
function Invoke-V51Playwright {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArguments
  )

  & npx.cmd --yes --package @playwright/cli@0.1.17 playwright-cli @CommandArguments
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "Playwright CLI 실패: $($CommandArguments -join ' ') (exit $exitCode)"
  }
}

Invoke-V51Playwright install-browser chromium
Invoke-V51Playwright -s=v51qa open http://127.0.0.1:3101/
Invoke-V51Playwright -s=v51qa resize 1440 1000
Invoke-V51Playwright -s=v51qa snapshot
Invoke-V51Playwright -s=v51qa eval "() => { const state = { innerWidth: window.innerWidth, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }; if (state.innerWidth !== 1440 || state.clientWidth !== 1440 || state.scrollWidth !== state.clientWidth) throw new Error('desktop viewport mismatch: ' + JSON.stringify(state)); return state; }"
Invoke-V51Playwright -s=v51qa run-code "async (page) => { await page.getByRole('button', { name: /감기약 \+ 해열제/ }).click(); await page.waitForTimeout(2500); }"
Invoke-V51Playwright -s=v51qa eval "() => { const result = document.getElementById('safety-result'); if (!result) throw new Error('result missing'); const state = { resultTop: result.getBoundingClientRect().top, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }; const text = result.textContent || ''; if (state.resultTop < 64 || state.resultTop > 96) throw new Error('desktop result geometry mismatch: ' + JSON.stringify(state)); if (state.clientWidth !== 1440 || state.scrollWidth !== state.clientWidth) throw new Error('desktop overflow mismatch: ' + JSON.stringify(state)); if (!text.includes('같은 성분이 여러 제품에 들어 있습니다') || !text.includes('800 mg') || !text.includes('1개 주의 항목')) throw new Error('desktop duplicate-ingredient result mismatch'); return state; }"
Invoke-V51Playwright -s=v51qa resize 390 844
Invoke-V51Playwright -s=v51qa goto http://127.0.0.1:3101/
Invoke-V51Playwright -s=v51qa snapshot
Invoke-V51Playwright -s=v51qa eval "() => { const state = { innerWidth: window.innerWidth, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }; if (state.innerWidth !== 390 || state.clientWidth !== 390 || state.scrollWidth !== state.clientWidth) throw new Error('mobile viewport mismatch: ' + JSON.stringify(state)); return state; }"
Invoke-V51Playwright -s=v51qa press Tab
Invoke-V51Playwright -s=v51qa eval "() => { const active = document.activeElement; if (!active) throw new Error('active element missing'); const style = getComputedStyle(active); const state = { tag: active.tagName, text: active.textContent?.trim(), href: active.getAttribute('href'), outline: style.outline }; if (state.tag !== 'A' || state.text !== '본문 바로가기' || state.href !== '#main-content' || style.outlineStyle !== 'solid' || parseFloat(style.outlineWidth) < 2) throw new Error('skip-link focus mismatch: ' + JSON.stringify(state)); return state; }"
Invoke-V51Playwright -s=v51qa run-code "async (page) => { await page.getByRole('button', { name: /감기약 \+ 해열제/ }).focus(); }"
Invoke-V51Playwright -s=v51qa eval "() => { const active = document.activeElement; if (!active) throw new Error('active element missing'); const style = getComputedStyle(active); const state = { tag: active.tagName, label: active.getAttribute('aria-label'), outline: style.outline }; if (state.tag !== 'BUTTON' || !state.label?.startsWith('감기약 + 해열제:') || style.outlineStyle !== 'solid' || parseFloat(style.outlineWidth) < 3) throw new Error('first demo focus mismatch: ' + JSON.stringify(state)); return state; }"
Invoke-V51Playwright -s=v51qa press Enter
Invoke-V51Playwright -s=v51qa run-code "async (page) => { await page.waitForTimeout(2500); }"
Invoke-V51Playwright -s=v51qa eval "() => { const result = document.getElementById('safety-result'); if (!result) throw new Error('result missing'); const state = { resultTop: result.getBoundingClientRect().top, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }; const text = result.textContent || ''; if (state.resultTop < 64 || state.resultTop > 96) throw new Error('mobile result geometry mismatch: ' + JSON.stringify(state)); if (state.clientWidth !== 390 || state.scrollWidth !== state.clientWidth) throw new Error('mobile overflow mismatch: ' + JSON.stringify(state)); if (!text.includes('같은 성분이 여러 제품에 들어 있습니다') || !text.includes('800 mg') || !text.includes('1개 주의 항목')) throw new Error('mobile duplicate-ingredient result mismatch'); return state; }"
Invoke-V51Playwright -s=v51qa screenshot
Invoke-V51Playwright -s=v51qa run-code "async (page) => { await page.waitForTimeout(3000); }"
$consoleMessages = @(Invoke-V51Playwright -s=v51qa console warning)
$consoleText = $consoleMessages -join "`n"
Write-Output $consoleText
if ($consoleText -notmatch 'Errors:\s*0') {
  throw "브라우저 콘솔 오류가 남았습니다:`n$consoleText"
}
Invoke-V51Playwright -s=v51qa close
```

나머지 판정 시나리오는 snapshot의 접근성 ref로 입력 필드와 데모 버튼을 조작한다. 정확한 나이,
제품별 사용량·횟수, 임신 시기, 병용약 문자열, 기대 결과와 실제 콘솔 경고 수는
`research_v51/audit/BROWSER_QA.md`의 표를 그대로 사용한다.

## 커밋된 파일만 별도 worktree에서 자동 검증한다

로컬 커밋을 만든 뒤 저장소의 `etc/` 아래에 임시 detached worktree를 만들면 동시 작업자의
미커밋 변경과 분리해서 검증할 수 있다. 다음 명령은 임시 worktree 안에서 의존성을 설치하고
커밋된 감사 산출물의 일치, 전체 자동 테스트, 정적 검사와 production build를 다시 확인한다.
이 블록은 원격 식약처 PDF를 다시 받는 live source freshness 감사와 production 브라우저 QA를
실행하지 않는다. 두 검증은 이 블록이 통과한 뒤 `$verificationTree`에서 앞 절의 절차를 별도로
실행하고 결과를 기록한다.

```powershell
$ErrorActionPreference = 'Stop'
function Assert-NativeSuccess([string]$step) {
  if ($LASTEXITCODE -ne 0) { throw "$step 실패: exit $LASTEXITCODE" }
}

$repositoryRoot = (Resolve-Path -LiteralPath .).Path
$verificationTree = Join-Path $repositoryRoot 'etc\v51-clean-worktree'
git worktree add --detach $verificationTree HEAD
Assert-NativeSuccess 'git worktree add'
$locationPushed = $false
try {
  Push-Location -LiteralPath $verificationTree
  $locationPushed = $true
  $actualTree = (Resolve-Path -LiteralPath .).Path
  $expectedTree = (Resolve-Path -LiteralPath $verificationTree).Path
  if ($actualTree -ne $expectedTree) { throw "검증 위치 불일치: $actualTree" }

  $actualResearchPython = py -3.12 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
  Assert-NativeSuccess 'Python 3.12.13 preflight'
  $actualResearchPython = ($actualResearchPython -join "`n").Trim()
  if ($actualResearchPython -ne '3.12.13') {
    throw "Python 3.12.13이 필요합니다. 실제 버전: $actualResearchPython"
  }
  py -3.12 -m venv .venv-research
  Assert-NativeSuccess '연구용 가상환경 생성'
  .\.venv-research\Scripts\python.exe -m pip install -r requirements-research.lock
  Assert-NativeSuccess '연구용 Python 의존성 설치'
  npm.cmd ci
  Assert-NativeSuccess 'npm ci'
  .\.venv-research\Scripts\python.exe scripts\research\otc\audit_v51_boundaries.py
  Assert-NativeSuccess '보존 감사'
  .\.venv-research\Scripts\python.exe scripts\research\otc\build_v51_final_audit.py --check
  Assert-NativeSuccess '최종 감사 check'
  .\.venv-research\Scripts\python.exe -m pytest -q
  Assert-NativeSuccess 'Python 전체 테스트'
  npm.cmd run typecheck
  Assert-NativeSuccess 'TypeScript 검사'
  npm.cmd run lint
  Assert-NativeSuccess 'ESLint'
  npm.cmd test
  Assert-NativeSuccess 'Vitest 전체 테스트'
  npm.cmd run build
  Assert-NativeSuccess 'production build'
  git diff --exit-code
  Assert-NativeSuccess 'tracked 파일 재현성'
  $uncommitted = git status --porcelain
  Assert-NativeSuccess 'git status'
  if ($uncommitted) { throw "깨끗한 worktree에 변경이 생겼습니다:`n$uncommitted" }
} finally {
  if ($locationPushed) { Pop-Location }
}
```

검증 결과를 기록한 뒤, 경로가 `$verificationTree`와 정확히 같은지 확인하고 Codex가 만든 임시
worktree만 `git worktree remove --force $verificationTree`로 제거한다.

## 작업을 마칠 때 경계를 다시 확인한다

```powershell
.\.venv-research\Scripts\python.exe scripts\research\otc\audit_v51_boundaries.py
git status --short
```

v5.1은 로컬 브랜치와 로컬 커밋까지만 허용한다. 연구자가 명시적으로 승인하기 전에는
`git push`, PR 생성, production 배포, 공개 게시 또는 G 드라이브 정본 교체를 하지 않는다.

Reference basis: tossfeed-easy-finance

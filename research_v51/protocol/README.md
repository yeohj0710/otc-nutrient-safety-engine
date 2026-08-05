# v5.1은 v5.0을 덮어쓰지 않는다

v5.1은 실사용 범위를 넓히는 별도 연구 트랙이다. v5.0의 제품·규칙·문헌·측정 결과와
최종 논문은 비교 기준으로만 읽는다. v5.1 결과를 v5.0 결과처럼 소급 기록하지 않는다.

## 무엇을 고정하나

baseline commit은 `6dbdad518e2fa7b2ed7b9a8048e0c47dba5b6ae9`(`6dbdad5`)이다.
이 커밋의 `research_v3/` Git tree 전체를 v5.0 정본으로 고정한다.

특히 다음 경로는 수정·삭제하거나 새 파일을 추가하지 않는다.

- `research_v3/otc/normalized/`: 허가원문 제품·성분·복용 조건
- `research_v3/otc/rules/`: v5.0 규칙과 근거 후보
- `research_v3/otc/literature/v5/`: v5.0 문헌 코퍼스·선별·직접 연결
- `research_v3/logs/v50_*`: 실행 원장·요약·채점 결과
- `research_v3/protocol/`: 채택 프로토콜과 AM-OTC-001~005
- `research_v3/otc/validation/`, `research_v3/measurement/`: 기존 측정 결과
- `research_v3/thesis/`: 저장소 안의 이전 논문 계보

현재 v5.0 논문은 저장소 밖 다음 두 파일이다. 이번 작업에서는 두 파일도 읽기만 한다.

- `G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\06_졸업논문\권혁찬_졸업논문_최종본.docx`
- `G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬\06_졸업논문\권혁찬_졸업논문_최종본.pdf`

v5.1 연구 산출물은 `research_v51/` 아래에만 새 파일로 만든다. 코드와 테스트는 기존
애플리케이션 경로에서 바꿀 수 있지만, v5.0 연구 데이터를 고쳐서 v5.1 결과를 만들면 안 된다.

## 후보 상태는 무엇을 뜻하나

근거 상태와 운영 상태를 따로 기록한다. 상태는 근거 단위 328건이 아니라 후보–규칙 연결
360건에 붙는다.

- 현재 `verified_primary` 15건은 v5.0에서 상속한 운영 근거다. 각 행은
  `human_expert_verified`, `supports_release=true`, released 규칙, `pharmacist_expert` 검토
  메타데이터와 허가원문 source·version·locator를 모두 충족한다.
- `needs_expert_review` 33건은 의약학 판단이나 적용 범위를 사람이 확인하기 전까지 비활성이다.
- `provisional` 308건은 1차 출처 후보가 있지만 범위나 조건을 더 확인해야 하므로 비활성이다.
- `rejected` 4건은 분석 제외 제품의 후보이며 운영 판정에 쓰지 않는다.

따라서 기존 운영 근거는 15건이고 비활성 후보는 345건(33+308+4)이다. v5.1에서 새로 수행한
사람 전문가 검토나 새로 활성화한 규칙·후보는 없다.

`verified_primary`라는 일반적인 근거 라벨만으로 미래 후보의 사람 승인까지 증명할 수는 없다.
미래 후보를 활성화하려면 공식 1차 출처 대조 외에도 사람의 명시적 승인, 안정적인 rule ID,
허가원문 source·version·locator, 제한된 적용 범위, 사용자 문구와 정상·경계·비대상·오탐 방지
테스트를 모두 갖춰야 한다. 사람이 확인하지 않은 후보에 `approved`, `전문가 검토 완료` 또는
`sealed`를 기록하지 않는다.

## 허가원문은 판정하고 문헌은 설명한다

식약처 허가원문은 제품, 성분, 함량, 복용 조건과 규칙 판정을 결정한다. PubMed 문헌은 위해
연관성을 설명할 수 있지만 허가 판정을 넓히거나 뒤집지 못한다. 두 근거는 별도 필드에 저장하고,
충돌하면 `conflict`로 남긴다.

문헌을 직접 근거로 표시하려면 규칙의 성분·대상·조건·결과가 직접 대응해야 한다. 직접 일치하지
않으면 `직접 일치 문헌 없음`으로 표시한다. 다른 성분 연구나 배경 문헌을 현재 판정의 직접
근거처럼 노출하지 않는다.

## 로컬 검증까지만 한다

이 트랙은 로컬 브랜치와 로컬 커밋까지만 허용한다. `git push`, PR 생성, production 배포,
공개 게시, G 드라이브 정본 교체는 사용자 명시 승인 전 금지한다. `release_ready=false`는 유지한다.

경계 감사는 다음 명령으로 실행한다.

```powershell
.\.venv-research\Scripts\python.exe scripts\research\otc\audit_v51_boundaries.py
.\.venv-research\Scripts\python.exe -m pytest tests\research\test_v51_boundary_audit.py -q
```

감사는 다음 상황에서 실패한다.

- 현재 HEAD의 `research_v3/` tree가 baseline commit과 다르다.
- `research_v3/`의 staged 또는 unstaged 파일이 HEAD와 다르다.
- `research_v3/`에 Git이 무시하지 않는 untracked 파일이 생겼다.
- 핵심 정본 파일의 바이트 수나 SHA-256이 manifest와 다르다.
- 제품·성분·규칙·후보·문헌·채점 수치가 manifest와 다르다.

감사 스크립트는 `captured_at=2026-07-31`, baseline commit과 `research_v3` tree, 핵심 파일·수치
선언을 별도 계약 digest로 고정한다. manifest가 이 계약과 다르면 선언값을 사용하기 전에
실패한다.

## 검증 환경이 다르면 같은 검사가 모두 가능하지 않다

baseline은 Windows의 `C:\dev\otc-nutrient-safety-engine`에서 만들었다. 보호된 `research_v3`
핵심 파일의 이식 가능한 SHA-256은 고정 commit의 Git blob 바이트를 기준으로 한다. 감사기는
`HEAD:research_v3` tree와 tracked·untracked 상태도 따로 확인한다. 따라서 `core.autocrlf`
설정이 달라도 같은 Git tree는 같은 기준 입력으로 계산되며, 작업 트리의 실제 변경은 허용하지
않는다.

G 드라이브 논문은 로컬 Windows 환경에만 있다. 기본 최종 감사는 저장소 안의 고정 입력과
산출물을 이식 가능한 범위에서 생성·검사하고, 외부 논문 검사를 건너뛴 사실을 명시한다. 최종
로컬 보고에는 `--require-external` 검사를 추가로 통과해야 한다. G 드라이브가 연결된 환경에서
논문 파일이 없거나 해시가 다르면 이 외부 검사는 실패한다.

외부 논문은 같은 파일 핸들의 identity·크기·SHA-256을 읽기 전후와 반환 직전에 다시 확인한다.
Google Drive 가상 볼륨이 link count를 0으로 보고하면 Windows 볼륨 플래그에서 hardlink 미지원이
확인된 경우에만 허용한다. hardlink 지원 여부를 확인하지 못하거나 지원 볼륨에서 link count가
0이면 검사를 실패 처리한다.

최종 감사 출력 3개는 제품 행렬, 규칙 행렬, `final_metrics.json` 순서로 게시한다. 첫 출력을
게시한 뒤 오류가 나면 생성기는 동시 작성자의 파일을 지울 수 있는 자동 rollback을 하지 않고
partial-publication 오류로 중단한다. `--check`로 혼합 출력 세트를 확인한 뒤 원인을 해결하고
생성기를 다시 실행해야 한다. `final_metrics.json`은 완료 표지 역할을 하도록 항상 마지막에
게시한다. 예외 경로에서는 임시 pathname도 자동 삭제하지 않으며 오류의 `retained_staged`에
남은 경로를 표시한다. 정상 완료 시에는 세 임시 파일이 모두 정본 경로로 이동하므로 남지 않는다.

전문가 패킷과 패킷 감사 파일도 같은 동시 작성자 보존 원칙을 따른다. 둘 중 하나를 게시한 뒤
실패하면 이전 파일로 자동 rollback하거나 현재 경로를 `unlink`하지 않는다. 오류가 가리키는
게시 경로와 staged 경로를 확인하고 생성기를 다시 실행한다.

`research_v3/`에는 baseline 당시 이미 존재하던 ignored 파일이 있다. 감사기는 Git이 무시하지
않는 새 untracked 파일을 차단하지만, 기존 ignored 파일의 과거 동일성은 증명하지 않는다.
또한 README의 v4.0 수치와 문서별 과거 테스트 개수는 현재 v5.0 기준선이 아니다. 기준 수치는
`research_v51/audit/baseline_manifest.json`과 그 파일이 가리키는 정본에서 다시 계산한다.

## 식약처 PDF의 원시 바이트와 문서 내용을 구분한다

식약처 PDF URL은 같은 문서 내용을 요청해도 PDF 내부 메타데이터가 달라진 새 파일을 반환할 수
있다. 실제로 2026-07-31 같은 URL을 연속 요청했을 때 PDF SHA-256은 달랐지만 `pdftotext
-layout -enc UTF-8`로 추출한 문서는 같았다. 따라서 `source_version=sha256:<값>`은
2026-07-14에 보관한 PDF 스냅샷의 바이트 식별자다. 현재 허가문구가 달라졌는지는 원격 PDF
바이트 해시만으로 판단하지 않는다.

현재 출처 감사는 추출 문서를 Unicode NFKC로 정규화한 뒤 모든 공백을 제거하고 비교한다.
구두점과 실제 문자는 그대로 비교한다. 문서 20개와 후보–규칙 연결 원문 360건의 결과는
`research_v51/audit/source_freshness_snapshot.json`에 기록한다. 다음 명령은 식약처 서버를
다시 조회하므로 네트워크에 연결된 환경에서 실행한다.

```powershell
.\.venv-research\Scripts\python.exe scripts\research\otc\audit_v51_source_freshness.py
.\.venv-research\Scripts\python.exe -m pytest tests\research\test_audit_v51_source_freshness.py -q
```

원격 문서에 의미 차이가 있거나 문서를 받지 못하면 감사 명령은 1을 반환한다. 이 결과만으로
새 규칙을 만들거나 기존 규칙을 넓히지 않는다. 변경된 원문을 별도 후보로 기록하고 사람 전문가의
확인을 받아야 한다.

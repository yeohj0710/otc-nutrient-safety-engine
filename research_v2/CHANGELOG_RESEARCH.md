# Research changelog

## 2026-07-10 — PubMed 타당성 연구본 release

- K2–K5 검색식을 v0.2로 개정해 사전 seed 회수를 15/22에서 22/22로 교정했다.
- PubMed occurrence 16,194건을 전량 보존하고 15,890개 고유 레코드를 생성했다.
- 사전 seed 22건의 초록 근거 지도와 source locator 22개를 생성했다.
- 규칙 5개는 `draft_ai`, released 규칙은 0개로 유지했다.
- 미확보 임상 성능 지표를 `not_evaluated`로 기록했다.
- 권혁찬 연구본 DOCX/PDF를 생성하고 7쪽을 렌더링 검사했다.
- `validate_feasibility_release.py` 통과. 임상 release 권한은 false다.

## 2026-07-10

- 제공 실행패키지 76개 해시 검증 후 `execution_package/`에 복사.
- 권혁찬·2021194024·`otc-nutrient-safety-engine` 기준으로 Gate 0 포팅.
- K1-K5 성분 노드 설정.
- `research_v2` 비덮어쓰기 부트스트랩과 두 번째 실행 idempotency 확인.
- 기존 repo 156개 파일과 Google Drive 권혁찬 자료 361개 파일의 SHA-256 inventory 생성.
- 기준선 테스트에서 Node 33개 통과, TypeScript typecheck 통과, Python 환경 의존성 실패와 비결정적 생성시각 변경을 기록.
- Python 3.12.13 독립 환경과 `requirements-research.lock` 생성; Python 전체 9개 테스트 통과.
- RIS `JF` 저널명 누락을 `alternate_title3` 매핑으로 수정하고 회귀 테스트 통과.
- 문헌후보 JSON의 생성시각을 최신 검색일로 결정론화하고 연속 두 번 생성 해시 일치 확인.
- reference provenance의 Google Drive 상위 폴더명으로 발생한 Gate 0 오탐을 좁은 파일 예외로 수정; 활성 앱 identity leak 검사는 유지.
- K1-K5 프로토콜 v0.1, 적격 기준, PubMed 검색식 5개, seed 후보 22개, 동료 검토 양식 작성.
- PubMed pipeline을 전량 반입 기본값으로 변경; 10,000 UID 초과와 export/import 불일치는 부분 저장 없이 실패.
- junction 경로에서도 생성 자료가 `research_v2/project_identity.json`의 권혁찬 identity를 사용하도록 수정하고 회귀검사 추가.
- release validator의 reference provenance 오탐을 좁은 파일 예외로 수정; 활성 자료 identity 검사는 유지.
- P0-P1 순차 회귀검사: Python 13개, Node 33개, TypeScript, Next.js production build 통과.
- release preflight 실행; Gate 1 승인과 Gate 2 원시 검색 전이므로 12개 미완료 조건을 그대로 실패 처리.
- 실행패키지 task graph의 여형준 프로젝트명·반대 Gate 0 문구를 권혁찬 기준으로 교정하고 실제 P0-P2 상태 반영.
- 독립 선별·추출·RoB·GRADE 사람 판정의 완전성을 검사하는 fail-closed validator와 빈 입력 실패 보고서 생성.
- held-out 추출 평가기와 독립 시나리오·전문가 내용타당도 지표 계산기 구현; CI, critical FN, provenance, I-CVI/S-CVI 포함.
- 추출 지표 계산의 문자열 truthy 합산 오류를 X-06으로 기록하고 boolean 변환·회귀검사로 수정.
- 권혁찬 K1-K5만 허용하도록 rule schema를 교정하고, 두 검토자·근거·source quote를 강제하는 released-only compiler 구현.
- evidence freeze 선행조건·해시 검사와 동결 뒤에만 작동하는 metrics manifest 생성기 구현.
- 현재 빈 입력에 evidence freeze preflight를 실행해 17개 결손을 `not_frozen`으로 보존.
- `REPRODUCE.md`에 Gate 순서와 재현 명령 기록.
- 기존 권혁찬 DOCX 구조와 대응 PDF 21쪽을 검사해 서식 참조 계약 작성; legacy 본문·수치는 사용 금지.
- 최신 공식 졸업논문 서식 확인을 H-008로 추가. DOCX renderer의 LibreOffice 부재는 최종 Gate 9 전 해결 대상으로 기록.
- H-001/H-002/H-003/H-004/H-005/H-008 통합 입력 XLSX 생성; 7개 시트 전부 렌더 검사하고 빈 프로토콜 완료 수식 오판을 수정.
- 사람 입력 패킷 SHA, NCBI 환경변수, repo 상태, 대상 Drive 공식 서식 후보를 재검사했으나 새 입력 없음. 차단 상태를 `audit/blocked_state_20260710.json`에 보존.
- 사용자 지시에 따라 차단을 해소하기 위해 AMEND-001 채택: PubMed-only 단일검토자 근거지도·소프트웨어 실행가능성 연구로 주장 수준을 공식 축소.

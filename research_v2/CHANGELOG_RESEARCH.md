# Research changelog

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

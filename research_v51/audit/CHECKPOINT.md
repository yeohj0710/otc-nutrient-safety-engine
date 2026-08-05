# v5.1 완료 체크포인트

마지막 갱신 시각은 2026-08-01 12:45 KST다.

작업 브랜치는 `codex/v5.1-safety-expansion`이다. v5.0 고정 기준 commit은
`6dbdad518e2fa7b2ed7b9a8048e0c47dba5b6ae9`이고, 마지막 구현 commit은
`a62d3bd`이다. 목표 문서는 이 구현 commit 뒤의 마지막
로컬 문서 commit에 담는다. push, PR, production 배포와 공개 게시는 하지 않았다.

## 고정한 결과

- 제품 13개, released 규칙 15개, 허가 사용·복용 조건 32개를 유지했다.
- 과거 지원 유형 표기 26건을 제품별 직접 released 규칙 연결 13건과 ADMIN 유래 유형 연결
  13건으로 분해했다.
- 허가문구 후보–규칙 연결 360건을 고유 원문 위치 328곳으로 정리했다. 기존 약사 검토 운영
  근거 15건만
  `verified_primary`로 유지했다.
- 비활성 후보 345건은 `needs_expert_review` 33건, `provisional` 308건, `rejected` 4건이다.
  새로 활성화한 규칙이나 후보는 없다.
- 전문가 패킷 33건의 사람 검토 필드는 모두 비어 있고, 모든 항목에 필수 회귀 테스트가 있다.
- 후보–규칙 연결 360건 중 355건은 보관 식약처 변경 이력의 문서 개정일을 기록했다. 나머지
  5건은 개정일이 공개되지 않았다는 상태와 사유를 기록했다.
- 전문가 패킷 33건은 제품·성분, 문서 유형·개정일·UTC 접근일, 완결 공식 원문과 위치,
  정상·경계·비대상·오탐 방지 회귀 시나리오를 모두 포함한다.
- v5.0 문헌 링크 20건은 직접 일치 1건, 범위 일치 시 직접 4건, 배경 5건, UI 제외 10건으로
  구분했다. 어떤 문헌도 규칙을 release하지 않는다.
- 직접 안전 규칙이 없는 제품 10개 중 9개는 용량만, 1개는 용량·간격만 확인한다. 나머지
  3개는 제한된 공개 안전성 규칙도 지원한다.
- 미완성 1회 사용량이나 하루 횟수는 0으로 계산하지 않는다. 성공 카드와 0건 요약도 숨긴다.
- `releaseReady=false`를 유지한다.

## 보호 경계와 게시 정책

- 보호된 `research_v3` 입력은 고정 기준 commit의 Git blob 바이트로 파싱하고 해시한다.
  현재 브랜치의 `research_v3` 변경은 0건이다.
- `.gitattributes`는 SHA 매니페스트 입력과 결정론적 생성 파일의 커밋된 원본 바이트
  (LF·CRLF 혼합 포함)를 줄바꿈 변환 없이 보존한다. `core.autocrlf=true` worktree와
  `false` clone의 경계·최종 감사 결과와 해시가 같았고, LF clone의 관련 집중 검증은
  `118 passed, 1 skipped`였다.
- 경계 감사는 `valid=true`, `verification_complete=true`, 외부 제출 논문 2/2, 오류·경고
  0건이다.
- 최종 감사의 portable 모드는 `final_local_report_ready=false`, `--require-external` 모드는
  외부 정본 2/2를 확인한 뒤 `true`다. 두 모드는 같은 산출물 바이트를 계산한다.
- 최종 감사는 제품 행렬, 규칙 행렬, `final_metrics.json` 순서로 게시한다. 게시가 시작된 뒤
  실패하면 동시 writer의 파일을 덮어쓰지 않도록 자동 rollback이나 `unlink`를 하지 않고,
  partial-publication 오류와 보존된 staged 경로를 반환한다.
- 외부 정본은 같은 열린 핸들의 전후 `fstat`, 바이트, Windows 파일 identity와 경로를 다시
  확인한다. G 드라이브의 `st_nlink=0`은 볼륨이 hardlink를 지원하지 않음을 확인한 뒤에만
  허용한다.
- 독립 공격 재검토는 입력·출력 inode 교체, 같은 inode 쓰기, 게시 뒤 쓰기와 staged 경로
  재사용을 주입했다. 집중 회귀 8건과 독립 공격 회귀 9건이 통과했고 최종 판정은
  `Ready: yes`였다.

## 정본 수치와 해시

- 고유 원문 위치(evidence units): 328
- 허가문구 후보–규칙 연결(evidence links): 360
- review queue와 triage: 33/33
- expert packet: 33
- source freshness: 문서 20/20, 후보–규칙 연결 원문 360/360, 운영 근거 15/15, drift 0,
  unreachable 0
- baseline manifest: `35d9cc747a45b2027b29b4da250c8ecd159bae28def43e6562180859e5c0148d`
- evidence inventory: `237b55583b2b966ff174174d5a9e699f18125fd621761657114c3432fd5a9386`
- literature audit: `39e0454392bdb5a086f8150994d448f8264bd990ee2fa1bb770053b15d475863`
- review packet audit: `db6cf4e4a7a6ba3f9bcfe9392d96b987845a116027d59f60a3f2d051da4a3cc5`
- source freshness snapshot: `b595d09757393e1b650f5389ce85ec65f4d83004f8629617ff5ee9b29518f69c`
- final metrics: `72a00c9ac260f50d44cac0a8ae3893d94e5fa8d7724b626492f9e90332849121`
- product support matrix: `192df980c856339b1ee20248c96fe2315c2e37007ebca36adf0ab1a733929230`
- active rule matrix: `a18719361b9f9a3baa70058c5b246cdf76552df1f3b0376ea282110b9bfb20f1`
- expert queue: `dad992b216f3967dfd5c007b119e434222012962bb78b43a1fd64f0101711bb1`
- expert packet: `b613689cae311a21eeacdee250a2a1480815030c12662705e160e399e689ab24`

## 깨끗한 checkout 검증

- Python 3.12.13, pytest 9.1.1: `tests/research`는 `406 passed, 2 skipped`,
  `tests/research_v2`는 `45 passed`, `tests/test_search_pipeline.py`는 `6 passed`로
  전체 `457 passed, 2 skipped`.
- Python 잠금 의존성 52/52가 `requirements-research.lock`과 일치했고 `pip check`가 통과했다.
- `core.autocrlf=false` 별도 clone의 개정일·전문가 패킷·최종 감사 집중 검증은
  `118 passed, 1 skipped`였다.
- Vitest: 18 files, 269 tests 통과.
- TypeScript `tsc --noEmit` 통과. ESLint는 오류 0건, `etc/`의 QA helper 경고 4건이었다.
- Next.js 16.2.1 production build 통과, 정적 페이지 157개 생성.
- portable·external 최종 감사 `--check`가 모두 통과했고 작업 트리는 검증 뒤 깨끗했다.
- 깨끗한 production 브라우저 QA에서 데스크톱 1440×1000, 모바일 390×844, 대표 판정,
  coverage gap, 미완성 복용량, 입력값별 지원 배지, 혼합 결과의 문헌 부재 표시와 키보드 실행이
  통과했다. 콘솔 오류는 0건이었다.

## 공개 전 남은 사람 결정과 별도 위험

- 약사 또는 의학 전문가가 패킷 33건을 실제로 채택·수정·기각해야 한다.
- 사람 대상 사용성, 임상 민감도·특이도와 실제 복약 안전 결과는 검증하지 않았다.
- `npm audit --omit=dev`는 Next.js 16.2.1 계보의 high 등급 취약 패키지 3개(`next`,
  `postcss`, `sharp`)를 보고했다. 직접 의존성은 `next`다. 현재 목표는 배포하지 않았고,
  의존성 갱신은 연구 결과 변경과 분리해 Next.js 16.2.12 이상으로 검증해야 한다.
- `release_ready=false`와 연구용 시제품 고지를 유지한다.

재현 순서는 저장소 루트의 `REPRODUCE.md`, 브라우저 상세 결과는 `BROWSER_QA.md`, 독립 결함
기록은 `CODE_REVIEW.md`, 전체 결론은 `research_v51/reports/FINAL_REPORT.md`를 따른다.

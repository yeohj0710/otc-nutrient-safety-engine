# NIH ODS 접근 상태

2026-07-13 기준 공식 NIH ODS Health Professional fact sheet 6개 URL은 존재하고 공식 목록과 검색 색인에서 확인된다. 자동 HTTP 수집은 모두 403을 반환했다. 실제 브라우저와 Health Professional PDF 직접 주소도 Cloudflare 사람 확인 화면에서 멈췄다.

대체 보존으로 다음은 확보했다.

- 공식 URL별 본문 Markdown 파생 사본 6건
- 제목·원 URL·목차·Health Professional 표지 검증 6/6
- 파일 크기와 SHA-256 manifest

그래도 다음을 하지 않는다.

- 파생 텍스트 사본을 NIH 직접 원본 HTML/PDF로 간주하지 않는다.
- 원본 SHA-256를 임의 생성하지 않는다.
- 페이지 locator를 검토 완료로 표시하지 않는다.
- NIH ODS를 근거로 규칙을 released로 승격하지 않는다.

직접 원본 보존 상태는 `derived_text_preserved_direct_original_pending`이다. 직접 원본이 필요하면 일반 브라우저에서 공식 HTML/PDF를 저장한 뒤 파일 해시, 문서 갱신일, 관련 절·표 locator를 기록해야 한다.

상세 브라우저·HTTP 증거: `../audit/ods_access_audit_20260713.json`

파생 텍스트 manifest: `ods_web_text_manifest_20260713.json`

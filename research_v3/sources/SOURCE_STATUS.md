# 공식 기준자료 수집 상태

수집일: 2026-07-13

## 성공

- EFSA UL summary PDF: HTTP 200, 원본과 SHA-256 보존.
- 한국영양학회 2025 KDRI 개정 보도자료: HTTP 200, HTML과 SHA-256 보존.
- 한국영양학회·보건복지부 2025 KDRI 정오표 적용 f4 ZIP: HTTP 200, 44,386,649 bytes. 3권·국문/영문 요약본·3차 정오표를 추출하고 각 파일 SHA-256를 보존.
- 국가법령정보센터의 현행 「건강기능식품의 기준 및 규격」: HTTP 200, HTML과 SHA-256 보존.

## 직접 원본 수집 실패와 대체 보존

NIH ODS 6개 health professional fact sheet는 서버가 자동 다운로드 요청에 HTTP 403을 반환했고 자동 브라우저도 Cloudflare 확인 화면에서 멈췄다. 대신 `r.jina.ai` 읽기 전용 텍스트 프록시로 공식 URL의 본문 Markdown 사본 6건을 보존했다. 제목·원 URL·목차·Health Professional 표지를 검사했고 SHA-256는 `ods_web_text_manifest_20260713.json`에 기록했다.

이 사본은 본문 확인과 locator 탐색을 돕는 파생 텍스트다. NIH가 직접 제공한 HTML/PDF 원본으로 간주하지 않으며, 기존 `fetch_manifest_20260713.json`의 직접 수집 성공 수 6/12도 변경하지 않는다.

## 사용 경계

`normative_candidates.csv`는 단일 에이전트가 EFSA 요약표에서 옮긴 검토 후보일 뿐 released 규칙이 아니다. 특히 다음을 구분한다.

- 철 40 mg/day: UL이 아니라 safe level.
- 마그네슘 250 mg/day: 자연식품 마그네슘을 제외한 특정 보충·첨가 형태 범위.
- 비타민 B6 12 mg/day: 요약표 표시값이며 2023 개별 opinion과 대조 필요.
- 수치는 국가·연령·임신·수유·치료 감독 여부에 따라 직접 전용하면 안 된다.

2025 KDRI 후보는 정오표 적용 공식 책자의 요약표를 PDF 페이지 단위로 확인했다. 그래도 약사·지도교수의 규칙 적용 검토 전에는 released로 승격하지 않는다.

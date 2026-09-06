<!-- BEGIN:nextjs-agent-rules -->
# Next.js 작업 안내
프레임워크 코드를 바꾸기 전에 `node_modules/next/dist/docs/`의 해당 문서를 읽는다.
<!-- END:nextjs-agent-rules -->

# 권혁찬 최종 연구

현재 논문·사이트의 자료는 사후 정정한 80,965행이다. `README.md`, `docs/version_map.md`, `research/final/manifest.json`을 읽고 시작한다. 과거 제출본의 버전 번호를 현재 정본으로 사용하지 않는다.

## 원자료와 평가

- 실행 루트: `C:/dev/evidence-recollect`; 연구 자료: `data/kwon/`.
- 채점 표본 2,505행, 표본 추출틀 76,899행. 표본·잠금·원래 판정은 보존한다.
- 지표는 AI 비교 기준을 이름에 명시한다. 임상 정답률로 표현하지 않는다. `independent_blinding`은 사람 맹검이므로 false다. AI 맹검은 별도 속성으로 기록한다.
- 판정 이유 감사는 사후 검토다. 원래 맹검 평가를 수정하거나 독립 평가로 바꾸어 설명하지 않는다.
- 문헌을 대량으로 의미 검토할 때는 사용자 지정 모델 `gpt-5.6-luna`를 사용한다. 유료 API를 임의로 켜지 않는다.

## 유지할 경계

- 식약처 허가자료가 판정의 결정 근거다. PubMed 문헌 후보는 판정을 바꾸지 못한다.
- released 규칙 15개와 허가 복용 조건 32개를 구분한다. 새 규칙 활성화에는 명시적 승인과 출처·적용 범위·검사가 필요하다.
- `research_v3/logs/v50_run_report.json`, `v50_scoring_report.json`, 봉인 문헌 연결, 사람 검토 기록을 변경하지 않는다.
- `research_v2/`, `research_v3/`, `research_v51/`의 경로를 무작정 정리하지 않는다. 현재 prepare:knowledge 및 런타임 생성기가 읽는다.
- 문헌 후보 수와 표시 수를 구분한다. 규칙당 400편 제한은 표시 제한이며 전체 후보를 제한하지 않는다.
- excluded 제품과 비활성 후보를 되살리지 않는다. 새 후보를 기존 승인 근거처럼 표시하지 않는다.
- 상담 설명의 추가 선별 후보(`research/counseling/curated-candidates.json` → `src/generated/otc-counseling-candidates.json`)는 에이전트가 초록을 읽고 고른 자료다. 화면과 상담문에서 항상 "추가 선별 후보"로 표시하고, v5.0 검토 문헌의 uiPolicy와 봉인 연결, 허가 판정을 바꾸지 않는다. 후보를 고치면 `python scripts/build-counseling-candidates.py`로 다시 만들며, 검사가 인용문을 저장 초록과 대조한다.

- `release_ready=false`를 유지한다. 공개 사이트 배포는 연구자의 명시적 요청 후 실시한다.
- `tools/search_pipeline/embase_adapter.py`는 미실행된 후속 검색용 코드다. 제2 데이터베이스 검색을 완료한 것으로 보고하지 않는다.
- `.gitattributes`의 연구 자료 줄바꿈 규칙과 `.vercelignore`의 대용량 원자료 제외를 유지한다.
- 과거 기록 전체는 이번 정리 이전 `etc/remediation/backups/AGENTS.md`에서 확인할 수 있다. 현재 실행 지시로 해석하지 않는다.

## 검증

변경 범위에 맞는 회귀검사를 실행한다. 사이트 변경 뒤에는 `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`를 완료한다. 연구 자료는 `npm run validate:research`로 검증한다.

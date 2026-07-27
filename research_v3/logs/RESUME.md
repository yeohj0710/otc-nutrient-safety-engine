# v4.0 실행 재개 기록

최종 갱신: 2026-07-27 (Claude Code 인수 세션)

## 인수 배경

이전 실행의 P2는 소형 로컬 모델 판정이었고 품질 미달로 **전량 폐기**했다
(`research_v3/otc/literature/screening_discarded_local3b/`, D-020).
현재 P2는 에이전트가 직접 판정하는 방식(`screener=agent_direct`)으로 처음부터 다시 수행 중이다.
로컬 언어모델·외부 LLM API·서브에이전트를 사용하지 않는다.

## 완료

- P0: 사람 산출물 보존 커밋, `v3-otc-frozen` 태그, 24개 파일 동결 매니페스트, AM-OTC-001 기록.
- P1: AI PICOS 5개, PubMed 실검색 5,742건, 중복 제거 후 5,724개 PMID, 원시 XML·메타데이터·SHA-256 저장.
- P2-0: 로컬 3B 산출물·실행 스크립트 격리. 해당 스크립트 전용 테스트 제거.
  연구 테스트 기준선 143 passed.
- P2-1: 판정 프롬프트 확정 `research_v3/otc/literature/prompts/agent_screening_prompt.md`
  SHA-256 `58186692d7cd2241b4342578babe6d87615f762bafbcda2445d20f96330c3a60`. 실행 중 변경 금지.
- P2-2: 5,724행 → 50행 단위 115개 배치 (`screening/batches/`).
- P2-3: AGT-B0001 ~ AGT-B0010 (500행) 판정·적재 완료.

## 진행 중

P2-3 나머지 배치 판정.

## 재개 절차

```powershell
.\.venv-research\Scripts\python.exe -X utf8 tools\agent_screening.py coverage
```

남은 배치를 확인한 뒤 다음을 반복한다.

1. `research_v3/otc/literature/screening/cards/AGT-Bxxxx.txt` 를 읽는다
2. 판정을 `research_v3/otc/literature/screening/agent_decisions/AGT-Bxxxx.jsonl` 에 쓴다
3. `tools\agent_screening.py ingest AGT-Bxxxx ...` 로 스키마·중복·누락을 검증하며 적재한다
4. 배치 10개마다 커밋한다

카드 파일은 재생성 가능하므로 git에서 제외한다:
`tools\agent_screening.py render AGT-B0001 ...`

## 미실행

- P2-4 매니페스트 확정 (`coverage=1.0`, `run_complete=true`)
- P3-A AI 참조표준, P3-B 규칙엔진 AI 맹검 독립평가, P3-C 상태 갱신
- P4 문장 locator 근거 연결, UI 변경, 전체 테스트·빌드
- P5 논문·문서·발표원고·Notion 원고 재생성, Google Drive 동기화, 최종 보고서

## 보존 (이전 실행 산출물, 최종본 아님)

`research_v3/logs/v40_run_report.json`, `research_v3/thesis/*`, `research_v3/reports/*`는
300/5,724 부분 상태 시점의 산출물이다. P5에서 전부 재생성한다.

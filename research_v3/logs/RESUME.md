# v4.0 실행 재개 기록

최종 갱신: 2026-07-27 08:31 +09:00

## 완료

- P0: 사람 산출물 보존 커밋, `v3-otc-frozen` 태그, 24개 파일 동결 매니페스트, AM-OTC-001 기록.
- P1: AI PICOS 5개, PubMed 실검색 5,742건, 중복 제거 후 5,724개 PMID, 원시 XML·메타데이터·SHA-256 저장.

## 부분 완료

- P2: 로컬 `Qwen/Qwen2.5-3B-Instruct`로 10개 배치 1,000행을 판정했다. 전체 5,724행 중 4,724행이 남았다.
- 프롬프트는 고정됐고 체크포인트는 append-only다. 완료된 판정은 수정하지 않는다.
- 사용자가 시간 제한 축소를 해제했으므로 P2 100% 완료까지 계속한다.
- 32행 마이크로배치, 입력 1,280토큰, 출력 20토큰 설정은 새 700행에서 안정적으로 동작했다.

## 미실행

- P3 AI 참조표준과 규칙엔진 맹검 독립평가.
- P4 문장 locator 근거 연결, UI 변경, 전체 테스트·빌드.

## 종료 산출물

- `research_v3/logs/v40_run_report.json`: `research_complete=false`와 차단 사유를 포함한 최종 보고서.
- `research_v3/thesis/권혁찬_졸업논문_최종본.docx`와 `.pdf`: 현재 부분 상태를 반영한 A4 7쪽 문서.
- `research_v3/reports/발표원고_v4.0.md`, `notion_update.md`: 발표·Notion 갱신 원고.
- Google Drive 대상 파일 10개를 복사했으며 원본·복사본을 확인했다.
- 지정 Notion 페이지의 현재 상태 절을 갱신하고 하위 페이지 4개가 유지되는지 확인했다.

## 재개 명령

```powershell
.\.venv-research\Scripts\python.exe -X utf8 tools\screen_v40_literature_local.py --max-batches 10 --micro-batch-size 32
```

10개 배치마다 체크포인트와 매니페스트를 검증한 뒤 커밋한다. P2 `coverage=1.0`과 `run_complete=true` 전에는 P3를 시작하지 않는다.

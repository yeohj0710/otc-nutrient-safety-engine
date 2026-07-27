# RESUME

## 현재 상태

v4.0 전 단계 완료. 최종 완료 감사 12개 검사 전부 통과.

- P2 문헌 선별: 5,724행, 커버리지 1.0, 사람 판정 0건
- P3-A AI 참조표준: 층화 표본 300건, AI 참조표준 대비 F1 0.8484
- P3-B 규칙엔진 맹검평가: 사례 237건, 채점 210건,
  AI 참조표준 대비 특이도 1.0000 / 민감도 0.5702
- P3-C 상태 갱신: complete=true,
  independent_blinding_ai=true,
  independent_blinding=false,
  release_ready=false
- P4 문헌 근거: 규칙 16/16개 연결,
  링크 20건, 보존한 충돌 4건
- P5 문서·동기화: 논문 10쪽, Drive 13개 파일 SHA-256 일치, Notion 갱신 확인
- 검증: 연구 시험 192 · 앱 시험 70 · 정적 경로 156
- 배포: not_run (배포 금지 유지)

## 성능 수치를 인용할 때

모든 지표는 **AI 참조표준 대비** 값이다. 사람 참조표준이 아니고 절대적 진실 대비 정확도가 아니다.
분류기와 참조표준을 같은 에이전트가 수행했으므로 평가자 독립성이 부분적이다.

## 남은 선택 항목

- 사람 블라인드 독립평가 (필수 아님, `research_v3/HUMAN_ACTION_REQUIRED.md` 1번)
- 복용 조건 32개 약사 재검토 (필수 아님)
- 규칙 바인딩 커버리지 공백 49건 — 허가원문에 이미 있는 주의를
  규칙 바인딩으로 넓히는 작업. `ai_independent_evaluation.json` 의 `coverage_gap_analysis` 참조
- 자료원 확장 (PubMed 단일 자료원)

## 다시 확인하는 방법

```powershell
.\.venv-research\Scripts\python.exe -m tools.audit_v40_closure
```

마지막 감사: all_passed=true, 검사 12개

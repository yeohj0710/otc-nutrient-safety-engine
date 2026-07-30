# v5.0 선별 채점 arm 재현 절차

## 실행 순서

저장소 루트에서 다음 순서로 실행한다.

```powershell
python tools/v50_scoring/sample_and_build_cards.py
python tools/v50_scoring/scoring_harness.py start
python tools/v50_scoring/scoring_harness.py cards
# rounds/의 카드만 보고 judgments/에 판정을 작성한다.
python tools/v50_scoring/scoring_harness.py validate
python tools/v50_scoring/scoring_harness.py lock
# lock이 성공한 뒤에만 다음 명령으로 봉인 정답을 연다.
python tools/v50_scoring/compare_and_report.py
```

`sample_and_build_cards.py`를 다시 실행하면 준비 산출물이 바뀔 수 있다. 완료된 arm을 재현할 때는 먼저 현재 잠금 파일과 영수증을 별도 보존해야 한다.

## 잠금 전 확인 사항

- 카드 894건을 모두 판정했는가.
- 카드에 허용된 여섯 필드 외의 키가 없는가.
- 초록 없는 행에 `confidence=low`, `evidence_basis=title_only`, `insufficient_abstract`가 모두 있는가.
- `scoring_execution_receipt.json`에 실행자, 모델 표기, 시작 시각이 있는가.
- 봉인 정답을 열지 않았는가.

하네스는 이 조건을 검사한 뒤 `scored_labels_locked.json`과 `lock_receipt.json`을 만든다. 잠금 영수증은 잠금 UTC 시각, SHA-256, `truth_opened_before_lock=false`를 기록한다.

## 비교 결과의 범위

비교 스크립트는 전체, classifier층, adjudicated층을 나눠 설계가중 지표를 계산한다. 층화 부트스트랩은 확률표본층 안에서만 다시 뽑고 전수층을 고정한다. `v50_SCORING_FINAL.md`는 표본층 합계, 잠금 정보, 세 갈래 지표, 불일치 방향, 질문별 일치율과 미재판정 retain 6,682건의 해석 범위를 담는다.

이 arm에는 사람 참조 행이 없다. 결과는 사람 판단이나 임상적 결론을 대신하지 않으며 `release_ready=false`를 바꾸지 않는다.

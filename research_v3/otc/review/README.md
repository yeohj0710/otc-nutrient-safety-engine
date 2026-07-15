# OTC 통합 사람 검토 절차

`OTC_통합검토.html`은 동일한 화면을 역할별로 나누어 사용한다. 한 파일에서 여러 역할을 동시에 주장하지 않는다.

1. 약사·약학 전문가는 `pharmacist_expert`로 규칙의 공식 근거, 문구와 runtime binding을 검토한다.
2. 독립 시나리오 검토자는 시스템 예측을 보지 않은 상태에서 `independent_scenario_reviewer`로 기준정답을 확정한다.
3. 연구 지도자는 필요할 때 `research_advisor`로 공식 지정 후보의 포함·보류·제외를 검토한다.
4. 성분 정규화 검토자는 `normalization_reviewer`로 고유 성분 31개의 원문명과 시스템 표준명을 독립적으로 확인한다. 수정이 필요하면 메모에 기준 표준명을 입력한다.
5. 각 검토자는 결과를 JSON으로 저장한다.
6. 결과는 다음 명령으로 가져온다.

```powershell
.\.venv-research\Scripts\python.exe scripts\research\otc\import_review_result.py <검토결과.json>
```

Importer는 역할과 대상 ID를 검증하고 기존 기록과 병합한다. 전문가가 규칙을 승인해도 `rules.csv`를 자동 수정하거나 규칙을 `released`로 승격하지 않는다. 독립 기준정답을 가져올 때도 시스템 예측은 비워 두며 상태만 `human_label_locked_awaiting_prediction`으로 변경한다.
이미 잠긴 독립 기준정답은 뒤의 검토 결과로 변경할 수 없다.
성분 정규화 기준표도 한 번 잠긴 항목은 다른 결과로 덮어쓸 수 없다. 사람 기준표 31건이 완료되기 전에는 성분 정규화 정확도를 보고하지 않는다.

약사 승인 결과를 가져온 뒤에도 먼저 읽기 전용 승격 점검을 실행한다.

```powershell
.\.venv-research\Scripts\python.exe scripts\research\otc\promote_reviewed_rules.py
```

점검기는 약사의 `approve`, 규칙과 권고 1차 근거의 source/locator 일치, 실행에 필요한 runtime binding 존재를 모두 확인한다. 기본 실행은 파일을 변경하지 않는다. 실제 승격은 점검 결과를 확인한 뒤 `--apply`를 명시해야 하며, 원본 CSV는 `research_v3/otc/etc/promotion_backups/`에 백업된다. 긴급증상 규칙에는 품목별 증상어 binding이 마련되어 있다. 장기복용 규칙은 판콜에이 허가문구가 “장기간 계속 복용하지 말 것”이라고만 규정하고 정량 일수를 제시하지 않으므로, 임의의 최대 일수를 만들지 않았다. 따라서 별도의 정량 근거와 구조화 binding이 확정되기 전에는 문구를 승인해도 승격되지 않는다.

전체 13건의 독립 기준정답이 먼저 잠긴 뒤, 전문가 검토와 별도 승격 절차를 거친 released 규칙이 있을 때만 다음 명령으로 예측을 생성한다.

```powershell
npx tsx scripts\research\otc\predict-independent.ts
```

실행기는 하나라도 사람 라벨이 없거나, released 규칙이 0개거나, 원본 사례 JSON에 기준정답·예측이 들어가 있으면 아무 파일도 수정하지 않고 종료한다. 예측은 `releasedRuleTypes`에 포함된 결정론적 규칙만 사용하며 runtime과 사례별 SHA-256을 `independent_prediction_audit.json`에 기록한다.

현재 자동 생성 후보를 사람이 검토한 것으로 표시하거나, 구방향 영양성분 검토 결과를 OTC 검토로 가져오면 안 된다.

# 연구 재현 명령

현재 상태는 검색 실행 전 preflight다. 아래 명령은 사람 승인·기관 DB export·독립 판정 자료가 채워진 뒤 순서대로 실행한다. 실패한 관문을 건너뛰지 않는다.

```powershell
cd C:\dev\otc-nutrient-safety-engine
& .\.venv-research\Scripts\Activate.ps1
python -m pytest tests -q
npm.cmd run test
npm.cmd run typecheck
npm.cmd run build
python execution_package\scripts\check_project_identity.py --root .
python scripts\research\validate_human_adjudication.py research_v2 --out research_v2\audit\human_adjudication_readiness.json
python execution_package\scripts\generate_prisma_counts.py --records research_v2\search\normalized\records.csv --ta research_v2\screening\title_abstract.csv --ft research_v2\screening\full_text.csv --retrieval research_v2\full_text\retrieval_log.csv --out research_v2\screening\prisma_counts.json
python execution_package\scripts\compute_ai_metrics.py research_v2\ai_eval\screening_predictions.csv --split-column split --split-value held_out --out research_v2\ai_eval\screening_metrics.json
python scripts\research\compute_extraction_metrics.py research_v2\ai_eval\extraction_gold_predictions.csv --split held_out --out research_v2\ai_eval\extraction_metrics.json
python scripts\research\build_evidence_map.py --extraction research_v2\extraction\extraction.csv --grade research_v2\synthesis\grade.csv --out research_v2\synthesis\evidence_map.csv
python scripts\research\select_focused_node.py research_v2\synthesis\focused_node_scores.csv --out research_v2\synthesis\focused_node_decision.json
python scripts\research\validation_metrics.py scenario research_v2\validation\scenarios.csv --out research_v2\validation\scenario_metrics.json
python scripts\research\validation_metrics.py content-validity research_v2\validation\expert_review.csv --out research_v2\validation\content_validity.json
python scripts\research\compile_rules.py --trace research_v2\rules\rule_trace.csv --quotes research_v2\extraction\source_quotes.csv --out research_v2\rules\rules.jsonl --report research_v2\audit\rule_compile_report.json
python scripts\research\freeze_evidence.py research_v2 --dataset-version VERSION --frozen-at UTC_TIMESTAMP
python scripts\research\build_metrics_manifest.py research_v2
python execution_package\scripts\validate_release.py research_v2 --out research_v2\audit\final_gate_report.json
```

`VERSION`과 `UTC_TIMESTAMP`는 승인된 evidence freeze 값으로 대체한다. `NCBI_EMAIL`과 기관 인증정보는 git에 저장하지 않는다.

# research_v3 OTC 재현 명령

모든 명령은 `C:\dev\otc-nutrient-safety-engine`에서 PowerShell로 실행한다.

## 1. 제품 마스터와 런타임 재생성

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/build_nedrug_masters.py
.venv-research\Scripts\python.exe scripts/research/otc/build_runtime.py
```

첫 명령은 후보 16개를 보존하고 분석 포함 13개와 신신파스아렉스 제외 로그를 생성한다. 두 번째 명령은 분석 제품만 사이트 런타임으로 만든다.

## 2. 사이트-연구 정합성 감사

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/audit_runtime_alignment.py
```

13개 제품, 28개 고유 성분, 47개 제품-성분 연결, 32개 복용 조건, 액상제 단위 환산과 제외 제품 유입을 검사한다.

## 2-1. 비공개 판매 SKU 후보 연결

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/catalog_candidate_bridge.py --catalog-root C:\dev\pharmacy-product-catalog
```

이 명령은 외부 저장소의 `products.json`, `catalog.csv`와 `enrichment-queue.json`을 제자리에서 읽는다. 전체 원본과 가격은 복사하지 않는다. 결과는 정확 이름 교집합, fuzzy 검토 큐와 추가 screening 후보로 분리하며 모든 행을 `promotion_allowed=false`로 기록한다.

재현 결과는 원본 776건, 중복 22그룹·46 SKU, 정확 이름 교집합 5 SKU·기존 분석 제품 4개, fuzzy 검토 2 SKU, 추가 screening 후보 99 SKU·97개 이름이다. 공공데이터 서비스 키가 없으면 `official_enrichment_status=blocked_missing_key`를 유지하고 제품 마스터와 런타임을 변경하지 않는다.

## 3. 규칙·독립 사례 검증

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/validate_rules.py
.venv-research\Scripts\python.exe scripts/research/otc/validate_independent_cases.py
```

외부 확인 13건은 비블라인드 자료다. 검증 명령을 실행해도 `performance_claim_allowed=false`와 독립평가 미완료 상태는 바뀌지 않는다.

## 4. 전체 테스트와 빌드

```powershell
.venv-research\Scripts\python.exe -m pytest tests/research -q
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

## 5. 지표와 완료 감사

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/build_metrics.py
.venv-research\Scripts\python.exe scripts/research/otc/audit_completion.py
```

블라인드 독립평가가 없으면 완료 감사의 유일한 미완료 조건은 `independent_evaluation_complete`여야 한다.

## 6. 논문·연구계획서 생성

```powershell
.venv-research\Scripts\python.exe scripts/research/otc/build_thesis_docx.py --markdown research_v3/thesis/otc_thesis_working.md --output research_v3/thesis/권혁찬_졸업논문_최종본.docx --document-label 졸업논문
.venv-research\Scripts\python.exe scripts/research/otc/build_thesis_docx.py --markdown research_v3/protocol/otc_research_plan_working.md --output research_v3/protocol/권혁찬_OTC_연구계획서_최종본.docx --document-label 연구계획서
.venv-research\Scripts\python.exe scripts/research/otc/render_docx_windows.py research_v3/thesis/권혁찬_졸업논문_최종본.docx research_v3/thesis/권혁찬_졸업논문_최종본.pdf
.venv-research\Scripts\python.exe scripts/research/otc/render_docx_windows.py research_v3/protocol/권혁찬_OTC_연구계획서_최종본.docx research_v3/protocol/권혁찬_OTC_연구계획서_최종본.pdf
```

PDF 전 페이지를 PNG로 렌더링해 한글, 표, 페이지 번호, 참고문헌과 연구자 정보를 확인한다.

## 해석 경계

- 후보 마스터 16·31·106과 분석·사이트 집합 13·28·47을 혼용하지 않는다.
- 제품명·함량은 식약처 허가 원문과 locator를 기준으로 한다.
- 제품별 복용 조건 32개는 허가 원문 검증 상태이며 별도 약사 재검토 완료가 아니다.
- 비블라인드 외부 확인을 블라인드 독립평가로 바꾸지 않는다.
- 비공개 판매 SKU 후보를 식약처 허가 제품이나 판매량 순위로 바꾸지 않는다.
- 카탈로그 가격과 전체 원본 JSON·CSV를 Git, 사이트와 논문 부록으로 복사하지 않는다.
- `complete=false`, `release_ready=false`, `performance_claim_allowed=false`를 유지한다.

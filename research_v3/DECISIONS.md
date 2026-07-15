# research_v3 결정 기록

## D-001 (superseded)

2026-06-18 기준 계획서와 2026-06-01·06-04 초기본이 모두 고함량 영양성분 연구를 명시하므로 이 방향을 유지한다는 이전 결정을 보존한다. 최신 사용자 결정으로 이 결정은 더 이상 활성 연구 범위를 정하지 않는다.

## D-002 (superseded)

국내 다빈도 일반의약품 제품 연구와 원문 계획서의 충돌 및 2026년 7월 13일 전자 승인 기록을 근거로 영양성분 방향을 유지했던 결정을 보존한다. 최신 사용자 결정은 이 승인 기록을 새 OTC 연구의 승인·검토·성과로 재사용하지 않도록 명시하므로 활성 효력이 없다.

## D-003

research_v2의 110개 규칙은 legacy 탐색 자료다. source·locator·사람 원문 검토를 충족하지 않은 규칙은 v3 released로 승격하지 않는다.

## D-004

기준 계획서의 학번 공란과 서명 부재는 원문 상태로 기록한다. 별도 전자 승인 결과와 SHA-256를 `research_v3/approvals`에 보존하며 이를 방향·신원·주장 수준·최종본 승격의 승인 증거로 사용한다.

## D-005

2026-07-14 최신 사용자 결정에 따라 활성 연구 방향을 `korean_otc_product_safety`로 전환한다. 연구 질문은 국내 대표 일반의약품의 제품·성분·함량·복용 조건을 구조화하고, 제품명 기준 중복 성분·동일 약리군·최대용량·복용 간격·연령·질환·병용약 위험을 source/locator와 함께 조회하는 시스템의 개발과 평가다.

## D-006

기존 영양성분 자료는 삭제하거나 새 OTC 성과에 합산하지 않는다. 기존 위치를 유지하면서 `direction_status=superseded`, `reason=actual frequent OTC research direction confirmed by user`로 분리한다. 검색·중복 제거·계보·source/locator·범용 엔진·테스트·공통 UI·문서 검증 코드만 감사 후 재사용할 수 있다.

## D-007

새 OTC 연구에서 사람이 수행하지 않은 전문 판정과 승인을 완료로 기록하지 않는다. 기존 승인 마법사, PRESS 35건, 문헌 118/63건, 근거 326건, 규칙 6건, 시나리오 12건과 성능값은 영양성분 구방향 결과다. 활성 OTC metrics의 초기값으로 사용하지 않는다.

## D-008 (superseded in part)

`release_ready=false`와 goal complete 금지는 유지한다. canonical 승격과 production 배포를 사용자 명시 승인 전 금지했던 부분은 후속 사용자 승인으로 대체되었다.

## D-009

2026-07-14 canonical 승격 승인과 실제 승격을 확인하였다. 이 승격은 블라인드 독립평가 완료를 뜻하지 않는다. 2026-07-15 사용자는 이후 변경을 Git에 push하고 production으로 배포하도록 명시적으로 승인하였다. 배포 승인은 `release_ready`, `complete` 또는 임상 성능 주장 허용으로 해석하지 않는다.

## D-010

신신파스아렉스는 4매 포장이 7×10㎠와 10×14㎠ 규격에 모두 허가되어 포장 수량만으로 단위당 함량을 하나로 결정할 수 없다. 원시 HTML·PDF, 제품 마스터, 성분 마스터와 49개 제품-성분-규격 행은 보존한다. 다만 `analysis_status=excluded`, `exclusion_reason=ambiguous_authorized_package_size`로 기록하고 분석 집합, 사이트 검색·계산 대상과 런타임 미지원 후보 목록에서 제외한다.

## D-011

연구 수치는 데이터 층별로 분리한다. 후보·허가 원문 마스터는 16개 제품, 31개 고유 성분, 106개 제품-성분-규격 행이다. 분석·사이트 집합은 13개 제품, 28개 고유 성분, 47개 계산용 제품-성분 연결이다. 두 층의 수치를 같은 의미의 “제품-성분 연결”로 혼용하지 않는다.

## D-012

2026-07-15 허가 용법·용량 PDF에서 제품별 복용 조건 32개를 구조화하였다. 모든 행은 source, locator와 SHA-256을 확인한 `verified_from_authorization_source` 상태다. 이 조건들은 2026-07-14 외부 약사 규칙 검토 이후 추가되었으므로 별도 약사 검토 완료라고 표시하지 않는다.

## D-013

13개 시나리오의 외부 확인 결과는 `codex_prefilled_external_human_confirmation`이다. 평가자가 Codex 예상 답안을 볼 수 있었으므로 `independent_blinding=false`, `performance_claim_allowed=false`, `independent_evaluation_complete=incomplete`, `complete=false`, `release_ready=false`를 유지한다.

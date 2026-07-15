# 국내 일반의약품 데이터 사전

## 계보 원칙

활성 OTC 데이터는 `research_v3/otc`에서 생성한다. 제품명, 함량과 허가 상태는 식품의약품안전처 허가 원문에 연결한다. 값이 없거나 규격을 하나로 결정할 수 없으면 추정값을 만들지 않고 제외 상태와 이유를 기록한다. 기존 영양성분 자료는 superseded 계보로 보존하며 활성 OTC 수치에 합산하지 않는다.

## 데이터 층

### 후보·허가 원문 마스터

공적 지정과 규칙 범위 후보를 포함한다. 16개 제품, 31개 고유 성분과 106개 제품-성분-규격 행이다. 허가 취하 제품과 신신파스아렉스 규격 행도 감사 계보를 위해 보존한다.

### 분석·사이트 집합

`analysis_status=included`이고 `selected_for_calculation=true`인 행만 계산에 사용한다. 현재 13개 제품, 28개 고유 성분과 47개 제품-성분 연결이다. 사이트 런타임과 논문의 주 분석 수치는 이 층을 사용한다.

## 주요 테이블

### `normalized/product_master.csv`

제품 한 개당 한 행이다. `product_id`는 내부 안정 식별자, `item_sequence`는 식약처 품목기준코드다. `record_status`는 허가 원문 확인 상태, `calculation_ready`는 계산 규격 식별 여부, `analysis_status`는 최종 분석 포함 여부다. 제외 제품은 `analysis_exclusion_reason`을 반드시 가진다.

### `normalized/ingredient_master.csv`

표준화 유효성분 한 개당 한 행이다. 한글·영문 표준명, 정규화 키와 약리군을 저장한다. 염·수화물·복합체를 근거 없이 합치지 않는다.

### `normalized/product_ingredient.csv`

제품, 성분과 허가 규격의 연결 행이다. `amount_per_unit`, `amount_unit`, `unit_basis`, `variant`를 함께 보존한다. `selected_for_calculation=true`인 47개 행만 사이트 계산 binding으로 사용한다. 따라서 전체 106개 행을 단순한 사이트 제품-성분 연결 수로 부르지 않는다.

### `normalized/analysis_exclusions.csv`

허가 원문은 보존하지만 분석·런타임에서 제외한 제품의 로그다. 제품 ID, 제외 단계, 이유, source, locator, 원본 해시와 원자료 보존 여부를 기록한다.

### `normalized/administration_constraints.csv`

제품별 용법·용량 수치다. 허용 유형은 `maximum_units_per_dose`, `maximum_doses_per_day`, `maximum_daily_ingredient_amount`, `minimum_interval_hours`다. 값, 단위, 도출 방법, source, locator, SHA-256과 검증 상태를 저장한다. 현재 32개 행은 `verified_from_authorization_source`이며 별도 약사 재검토 완료 상태가 아니다.

### `rules/rules.csv`

결정론적 안전성 규칙이다. `draft`, `released`, `retired`를 구분한다. `released` 규칙은 비어 있지 않은 `source_id`와 구체적인 `source_locator`가 있어야 한다. AI는 predicate, 기준값 또는 위험 판정을 생성하지 않는다.

### `validation/independent_scenarios.csv`

외부 확인 라벨과 엔진 예측의 index다. 실제 사례 payload JSON은 무라벨 상태로 분리한다. 현재 `review_method=codex_prefilled_external_human_confirmation`, `independent_blinding=false`이므로 성능 주장을 허용하지 않는다.

### `audit/runtime_research_alignment.json`

분석 집합과 사이트 런타임의 제품 ID, 성분 ID, 함량, 단위, 근거와 복용 조건을 비교한다. 13개 제품, 28개 성분, 47개 연결, 32개 복용 조건과 제외 제품 유입 여부를 검사한다.

## 비공개 판매 SKU 후보 층

`C:\dev\pharmacy-product-catalog`의 776개 판매 SKU는 국내 실제 판매 제품을 탐색하는 비공개 후보 모집단이다. Firestore 원본 확인은 판매 SKU 원문을 확인했다는 뜻이며, 일반의약품 허가·성분·용법을 확인했다는 뜻이 아니다. 가격과 전체 원본 JSON·CSV는 이 저장소로 복사하지 않는다.

### `selection/catalog_screening_policy.json`

카탈로그 카테고리를 `일반의약품 가능성 검토`, `카테고리상 비의약품으로 보아 승격 금지`, `공식 제품 영역 미확정`으로 나누는 screening 설정이다. 이 분류는 공식 품목 분류가 아니며 식약처 제품 영역 확인 전에는 연구 제품으로 사용하지 않는다. 제품명 끝의 제형 단서와 규격 단위가 함께 맞아야 추가 검토 후보가 된다.

### `selection/catalog_existing_product_intersection.csv`

카탈로그 정규화 제품명이 기존 분석 제품의 제품명·제형 제거 별칭과 정확히 같은 판매 SKU만 담는다. 현재 5개 SKU가 기존 식약처 제품 4개와 이름 수준에서 교차한다. 제조사와 공식 품목코드를 카탈로그 출처에서 확인하지 못했으므로 모든 행은 `requires_official_match_review`, `promotion_allowed=false`다.

### `selection/catalog_fuzzy_match_review.csv`

문자열 유사도 기준을 충족했지만 동일 제품으로 볼 수 없는 2개 SKU를 분리한다. 예를 들어 산제와 현탁액처럼 제형이 다른 이름 후보가 들어올 수 있으므로 교집합 수에 포함하지 않는다.

### `selection/catalog_additional_otc_candidates.csv`

일반의약품이 포함될 수 있는 카테고리, 제품명 끝 제형 단서와 규격 호환 조건을 모두 충족한 screening shortlist다. 현재 99개 SKU·97개 정규화 이름이 있으나 `candidate_requires_official_domain_and_item_match` 상태다. 식약처 제품 영역, `item_sequence`, 허가 상태, 성분, 용법·용량과 DUR를 확인하기 전에는 제품 마스터·런타임·논문 제품 수에 합산하지 않는다.

### `audit/catalog_candidate_bridge.json`

원본 776건, 중복 22그룹·46 SKU, JSON/CSV 동일성, 원본 해시, 가격 미복사, 전체 원본 미복사와 산출물 해시를 검증한다. `DATA_GO_KR_SERVICE_KEY`가 없어 공식 보강 상태는 `blocked_missing_key`이며 공식 제품·공식 매칭 수는 0이다.

## 수치 용어

- `product_ingredient_rows`: 후보 마스터의 제품-성분-규격 행 수
- `analysis_product_ingredient_variant_rows`: 분석 제품에 속한 전체 허가 규격 행 수
- `runtime_product_ingredient_bindings`: 계산에 선택된 사이트 제품-성분 연결 수
- `analysis_ingredients`: 사이트에 실제 포함된 고유 성분 수

## 금지된 결합

기존 영양성분 검색·근거·규칙·시나리오·승인·성능 수치를 활성 OTC 테이블이나 metrics에 합치지 않는다. 비블라인드 외부 확인 결과를 블라인드 독립평가 또는 임상 성능 근거로 바꾸지 않는다.

비공개 판매 SKU 후보 수, 가격, 카테고리 분류와 fuzzy 문자열 후보를 허가 검증 제품 수나 판매 순위로 바꾸어 쓰지 않는다. 공식 매칭이 없는 후보는 규칙 적용 대상이나 사이트 검색 대상으로 승격하지 않는다.

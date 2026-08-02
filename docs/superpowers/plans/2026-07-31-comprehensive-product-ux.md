# OTC Nutrient Safety Engine Comprehensive Product UX Plan

> 로컬 구현 계획이다. 봉인 연구 산출물은 수정하지 않으며 명시 요청 전에는 배포하지 않는다.

**목표:** 현재 연구가 실제로 연결한 제품·규칙·허가 원문·v5.0 문헌의 범위를 정확히 보여주면서, 약을 찾고 입력하고 결과를 해석하는 전 과정을 빠르고 깔끔하게 만든다.

**원칙:** 판정 엔진과 봉인 데이터는 유지한다. v5.0 최종 연결 문헌만 결과 화면에 표시하고, `ui_policy=exclude_from_result_ui`인 기각 문헌 10건은 결과 화면에서 제외한다. 현재 제품 원문과 대표 제품 원문은 표시 모델에서 분리한다.

## 1. 실패하는 계약 테스트부터 추가

**수정 파일**

- `__tests__/otc-evidence-ux.test.ts`
- `__tests__/otc-product-flow.test.ts`
- `__tests__/otc-layout-contract.test.ts`
- 필요 시 새 표시 모델 테스트

**계약**

- v5.0 최종 연결 문헌만 결과 화면에 표시되고 기각 문헌 10건은 노출되지 않는다.
- 현재 제품 허가 원문과 대표 제품 규칙 원문 수를 합치지 않는다.
- 중복 성분 그룹이 원본 성분별 계산값을 보존한다.
- 빈 복용량 입력을 즉시 0으로 바꾸지 않는다.
- 수동 수정 시 활성 데모 표시가 해제된다.
- 데모가 실제 엔진 결과, 문헌 상태, 원문 일치 상태를 함께 표시한다.
- 44px 터치 영역, safe-area, focus-visible, reduced-motion, 간격 토큰을 요구한다.

## 2. 근거와 결과 표시 모델을 바로잡는다

**수정 파일**

- `src/lib/otc/presentation.ts`
- 필요 시 `src/lib/otc/display-model.ts`
- 필요 시 `src/lib/otc/form-state.ts`

**구현**

- 설명 문헌은 `ui_policy`를 확인해 결과 화면 표시 가능 문헌만 남긴다.
- 현재 제품 직접 허가 원문, 대표 제품 규칙 원문, 제품·성분·계산 원문을 따로 집계한다.
- 그룹 결과에 원본 `members`를 보존해 성분별 계산량과 포함 제품을 보여준다.
- 허가 상한 derivation을 개인 적정용량과 구분하는 사용자 문구로 변환한다.

## 3. 검색·입력·데모 흐름을 개선한다

**수정 파일**

- `src/lib/otc/search.ts`
- 필요 시 `src/lib/otc/demos.ts`
- `src/components/otc-product-safety-client.tsx`
- 필요 시 제품 선택·프로필·결과·도움말 컴포넌트로 분리

**구현**

- 연구 대상 13개 제품만 점검 가능하다는 범위를 검색 앞에 둔다.
- 공백·괄호·기호를 정규화하고 제품명과 성분명으로 검색한다.
- 제품마다 연결 규칙, 복용 조건, 직접 연결 문헌 수를 선택 전에 표시한다.
- 일반 제품 추가 시 복용량을 비워 두고 사용자가 확인하기 전에는 용량 판정을 보류한다.
- 숫자 입력은 문자열 draft로 유지하고 평가 시 안전하게 파싱한다.
- 모든 수동 입력은 활성 데모를 해제한다.
- 데모는 중복 성분, 중복 계열, 허가 상한, 복용 간격, 질환·병용약, 연결된 신호 없음 사례로 구성하고 실제 출력 요약을 함께 표시한다.
- 동기 계산에 넣은 460ms 가짜 로딩을 제거한다.

## 4. 결과 정보 구조와 문구를 정리한다

**수정 파일**

- `src/components/otc-product-safety-client.tsx`
- `src/components/otc-product-safety.module.css`

**표시 순서**

1. 가장 중요한 경고와 지금 할 일
2. 현재 제품에 직접 연결된 허가 원문
3. 확인하지 못한 범위
4. 성분별 계산 상세
5. v5.0 최종 연결 PubMed 문헌
6. 대표 제품 규칙 원문과 연구 범위 설명

**문구**

- `v5.0 선별 확인` 문헌만 결과 문헌 수에 포함한다.
- 기각 문헌 10건은 직접 일치·배경 문헌 수와 결과 목록에 넣지 않는다.
- 현재 제품의 직접 원문이 없으면 대표 제품 원문임을 본문에 표시한다.
- 허가 상한이 개인 적정용량이 아님을 제품 카드와 결과에 표시한다.

## 5. 활성 연구 경계·접근성·간격을 정리한다

**수정 파일**

- `app/sitemap.ts`
- `app/manifest.ts`
- 구세대 `ingredients`·`rules` metadata
- `src/components/site-frame.tsx`
- `app/globals.css`
- `app/loading.tsx`
- `src/components/otc-product-safety.module.css`
- 필요한 보조 화면 컴포넌트와 표 CSS

**구현**

- 사이트맵은 활성 OTC 홈과 연구 화면으로 제한하고 구세대 화면은 `noindex`로 표시한다.
- 앱 이름을 현재 OTC 연구와 일치시킨다.
- 모든 공개 화면에 `#main-content`와 포커스 가능한 skip target을 둔다.
- 닫힌 커스텀 패널을 탭 순서와 접근성 트리에서도 제외한다.
- 1240px shell과 4/8 기반 spacing token을 적용한다.
- 임의의 7/9/10/11/13/14/17/18px 구조 간격을 8/12/16/24/32px 역할 값으로 정리한다.
- 기본 카드 패딩 16px, 큰 패널 24px, 섹션 간격 32~48px, 모바일 gutter 16px를 적용한다.
- 모든 컨트롤은 최소 44px, 보조 본문은 최소 12px, 본문은 14px 이상으로 맞춘다.
- 모바일 고정 결과 버튼과 본문 여백에 safe-area를 반영한다.
- 도움말은 focus·hover·touch·Escape를 지원하고 핵심 제한은 인라인으로 유지한다.
- 모션은 160~220ms의 opacity/transform에만 사용하고 reduced-motion을 따른다.
- AM-OTC-004와 충돌하는 검색 기간 주석을 바로잡는다.

## 6. 검증

- 집중 테스트가 먼저 실패하고 구현 뒤 통과하는지 확인한다.
- `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, `git diff --check`를 실행한다.
- 봉인 연구 산출물과 별도 v5.1 작업 파일에 diff가 없는지 확인한다.
- 브라우저는 사용하지 않고 코드 계약·빌드·정적 접근성 검토로 확인한다.

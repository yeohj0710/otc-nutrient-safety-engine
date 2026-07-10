# 데이터 사전과 계보

## 1. 식별자 체계

| 식별자 | 단위 | 생성 시점 | 예시 역할 |
|---|---|---|---|
| `search_run_id` | 데이터베이스 검색 실행 | 검색 | 같은 식의 재실행 구분 |
| `record_id` | 반입된 서지 레코드 | 정규화 | 데이터베이스별 중복 전 기록 |
| `report_id` | 논문·초록·등록자료 한 건 | 원문 연결 | 한 연구의 여러 보고서 구분 |
| `study_family_id` | 실제 연구 단위 | 중복/보고서 연결 | 논문·보조분석·등록자료 묶음 |
| `extraction_id` | 연구-결과 추출 레코드 | 추출 | 결과별 값과 locator 연결 |
| `evidence_id` | 검증된 근거 주장 | 합성 | 연구 결과 또는 규범 기준 |
| `quote_id` | 원문 근거 위치 | 추출 | 규칙과 논문 주장 역추적 |
| `rule_id` | 상담지원 규칙 | 규칙 검토 | 앱 실행 단위 |
| `scenario_id` | 검증 사례 | 독립 검증 | 개발/held-out 분리 |
| `metric_id` | 최종 수치 | 분석 | 논문·앱·README 공유 |
| `claim_id` | 논문 핵심 주장 | 집필 | 수치·문헌 근거 검증 |

식별자를 재사용하지 않는다. 레코드가 폐기되면 삭제보다 상태와 대체 ID를 기록한다.

## 2. 단계별 최소 필드

### 검색

- 데이터베이스·플랫폼
- 정확한 검색식 파일
- UTC 실행시각
- 검색 범위와 제한
- hit/export/import 수
- 원시 파일 경로와 SHA-256
- operator와 status

### 선별

- reviewer별 독립 결정
- AI 출력 노출 여부
- rationale 또는 전문 제외 주 사유
- adjudicated decision
- timestamp
- study family 연결

### 추출

- 대상자·병용 약물
- 성분·제형·용량·기간
- 비교군
- 결과 정의·시점
- 사건 수·분모 또는 효과치·불확실성
- locator와 supporting quote
- extractor·verifier·verification status

### 근거평가

- 도구와 버전
- 결과 수준 평가 단위
- domain별 판단과 근거 위치
- GRADE 하향·상향 이유
- 불일치 조정 기록

### 규칙

- population/medication/dose/duration 조건
- 결과와 행동 등급
- 메시지 강도·불확실성
- evidence ID·quote ID
- 검토자·상태·유효기간·재검토일

### 검증

- split·난도·노드
- 구조화 입력
- gold hazard·gold action
- 필수 추가 질문
- 허용 규칙 ID
- 예측 결과
- critical false negative·false reassurance·provenance

## 3. 데이터 계보 규칙

`raw -> normalized -> adjudicated -> verified -> frozen -> released`의 상태를 명시한다. 하위 상태의 데이터는 상위 산출물에 직접 들어갈 수 없다.

예를 들어 규칙은 다음 연결을 만족해야 한다.

```text
rule_id
  -> evidence_id
  -> extraction_id / normative source record
  -> report_id
  -> source quote + locator
  -> raw source reference
```

논문의 숫자는 다음 연결을 만족해야 한다.

```text
claim_id
  -> metric_id
  -> metrics_manifest entry
  -> analysis script
  -> frozen input artifacts + hashes
```

## 4. 수정·삭제 정책

- 서지 정규화 오류: 원시 레코드는 유지하고 normalized version을 올린다.
- 사람 판정 변경: 기존 결정과 변경 사유·adjudicator를 보존한다.
- 추출 수정: 이전 값, 새 값, 근거 locator, 수정자를 기록한다.
- 규칙 폐기: `deprecated` 상태와 대체 규칙·이유를 기록한다.
- 논문 수치 수정: metrics manifest를 다시 생성하고 claim ledger를 재검증한다.

## 5. 날짜와 단위

- 시각: ISO 8601 UTC
- 날짜: `YYYY-MM-DD`
- 용량: 원 단위와 표준화 단위를 모두 보존
- 비타민 D: IU와 µg 변환 시 변환식·제형을 기록
- 칼슘: 원소 칼슘 기준 여부 명시
- 오메가-3: fish oil 총량과 EPA+DHA 또는 purified EPA를 구분
- 비타민 K: K1/K2·menaquinone subtype을 구분
- 비타민 C: 경구 보충제와 정맥 투여를 구분

## 6. 공개 범위

공개 가능한 파생 데이터에는 저작권 있는 원문 전체를 넣지 않는다. `supporting_quote`는 필요한 최소 길이로 제한하고, 접근권한이 필요한 locator는 비공개 원문 경로와 분리한다.

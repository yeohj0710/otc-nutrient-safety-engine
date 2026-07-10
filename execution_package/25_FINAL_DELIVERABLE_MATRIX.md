# 최종 산출물 매트릭스

## 1. 제출·재현 패키지

| 범주 | 필수 산출물 | 완료 증거 |
|---|---|---|
| 연구 정체성 | repo identity, legacy inventory | Gate 0 report |
| 프로토콜 | protocol, amendment log, registration record | 해시·날짜·검토 기록 |
| 검색 | DB별 전체 검색식, run log, raw exports | hit/export/import·SHA-256 |
| 선별 | calibration, 독립 판정, 전문 제외표 | 전 기록 final decision |
| PRISMA | counts JSON, flow diagram, checklist | 자동 산술 검사 |
| 원문 추출 | verified extraction, source quotes | verifier·locator 100% |
| 근거평가 | RoB, GRADE, evidence profiles | 설계/결과별 완전성 |
| 근거 합성 | 5노드 evidence map, 집중 합성 | 분석 스크립트·표·그림 |
| AI 연구 | gold sets, prompts, raw outputs, metrics | held-out·CI·오류분석 |
| 규칙 | rule schema, trace table, released ruleset | evidence/quote 참조 무결성 |
| 소프트웨어 | 앱, tests, build, deployment metadata | commit·ruleset version |
| 독립 검증 | held-out scenarios, expert review, metrics | critical FN·provenance 검사 |
| 논문 | DOCX, PDF, appendices, claim ledger | 학교 형식·렌더 검수 |
| 공개 | README, data dictionary, AI disclosure | 공개/비공개 자료 분리 |

## 2. 졸업논문 최소 표·그림

### 본문 표

1. 연구 질문과 임상 노드
2. 데이터베이스별 검색 및 선별 현황
3. 포함 연구 특성
4. 비뚤림 위험 요약
5. 주요 결과별 GRADE 근거표
6. AI 선별·추출 성능
7. 규칙 데이터 모델과 근거 추적 완전성
8. 독립 시나리오 검증 성능
9. 주요 오류 사례와 시정조치

### 본문 그림

1. 연구 전체 흐름도
2. PRISMA 흐름도
3. 5개 노드 근거 지도
4. 집중 합성 forest plot 또는 SWiM 효과방향 그림
5. AI 평가 설계와 데이터 분할
6. 규칙의 근거 계보 도식
7. 시나리오 검증 confusion/error plot
8. 최종 시스템 화면 또는 구조도

표·그림 수는 실제 결과에 따라 조정하지만, 같은 내용을 장식적으로 반복하지 않는다.

## 3. 부록

- 전체 검색전략
- 포함·전문 제외 연구 목록
- 추출 항목 정의
- RoB 도메인 판정
- GRADE 근거표
- AI 프롬프트와 출력 스키마
- AI 오류 사례
- 규칙 목록과 source trace
- 시나리오 구성·전문가 판정 절차
- 분석 코드·환경·재현 명령
- AI 사용 공개문

유료 원문과 개인식별정보는 부록에 포함하지 않는다.

## 4. 논문 완료 정의

다음이 모두 참일 때만 논문 완료로 표시한다.

- 마지막 검색 업데이트까지 선별됨
- 모든 포함 연구의 전문 검토·추출·RoB 완료
- 중요 결과 GRADE 완료
- AI held-out 평가와 독립 시나리오 검증 완료
- metrics manifest에서 모든 수치 생성
- claim ledger가 핵심 주장 100%를 연결
- 지도교수 피드백 반영 내역 기록
- DOCX/PDF가 학교 형식과 렌더링 검사를 통과
- 앱·논문·README의 범위·수치·버전이 일치
- 사람에게 필요한 미결 항목이 최종 결과에 없음

## 5. 완료할 수 없는 조건의 처리

DB 접근, 제2검토자, 전문 패널, IRB 등 필수 조건이 확보되지 않으면 사실을 꾸며 빈칸을 채우지 않는다. 차단된 범위를 명시하고, 연구 질문을 축소하거나 제출 논문의 주장 수준을 낮추는 공식 결정이 있어야 한다. 단순히 `추후 연구`로 넘기고 완성 논문으로 표시하지 않는다.

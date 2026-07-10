# 여형준 졸업논문 재설계 실행 패키지

작성 기준일: 2026-07-10  
기준 문서: `연구계획서_여형준_260618_서명본.pdf`  
기본 실행 대상: **여형준 연구**  
권장 논문 유형: **실험 및 분석논문**

## 이 패키지의 목적

이 패키지는 기존 산출물을 다듬는 문서가 아니다. 기존 자료를 검증되지 않은 초안으로 취급하고, 연구 질문·문헌검색·선별·근거평가·AI 활용·규칙 생성·소프트웨어 검증·졸업논문 집필을 다시 연결하는 실행 명세다. Codex는 파일을 읽고 곧바로 작업을 시작하되, 각 단계의 품질 관문을 통과하기 전에는 다음 단계의 결과를 확정해서는 안 된다.

## 가장 먼저 확인할 사실

1. 사용자가 가장 중요하다고 지정한 문서는 여형준의 연구계획서다.
2. 사용자가 제시한 `otc-nutrient-safety-engine`은 현재 공개 배포 내용상 권혁찬 연구와 연결되어 있다.
3. 여형준 연구와 정합적인 기존 배포는 `nutrition-safety-engine` 계열이다.
4. 따라서 이 패키지는 **여형준 연구를 기본 분기**로 선택한다. `otc-nutrient-safety-engine`의 범용 엔진 코드는 참고하거나 재사용할 수 있지만, 권혁찬의 이름·주제·근거·수치·규칙을 여형준 논문으로 가져오면 안 된다.

## 권장 최종 제목

**국문**  
항응고제 복용자와 신장결석 고위험군을 위한 영양소 보충제 안전성 근거 매핑과 근거 추적형 상담지원 시스템의 개발 및 검증

**영문**  
Evidence mapping of dietary supplement safety and development and validation of a traceable counseling-support system for anticoagulant users and adults at high risk of nephrolithiasis

## 연구의 핵심 산출물

- 사전 고정된 연구 프로토콜과 검색 전략
- 전량 반입·중복 제거된 문헌 데이터셋
- 사람이 판정한 AI 평가용 골드 스탠더드
- 원문 근거 위치까지 포함한 추출표와 비뚤림 위험 평가
- 5개 임상 노드의 근거 지도와 1개 집중 합성
- 근거 문장까지 역추적 가능한 안전성 규칙 데이터베이스
- 독립 시나리오에서 평가된 상담지원 프로토타입
- 수치·표·그림이 데이터에서 재생성되는 졸업논문

## 읽는 순서

1. `01_CURRENT_STATE_AUDIT.md`
2. `02_RESEARCH_DECISION_MEMO.md`
3. `03_MASTER_PROTOCOL.md`
4. `11_QUALITY_GATES.md`
5. `13_CODEX_MASTER_PROMPT.md`
6. `14_AGENTS.md`
7. `15_TASK_GRAPH.json`

## 절대 원칙

- 검색 결과 상위 20개 또는 100개만 저장한 자료는 체계적 문헌고찰의 전체 선별 자료로 간주하지 않는다.
- 기존 CSV의 숫자와 앱 지표는 원자료에서 재계산되기 전까지 논문 결과로 사용하지 않는다.
- 원문을 확인하지 않은 초록 기반 후보는 근거 규칙이 아니다.
- LLM은 자동 제외자·최종 근거평가자·임상 판단자가 아니다.
- 결과를 먼저 쓰고 그에 맞는 근거를 찾지 않는다.
- 근거 동결 전에는 결과·고찰·결론을 최종 작성하지 않는다.
- 앱이 일치하는 예시를 반환했다는 사실만으로 정확성을 주장하지 않는다.
- 일치하는 근거를 찾지 못한 경우 `안전`이 아니라 `검토된 규칙 없음`으로 표시한다.

## 실행을 시작하는 명령

패키지를 대상 저장소의 `execution_package/`에 복사했다고 가정한다.

```bash
python execution_package/scripts/bootstrap_research_v2.py \
  --repo-root . \
  --package-root execution_package

python execution_package/scripts/check_project_identity.py --root .
```

첫 명령은 기존 파일을 덮어쓰지 않고 `research_v2` 구조와 양식·설정을 만든다. 두 번째 명령이 실패하면 `research_v2/audit/repo_identity.json`의 실패 원인을 해결하기 전까지 연구 데이터를 생성하지 않는다.

## 추가 설계 문서

- `20_ENVIRONMENT_AND_REPRODUCIBILITY.md`: 실행환경·해시·재생성 규칙
- `21_DRAFT_SEARCH_STRATEGIES.md`: 5개 임상 노드의 검색 개념 블록과 PubMed 초안
- `22_TARGET_REPOSITORY_ARCHITECTURE.md`: 연구 데이터·규칙·앱의 책임 분리
- `23_DATA_DICTIONARY_AND_LINEAGE.md`: 식별자·필드·계보
- `24_ERROR_TAXONOMY_AND_CORRECTIVE_ACTIONS.md`: 오류 유형과 릴리스 차단 기준
- `25_FINAL_DELIVERABLE_MATRIX.md`: 논문·데이터·코드의 최종 완료 증거

## 이 패키지가 보장하지 않는 것

어떤 프롬프트도 데이터베이스 접근권한, 지도교수 승인, 제2검토자 판정, 전문 패널, IRB 판단을 대신하거나 연구의 완벽성을 보장할 수 없다. 이 패키지는 그런 의존성을 숨기지 않고 강제 관문으로 만들며, 확보되지 않은 사실을 AI가 꾸며서 완료하지 못하도록 설계한다. 사람이 필요한 작업은 정확한 요청 형식으로 분리하고, 차단되지 않은 연구·코드 작업은 계속 수행한다.

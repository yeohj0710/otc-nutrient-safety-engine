# 소프트웨어 개발·검증 명세

## 1. 저장소 기본 결정

여형준 연구의 기본 저장소는 `nutrition-safety-engine` 계열이어야 한다. 현재 Codex가 `otc-nutrient-safety-engine`에서 실행된다면 다음 순서로 처리한다.

1. 원격 주소·프로젝트명·학생명·학번·배포 도메인 검사
2. 권혁찬 특화 데이터와 범용 코드를 분리
3. 범용 엔진을 별도 package 또는 새 worktree로 복사
4. 여형준 데이터와 UI는 새 브랜치/프로젝트에서 시작
5. 과거 Kwon 규칙·수치가 import되지 않는 테스트 작성

## 2. 권장 디렉터리

```text
research_v2/
  protocol/
  search/raw/
  search/normalized/
  screening/
  full_text/
  extraction/
  risk_of_bias/
  synthesis/
  ai_eval/
  rules/
  validation/
  thesis/
  audit/
src/
  domain/
  engine/
  provenance/
  ui/
scripts/
  search/
  screen/
  extract/
  synthesize/
  validate/
```

원자료는 수정하지 않는다. 정제·분석 결과는 새 파일로 만들고 입력 해시를 기록한다.

## 3. 런타임 원칙

- 임상 위험 판정은 검토된 결정론적 규칙으로 수행
- LLM은 자유문 입력을 구조화하는 선택적 전처리로만 사용
- LLM이 추출한 약물·성분·용량을 사용자가 확인하기 전에는 판정 실행 금지
- 네트워크 오류가 결과를 바꾸지 않도록 출시 규칙은 로컬 버전 데이터 사용
- 모든 응답에 ruleset version과 timestamp 포함

## 4. 테스트 층

### 단위 테스트

- 단위 변환
- 경계 용량
- 기간 조건
- 복합성분 합산
- 약물·질환 동의어
- 누락 정보 처리
- 충돌 해결

### 계약 테스트

- JSON schema
- rule ID uniqueness
- evidence ID existence
- source locator 존재
- deprecated rule 미노출

### 회귀 테스트

기존 대표 시나리오가 의도한 결과를 유지하는지 확인한다. 단, 이는 정확성 검증과 구분해 보고한다.

### 독립 검증 테스트

규칙 작성에 쓰이지 않은 골드 시나리오로 평가한다.

## 5. 독립 시나리오 데이터셋

권장 구성은 120건이다.

- 5개 노드 × 16건 = 80건
  - 명확한 양성 6
  - 경계 용량/기간 4
  - 정보 누락 3
  - 음성·관련 없음 3
- 교차 조건 20건
- 범위 밖 음성 대조 20건

시나리오 작성자는 규칙 구현 세부를 보지 않는다. 최소 2명의 검토자가 독립적으로 gold label, 행동 등급, 필수 질문, 허용 가능한 메시지 요소를 판정한다.

## 6. 핵심 검증 지표

- hazard flag sensitivity/specificity
- action class macro-F1
- exact match와 clinically acceptable match
- critical false negative count
- false reassurance rate
- missing-information detection sensitivity
- source/provenance completeness
- stale/invalid source rate
- 노드별 오류율
- 입력 단위·표현별 오류율

모든 지표에 분모와 95% 신뢰구간을 표시한다.

## 7. 전문가 내용 검토

각 규칙을 관련성, 정확성, 명확성, 적용범위, 메시지 강도, 근거 추적성으로 평가한다. I-CVI와 S-CVI/Ave를 계산하고 자유서술 의견을 오류 유형으로 코딩한다. 패널이 3–5명이라면 우연 일치의 영향을 명시하고 필요 시 modified kappa를 함께 보고한다.

## 8. 사용성

사람을 모집한 사용성 평가를 수행하려면 기관의 IRB/면제 확인을 먼저 완료한다. 승인되면 대표 과제 성공률, 오류, 완료시간, SUS 또는 UMUX-Lite, 자유 의견을 수집한다. 승인되지 않으면 전문가 휴리스틱 평가와 인지적 walkthrough만 수행하고 이를 사용성 연구로 과장하지 않는다.

## 9. 배포 전 안전 문구

- 검토된 범위만 명시
- 입력하지 않은 질환·약물에 대한 판단을 하지 않음
- `규칙 없음`을 `안전`으로 번역하지 않음
- 출혈, 혈전, 급성 신장 증상 등 응급 신호는 일반 안내와 분리
- 사용자가 복용 변경을 직접 결정하도록 지시하지 않음

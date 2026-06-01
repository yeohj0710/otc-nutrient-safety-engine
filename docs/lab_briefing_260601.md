# 260601 랩 미팅 브리핑 자료

## 개요

- 권혁찬 연구는 기존 여형준 연구와 같은 시스템 구축형 연구 구조를 쓰되, 연구 질문을 성분 중심으로 분리함
- 기존 연구가 항응고제 복용자/신장 고위험군을 타겟으로 했다면, 이번 연구는 일반의약품형 고함량 영양성분 자체를 타겟으로 설정
- PubMed API 기반 문헌검색 pipeline을 새 repo에 그대로 적용하고, 새 검색 결과를 별도 CSV로 저장

## 연구 주제

일반의약품형 고함량 영양성분의 안전성 근거 매핑과 개인맞춤 조회 시스템 구축

## 차별성

| 구분 | 기존 연구 | 권혁찬 연구 |
| --- | --- | --- |
| 출발점 | 환자/질환/약물 맥락 | 성분/제제/고함량 복용 맥락 |
| 중심 질문 | 항응고제 복용자와 신장 고위험군에서 어떤 보충제가 위험한가 | 일반의약품형 고함량 영양성분은 어떤 조건에서 주의가 필요한가 |
| 타겟 | 출혈, INR, 신장결석, 고칼슘뇨증 | 지용성 비타민·칼슘, B6/B군, 철분·마그네슘·아연 |
| 시스템 | 개인 조건 기반 규칙 조회 | 성분·함량·개인 조건 기반 규칙 조회 |

## 이번에 만든 구조

```text
C:\dev\otc-nutrient-safety-engine
  tools\search_pipeline
  data\systematic_search
  docs\research_plan_260601.md
  docs\search_strategy_260601.md
  docs\lab_briefing_260601.md
```

## PubMed 검색 방향

1. vitamin D/calcium 고함량 및 고칼슘혈증·신결석 관련 검색
2. vitamin B6/B-complex 및 neuropathy 관련 검색
3. iron/magnesium/calcium/zinc 및 위장관 이상반응·흡수 상호작용 관련 검색

## 랩미팅에서 말할 요약

이번 주에는 기존 시스템 구축 연구의 틀을 유지하되, 권혁찬 연구는 환자군 중심이 아니라 성분 중심으로 주제를 분리했습니다. 일반의약품과 건강기능식품 양쪽에서 사용되는 고함량 비타민·미네랄 성분을 대상으로 PubMed 검색식을 만들고, 검색 로그와 후보 문헌을 CSV로 남기는 pipeline을 새 repo에 적용했습니다. 이후 title/abstract screening과 evidence extraction을 통해 성분별 안전성 규칙으로 연결할 예정입니다.

## 다음 할 일

- 검색 결과의 title/abstract 1차 screening
- B6 neuropathy와 vitamin D/calcium toxicity 쪽을 우선 full-text 검토 대상으로 좁히기
- 일반의약품/건기식 중복 성분 목록을 국내 제품 기준으로 추가 확인
- 성분별 safety rule 초안 작성

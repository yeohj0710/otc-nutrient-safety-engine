# OTC Nutrient Safety Rule Explorer

생성/전환 시각: 2026-06-01

## 목적

이 프로젝트는 일반의약품과 건강기능식품의 경계에 있는 고함량 영양성분을 대상으로, 성분·용량·복용 약물·질환 조건에 따른 안전성 근거를 조회하는 Next.js 앱입니다.

기존 `nutrition-safety-engine`의 기술 구조를 재사용하지만, 연구 질문은 환자군/질환 중심이 아니라 성분 중심으로 분리합니다.

- 기존 연구: 항응고제 복용자 및 신장 관련 고위험군에서의 영양소 보충제 안전성
- 권혁찬 연구: 일반의약품형 고함량 영양성분 복용자를 위한 성분 중심 안전성 근거 매핑

## 연구 주제

국문: 일반의약품형 고함량 영양성분의 안전성 근거 매핑과 개인맞춤 조회 시스템 구축

영문: Development of an Ingredient-Centered Evidence Mapping and Personalized Query System for Safety Evaluation of Over-the-Counter Nutrient Preparations

## 1차 타겟

| 타겟 | 성분 예시 | 주요 안전성 outcome | 차별점 |
| --- | --- | --- | --- |
| 지용성 비타민·칼슘 고함량 축 | vitamin D, calcium, vitamin A/E/K | hypercalcemia, hypercalciuria, nephrolithiasis, toxicity | 성분·용량 중심 |
| B군 복합제 축 | vitamin B6, B12, benfotiamine, B-complex | neuropathy, neurotoxicity, high-dose exposure | 일반의약품성 고함량 제제 중심 |
| 미네랄 보충제 축 | iron, magnesium, calcium, zinc | constipation, diarrhea, absorption interaction, overdose | OTC/건기식 중복 성분 중심 |

## 구현 구조

- 웹앱: Next.js 16, React 19
- 결정적 규칙 엔진: `src/lib/safety-engine/`
- 근거 데이터: `data/knowledge_pack.json`
- 검색 pipeline: `tools/search_pipeline/`
- 권혁찬 검색 결과: `data/systematic_search/`
- 연구 문서: `docs/research_plan_260601.md`, `docs/search_strategy_260601.md`, `docs/lab_briefing_260601.md`

## 배포

https://otc-nutrient-safety-engine.vercel.app

## 검색 pipeline 실행

```bash
python -m tools.search_pipeline.cli init
python -m tools.search_pipeline.cli pubmed --target high_dose_vitd_calcium --query "..."
python -m tools.search_pipeline.cli pubmed --target b6_bcomplex_neuropathy --query "..."
python -m tools.search_pipeline.cli pubmed --target mineral_gi_interaction --query "..."
python -m tools.search_pipeline.cli dedup
```

## 검증 명령

```bash
npm run prepare:knowledge
npm run typecheck
npm run test
npm run build
```

## 안전 제한

이 앱은 의학적 진단 또는 복약 결정을 대체하지 않습니다. 문헌과 공공자료 근거를 추적 가능한 형태로 보여주는 연구용 prototype이며, 최종 복용 판단은 의료진 상담을 전제로 합니다.

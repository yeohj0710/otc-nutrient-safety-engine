# 웹사이트 산출물 기록

- 공개 URL: https://otc-nutrient-safety-engine.vercel.app
- Vercel production deployment: `dpl_44dSm53KpDPWYKarniZoW8LMcKAZ`
- 연구자: 권혁찬(2021194024)
- 검증일: 2026-07-12

## 구현 범위

연구 범위 17개 성분을 대상으로 성분, 하루 섭취량, 병용약, 질환 및 선택적 개인 조건을 입력받아 기존 탐색 규칙과 대조한다. 초보자는 예시 입력을 눌러 자동 입력과 결과를 확인할 수 있다.

## 검증 결과

- 앱 테스트: 35/35 통과
- 연구 테스트: 51/51 통과
- ESLint: 통과
- TypeScript: 통과
- Next.js production build: 통과, 155개 route 생성
- production API: 마그네슘·비타민 D·아연·미지원 성분 시나리오 확인
- 모바일 390 px: 가로 넘침 없음

## 데이터 경계

- 논문 수치: `research_v2/thesis/metrics_manifest.json`
- 사이트 탐색 규칙: `data/knowledge_pack.json` 기반 legacy scoping 규칙
- `research_v2` released 규칙: 0개
- 임상 release: 승인되지 않음

사이트의 110개 탐색 규칙을 최종 연구에서 검증된 임상 규칙으로 해석하면 안 된다. OpenAI API 키가 없는 배포에서는 결정론적 요약을 사용한다.

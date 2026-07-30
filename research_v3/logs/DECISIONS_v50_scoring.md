# v5.0 선별 채점 arm 결정 기록

## D-01. 채점 arm은 기존 v5.0 라벨과 분리한다

기존 `decisions.csv`와 semantic adjudication 파일은 수정하지 않는다. 새 채점 라벨은 `screening_ai_reference_v50` 아래에만 두며, 기존 재판정 입력으로 재사용하지 않는다.

## D-02. 사람 참조 행은 0건이다

이번 비교의 참조는 기존 v5.0 최종 AI 라벨이다. 따라서 모든 성능 필드는 `_vs_ai_reference` 접미사를 사용하고, `independent_blinding=false`와 `release_ready=false`를 유지한다.

## D-03. 모집단은 43,207건 전체다

분류기 결정과 semantic adjudication을 합성한 뒤 최종 `decisions.csv`와 전량 대조한다. 최종 라벨 분포는 retain 7,875건, deprioritize 34,965건, uncertain 367건이다. 재판정 여부 분포는 adjudicated 5,000건, classifier 38,207건이다.

## D-04. 기본층은 질문 × 최종 라벨 × 재판정 여부다

비어 있지 않은 기본층 25개가 모집단을 완전분할한다. 특히 최종 retain이면서 재판정되지 않은 6,682건을 질문별 독립층으로 둔다.

## D-05. 불변식 실패 15건은 전수층이다

불변식 실패가 포함된 기본층은 실패 행 전수층과 나머지 확률표본층으로 나눈다. 이 분할 뒤 실제 표집층은 33개다. 스크립트는 표집층 `population_N` 합계가 43,207인지 검사한다.

## D-06. 목표 표본은 894건이다

확률표본층은 원칙적으로 층마다 38건을 뽑고, 모집단이 더 작으면 전수로 넣는다. 불변식 실패 15건을 전수로 합쳐 총 894건이다.

## D-07. 결정적 순위를 고정한다

seed는 `20260730-v50-scoring-arm`이다. 각 행의 순위는 `SHA-256(seed|question_id|record_id)` 오름차순이다.

## D-08. 설계가중치는 확률표본층 N_h/n_h, 전수층 1이다

모든 결과 행에 `population_N`, `sample_n`, `census`, `weight`를 봉인 정답과 함께 기록한다. 전수층은 표집오차가 없으므로 부트스트랩에서 다시 뽑지 않는다.

## D-09. 카드에는 여섯 필드만 넣는다

카드 필드는 `record_id`, `question_id`, `title`, `abstract`, `publication_types`, `mesh_terms`다. 분류기 라벨, 재판정 라벨, 선정 이유, 신뢰도와 표집층 정보는 누출 검사에서 금지한다.

## D-10. 채점 기준은 동결 프롬프트 하나다

`frozen_semantic_adjudication_prompt.md`를 그대로 쓴다. 동결 프롬프트가 답을 정하지 않은 경계만 `SCORER_RUBRIC.md`에 선례로 누적한다.

## D-11. 초록 없는 행의 출력은 하네스가 강제한다

초록이 비어 있으면 `confidence=low`, `evidence_basis=title_only`, `insufficient_abstract`를 모두 요구한다. 하나라도 없으면 잠금을 거부한다.

## D-12. 정답 공개 전에 라벨을 잠근다

894건 전부를 채점한 뒤 하네스 검사를 통과했다. `2026-07-30T07:19:24.842781+00:00`에 라벨을 잠갔고 SHA-256은 `a1cf7ba97a96186c93a3c6e62d02d868547220fa29c2d150858ff12262cb5cc4`다. 영수증은 `truth_opened_before_lock=false`를 기록한다.

## D-13. 새 채점은 AI 독립 맹검으로 기록한다

채점자는 기존 참조 라벨과 봉인 정답을 보지 않고 판정했다. 따라서 이 arm은 `independent_blinding_ai=true`다. 사람 독립 맹검은 수행하지 않았으므로 `independent_blinding=false`다.

## D-14. 비교는 세 갈래로 보고한다

전체, classifier 38,207건 층, adjudicated 5,000건 층을 따로 계산한다. retain을 양성으로 두며 deprioritize와 uncertain은 비양성으로 묶는다. 정확한 3개 라벨 행렬과 질문별 일치율도 함께 남긴다.

## D-15. 불확실성은 층화 부트스트랩과 Wilson 구간으로 나눈다

주 추론 구간은 층 안에서 확률표본만 10,000회 다시 뽑는 층화 부트스트랩이다. 전수층은 매 반복에 고정한다. Wilson 95% 구간은 표본의 단순 이항비율을 보조적으로 제시하며 층화 설계의 주 구간으로 해석하지 않는다.

## D-16. Cohen κ는 3개 라벨 설계가중 행렬로 계산한다

retain/deprioritize/uncertain의 3×3 가중 행렬에서 관찰 일치와 우연 일치를 계산한다. 이 값도 사람 판단과의 일치가 아니라 AI 참조와의 일치다.

## D-17. 로건-글래든 값은 교차확인이 아니다

AI 참조 라벨로 층을 만들고 같은 표본에서 두 오류모수를 구하면 로건-글래든 식은 새 채점 retain 비율로 대수적으로 환원된다. 이번 절대차 `1.25e-16`은 구현 일관성만 보여 주며 독립 보정 근거가 아니다. 외부 연구의 오류모수를 넣을 때만 보정으로 해석할 수 있다.

## D-18. 기존 v5.0 provenance 공백은 영구 한계다

v5.0 재판정 실행자·모델·실행 시각·선행 질문 영수증은 당시 남지 않았다. 이번 채점 arm의 실행자·모델 표기·시각·잠금 영수증은 새 작업만 증명하며 기존 공백을 소급해서 메우지 않는다.

## 최종 산출물

- 설계와 봉인 파일: `research_v3/otc/validation/screening_ai_reference_v50/`
- 실행 보고: `research_v3/logs/v50_SCORING_FINAL.md`
- 기계 판독 보고: `research_v3/logs/v50_scoring_report.json`
- 비교 산출물: `research_v3/otc/synthesis/screener_vs_ai_reference_v50.json`
- 재현 스크립트: `tools/v50_scoring/`

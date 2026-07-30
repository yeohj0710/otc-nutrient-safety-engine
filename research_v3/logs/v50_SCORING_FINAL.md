# v5.0 선별 채점 arm 최종 보고

생성 시각: `2026-07-30T07:33:32.394444+00:00`

## 결론

동결 프롬프트를 보지 않은 것이 아니라 정답 라벨을 보지 않은 상태에서, 동결 프롬프트를 그대로 사용해 894건을 새로 판정했다. 이 채점 arm에는 사람 참조 행이 없으므로 아래 수치는 사람 판단과의 성능이 아니라 AI 참조와의 일치도다.

## 라벨 잠금은 정답 공개보다 먼저 끝났다

- 잠금 시각(UTC): `2026-07-30T07:19:24.842781+00:00`
- 잠금 SHA-256: `a1cf7ba97a96186c93a3c6e62d02d868547220fa29c2d150858ff12262cb5cc4`
- `truth_opened_before_lock=false`
- `independent_blinding=false`, `independent_blinding_ai=true`, `release_ready=false`

## 표본층은 43,207건을 빠짐없이 한 번씩 나눈다

층 축은 질문 × 최종 라벨 × 재판정 여부다. 불변식 실패가 있는 기본층은 실패 행 전수층과 나머지 확률표본층으로 나눴다.

| 질문 / 재판정 여부 / 최종 라벨 | population_N | sample_n | 불변식 실패 전수 n |
|---|---:|---:|---:|
| OTC-LIT-Q01-ACETAMINOPHEN / adjudicated / deprioritize | 818 | 39 | 1 |
| OTC-LIT-Q01-ACETAMINOPHEN / adjudicated / retain | 448 | 38 | 0 |
| OTC-LIT-Q01-ACETAMINOPHEN / adjudicated / uncertain | 134 | 38 | 0 |
| OTC-LIT-Q01-ACETAMINOPHEN / classifier / deprioritize | 5,491 | 38 | 0 |
| OTC-LIT-Q01-ACETAMINOPHEN / classifier / retain | 2,368 | 38 | 0 |
| OTC-LIT-Q02-NSAID / adjudicated / deprioritize | 591 | 41 | 3 |
| OTC-LIT-Q02-NSAID / adjudicated / retain | 499 | 39 | 1 |
| OTC-LIT-Q02-NSAID / adjudicated / uncertain | 110 | 38 | 0 |
| OTC-LIT-Q02-NSAID / classifier / deprioritize | 3,324 | 38 | 0 |
| OTC-LIT-Q02-NSAID / classifier / retain | 1,924 | 38 | 0 |
| OTC-LIT-Q03-COLD-ALLERGY / adjudicated / deprioritize | 479 | 40 | 2 |
| OTC-LIT-Q03-COLD-ALLERGY / adjudicated / retain | 98 | 39 | 1 |
| OTC-LIT-Q03-COLD-ALLERGY / adjudicated / uncertain | 23 | 23 | 0 |
| OTC-LIT-Q03-COLD-ALLERGY / classifier / deprioritize | 4,242 | 38 | 0 |
| OTC-LIT-Q03-COLD-ALLERGY / classifier / retain | 827 | 38 | 0 |
| OTC-LIT-Q04-DIGESTIVE / adjudicated / deprioritize | 1,374 | 38 | 0 |
| OTC-LIT-Q04-DIGESTIVE / adjudicated / retain | 132 | 42 | 4 |
| OTC-LIT-Q04-DIGESTIVE / adjudicated / uncertain | 94 | 38 | 0 |
| OTC-LIT-Q04-DIGESTIVE / classifier / deprioritize | 18,189 | 38 | 0 |
| OTC-LIT-Q04-DIGESTIVE / classifier / retain | 1,525 | 38 | 0 |
| OTC-LIT-Q05-TOPICAL / adjudicated / deprioritize | 178 | 39 | 1 |
| OTC-LIT-Q05-TOPICAL / adjudicated / retain | 16 | 16 | 2 |
| OTC-LIT-Q05-TOPICAL / adjudicated / uncertain | 6 | 6 | 0 |
| OTC-LIT-Q05-TOPICAL / classifier / deprioritize | 279 | 38 | 0 |
| OTC-LIT-Q05-TOPICAL / classifier / retain | 38 | 38 | 0 |
| **합계** | **43,207** | **894** | **15** |

검산: 기본층 `population_N` 합계는 43,207이다. 기본층 25개를 불변식 실패 여부로 나눈 실제 표집층은 33개다. 확률표본층 가중치는 `N_h/n_h`, 전수층 가중치는 1이다.

## 전체·분류기층·재판정층 결과

retain을 양성으로 두고 deprioritize와 uncertain을 비양성으로 묶었다. 괄호는 전수층을 고정한 층화 부트스트랩 10,000회 95% 구간이다.

| 분석층 | 표본 n | 추정 모집단 N | sensitivity_vs_ai_reference | specificity_vs_ai_reference | precision_vs_ai_reference | f1_vs_ai_reference | agreement_vs_ai_reference | Cohen κ(가중) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 전체 | 894 | 43,207 | 46.9% (40.3%–53.6%) | 95.8% (93.8%–97.7%) | 71.6% (62.1%–81.9%) | 56.7% (50.0%–62.9%) | 86.9% (84.9%–88.8%) | 0.493 (0.421–0.563) |
| 분류기층 | 380 | 38,207 | 41.7% (34.1%–49.3%) | 96.2% (93.9%–98.3%) | 70.1% (58.1%–83.5%) | 52.3% (44.2%–60.1%) | 86.7% (84.4%–88.8%) | 0.452 (0.363–0.539) |
| 재판정층 | 514 | 5,000 | 76.2% (68.8%–83.0%) | 92.7% (90.0%–95.0%) | 76.6% (70.1%–83.0%) | 76.4% (70.8%–81.5%) | 88.8% (86.1%–91.2%) | 0.639 (0.572–0.701) |

표본의 단순 이항비율에 대한 Wilson 95% 구간은 다음과 같다. 층화 설계의 주 추론 구간은 위 부트스트랩 구간이다.

| 분석층 | sensitivity_vs_ai_reference | specificity_vs_ai_reference | precision_vs_ai_reference | agreement_vs_ai_reference |
|---|---:|---:|---:|---:|
| 전체 | 50.4%–60.5% | 82.8%–88.7% | 67.7%–78.1% | 70.6%–76.4% |
| 분류기층 | 33.8%–47.6% | 89.9%–96.7% | 79.0%–92.9% | 62.5%–71.9% |
| 재판정층 | 64.7%–78.0% | 77.0%–85.2% | 59.5%–72.8% | 74.4%–81.6% |

## 불일치는 어느 방향으로 발생했나

정확한 3개 라벨 불일치는 표본 894건 중 306건이다.

| AI 참조 → 새 채점 | 표본 건수 | 설계가중 추정 건수 |
|---|---:|---:|
| deprioritize->retain | 20 | 1,318.3 |
| deprioritize->uncertain | 4 | 184.8 |
| retain->deprioritize | 155 | 4,007.2 |
| retain->uncertain | 7 | 172.5 |
| uncertain->deprioritize | 66 | 154.6 |
| uncertain->retain | 54 | 149.8 |

## 질문별 정확한 3개 라벨 일치율

| 질문 | 표본 n | 추정 모집단 N | 설계가중 일치율 | 표본 불일치 |
|---|---:|---:|---:|---:|
| OTC-LIT-Q01-ACETAMINOPHEN | 191 | 9,259 | 80.8% | 58 |
| OTC-LIT-Q02-NSAID | 194 | 6,448 | 70.8% | 73 |
| OTC-LIT-Q03-COLD-ALLERGY | 178 | 5,669 | 87.1% | 57 |
| OTC-LIT-Q04-DIGESTIVE | 194 | 21,314 | 92.7% | 89 |
| OTC-LIT-Q05-TOPICAL | 137 | 517 | 92.3% | 29 |

## 최종 retain 중 미재판정 6,682건에서 확인한 범위

독립층에서 190건을 확률표집했다. 새 채점도 retain을 준 설계가중 비율은 41.7%이며, 층화 부트스트랩 95% 구간은 34.1%–49.3%다.

이 표본은 6,682건에서 동결 프롬프트를 새로 적용했을 때 기존 최종 retain 라벨이 얼마나 재현되는지를 추정한다. 표본은 사람 판단과의 일치, 임상적 타당성, 또는 미재판정 6,682건 전부의 개별 오분류 여부를 말해 주지 않는다.

## 전수층과 로건-글래든 식의 해석

불변식 실패 전수층은 부트스트랩에서 다시 뽑지 않고 매 반복에 그대로 넣었다. 전수층만 분석하면 구간이 한 점으로 수축하는 것이 맞다.

로건-글래든 식과 설계가중 새 채점 retain 비율의 절대차는 `1.25e-16`다. 층을 AI 참조 라벨로 정하고 같은 표본에서 두 오류모수를 계산했기 때문에 생기는 대수적 항등식이다. 외부 검증연구의 오류모수를 쓰지 않은 이 계산은 독립 교차확인이 아니다.

## 소급할 수 없는 v5.0 한계

v5.0 재판정의 실행자·모델·실행 시각·선행 질문 영수증은 당시 기록되지 않아 소급 생성할 수 없다. 이번 채점 arm의 새 영수증은 별도 검증층의 provenance만 보완하며, 기존 재판정의 공백을 메우지 않는다.

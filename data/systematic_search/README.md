# 권혁찬 PubMed 검색 실행 요약

실행일: 2026-06-01

## 검색 결과

| target_id | PubMed hit 수 | 저장 후보 수 | 설명 |
| --- | ---: | ---: | --- |
| high_dose_vitd_calcium | 4,433 | 50 | vitamin D/calcium 고함량, 고칼슘혈증, 고칼슘뇨증, 신결석, 독성/이상반응 |
| b6_bcomplex_neuropathy | 478 | 48 | pyridoxine/B6/B-complex/benfotiamine, 신경병증/신경독성/이상반응 |
| mineral_gi_interaction | 14,238 | 50 | iron/magnesium/calcium/zinc, 위장관 이상반응, 흡수·상호작용 |

## 중복 제거

- 총 후보 record: 148건
- 중복 표시: 11건

## 1차 screening 초안

`screening_log.csv`는 title/abstract에 성분 키워드와 안전성 outcome 키워드가 함께 있는지를 기준으로 자동 초안을 채웠다.

이 값은 최종 판단이 아니라 사람이 검토해야 하는 suggested decision이다.

## 다음 단계

1. `include_candidate`를 우선 full-text 또는 abstract 수준에서 재검토한다.
2. `maybe_needs_manual_review`는 outcome이 숨겨져 있을 수 있으므로 title/abstract를 직접 확인한다.
3. `evidence_extraction.csv`의 `dose`, `population`, `comparator`를 논문별로 수동 보강한다.

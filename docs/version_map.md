# 버전 지도 — 무엇이 최종이고 무엇이 옛것인가 (2026-07-31)

이 저장소는 버전 축이 **둘**이라 헷갈린다. 그 둘을 먼저 갈라 놓는다.
**저장소에서는 어느 경로도 지우지 않았다.** 이유는 §5에 적었다.

같은 랩 여형준 연구의 지도는 `C:\dev\nutrition-safety-engine\docs\version_map.md` 에 있다.

## 0. 헷갈림의 진짜 원인 — 같은 "v4.0"이 서로 다른 것을 가리킨다

| 표기 | 이 저장소 (otc-nutrient-safety-engine) | 여형준 (nutrition-safety-engine) |
|---|---|---|
| `v4.0` | **폐기된 선행 트랙** (AM-OTC-002로 대체) | **최종 트랙** |
| `v5.0` | **최종 트랙** | 없음 |
| 최종 원장 | `research_v3/logs/v50_run_report.json` | `research/logs/v40_run_report.json` |

**두 저장소에 `v40_run_report.json` 이 각각 있다.** 여기 것은 폐기된 트랙의 기록이고,
여형준 것이 최종 원장이다. 파일명만 보고 수치를 옮기면 다른 연구 값을 섞게 된다.

기억할 한 줄: **여기는 v5.0이 끝, 여형준은 v4.0이 끝.**

## 1. 축이 둘이다

**축 A — 저장소 세대**

| 경로 | 상태 | 크기 |
|---|---|---|
| `research_v2/` | 영양성분 시절 **구세대**. 탐색 자료로만 | 390 MiB, 246 파일 |
| `research_v3/` | **현재 세대** | — |

**축 B — 문헌층 트랙** (`research_v3/` 안에서 다시 갈린다)

| 경로 | 상태 | 크기 |
|---|---|---|
| `research_v3/otc/literature/v5/` | **최종** | 1,007 MiB, 593 파일 |
| `research_v3/logs/v50_*` (8개) | **최종 원장·판단기록·채점** | 32 MiB |
| `research_v3/otc/literature/{picos,searches,screening}/` | v4.0 문헌층. **수정·삭제 금지**(비교 기준) | 113 MiB |
| `research_v3/logs/v40_run_report.json` | v4.0 원장. 폐기 트랙 기록 | — |
| `research_v3/otc/literature/screening_discarded_local3b/` | 로컬 파일럿 폐기물 | 6 MiB |

**축과 무관하게 계속 유효한 것**

| 경로 | 상태 |
|---|---|
| `research_v3/otc/{normalized,rules}/` | 허가원문 계층. **읽기만.** 결정층이라 트랙 교체와 무관 |
| `research_v3/screening/`, `research_v3/human_review_minimal/` | 사람 판단 레거시. **v4/v5 체인에 넣지 말 것** (31 MiB) |
| `tools/search_pipeline/embase_adapter.py` | 제2 데이터베이스 공백용. 명시 요청 없이 삭제 금지 |

## 2. 최종 수치 — 여기 것만 쓴다

| | v4.0 (폐기) | **v5.0 (최종)** |
|---|---:|---:|
| 선별 단위 | 5,724 | **43,207** |
| 고유 논문 | 5,724 | **42,822** |
| retain / deprioritize / uncertain | 2,240 / 3,423 / 61 | **7,875 / 34,965 / 367** |
| 재판정 | — | **5,000 (11.6%)** |
| 규칙–문헌 연결 | 16/16 규칙, 링크 20건 | **9/16 규칙, 링크 10건** |
| 검색식 | 결과(O) 블록 + Humans[Mesh] 포함 | **P AND I 만** |
| 검색 기간 | — | Q01~Q03 2010-01-01~ · Q04~Q05 2000-01-01~ |
| 채점 arm | 없음 | **894행** |

허가원문 결정층은 트랙과 무관하게 같다: 제품 13 · 성분 28 · 제품–성분 연결 47 ·
복용조건 32 · 규칙 16(released 15).

### 채점 arm (2026-07-30)

| 지표 | 값 |
|---|---|
| `agreement_vs_ai_reference` | 86.93% (CI 84.87~88.83) |
| `sensitivity_vs_ai_reference` | 46.92% (CI 40.29~53.58) |
| `specificity_vs_ai_reference` | 95.84% (CI 93.81~97.66) |
| Cohen κ | 0.493 (CI 0.421~0.563) |
| 파이프라인 전수 retain | **18.23%** (7,875/43,207) |
| 채점자 설계기반 추정 | **11.95%** |
| 비 (채점자 ÷ 파이프라인) | **0.66배** — 파이프라인이 더 많이 남긴다 |

불일치 방향도 `retain→deprioritize` 가 지배적이다(raw 155 대 20).

**여형준 연구는 같은 두 층 구조에서 반대 방향(2.18배, 덜 남김)이 나왔다.**
`agreement_vs_ai_reference` 는 86.93% 대 86.95%로 거의 같은데 retain 방향은 반대다 —
일치율만 비교하면 두 연구가 같아 보인다. **두 값을 하나의 설계 결론으로 합치지 마라.**
근거: `C:\dev\nutrition-safety-engine\research\protocol\HANDOFF_scoring_arm_comparability.md`.

## 3. 미연결 7규칙 — 사유를 정확히 적어야 한다

규칙 16개 중 9개에만 문헌을 연결했고 연결은 10건이다. 미연결 7개:
`OTC-RULE-003` max_daily_dose · `009` gi_bleeding_ulcer · `010` sedation_driving ·
`011` alcohol · `013` sedative_medication · `015` maximum_duration · `016` urgent_referral.

**사유는 검색 기간이 아니다.** `AM-OTC-003` 이 "v5.0 검색 기간(2022-01-01~) 이전 출판"이라고
적었으나 산출물과 맞지 않아 `AM-OTC-004` 로 정정했다.

- 실행된 기간 필터는 Q01~Q03 이 2010/01/01, Q04~Q05 가 2000/01/01 이고
  질의문 SHA-256 안에 들어 있다(`research_v3/otc/literature/v5/query_definitions.json`).
- v5.0 코퍼스 `evidence_map.csv` 42,822행의 `publication_year` 범위는 **2000~2026** 이다.
- 미연결 후보 9편의 출판연도는 2010~2025 로 **전부 해당 규칙의 허용질문 검색 기간 안**이다.
  기간 때문에 빠진 후보는 **0편**이다.

실제 사유는 둘이고 `literature_link_manifest.json` 의 `rejection_counts` 에 있다.

| 사유 | 건수 | 뜻 |
|---|---:|---|
| `not_in_v5_corpus` | 6 (고유 5편) | AM-OTC-002 로 결과(O) 블록을 뺀 P AND I 검색식이 그 논문을 인출하지 못했다 |
| `no_retain_decision_for_rule_question` | 4 | 코퍼스에는 있으나 규칙이 허용한 질문에서 retain 이 아니다 (`015` 두 편은 Q01 에서는 retain 인데 규칙은 Q03·Q04 만 허용) |

**중복복용이 주제인데 `max_daily_dose` 에 검증 근거가 0건**이라는 점은 따로 적는다.
후보 2편(29516533·26149538) 모두 `not_in_v5_corpus` 다.

사이트는 논문마다 v5.0 검증 배지를 표시한다. 사이트가 서빙하는 규칙 근거 문헌 19편 기준으로
**검증 10편 · v5.0 코퍼스에 없음 5편 · 코퍼스에 있으나 retain 아님 4편** 이다.
배지의 사유는 매니페스트가 기록한 값을 그대로 쓴다. 출판연도로 사유를 추정하던 이전 방식은
`AM-OTC-004` 로 폐기했고, 그때의 표기(기간 밖 8편·retain 아님 1편)는 더 쓰지 않는다.

## 4. 손으로 고치면 안 되는 생성물

해시가 다른 파일에 기록돼 있어 손편집하면 보호 감사에서 위조처럼 잡힌다.

| 파일 | 생성기 | 해시가 기록되는 곳 |
|---|---|---|
| `research_v3/logs/v50_FINAL.md` | `finalize_v50_logs.py` | `v50_protected_final_audit.json`, `v50_run_report.json` |
| `research_v3/protocol/protocol-v5.0-mecir-search.md` | — | 원장 |
| `.../v5/downstream/literature_link_manifest.json` | `build_downstream_v50.py` | 원장 |
| `AGENTS.md`, `docs/project_map.md` | `tools/build_v40_reporting.py` | — (문서만 고치면 다음 빌드에 되돌아간다) |

프로토콜을 바꿔야 하면 `research_v3/protocol/amendments.csv` 에 개정으로 남긴다.

## 5. 왜 저장소에서는 아무것도 지우지 않았는가

1. **프로토콜이 금지한다.** v5.0 §6이 v4.0 문헌층과 허가원문 계층을 "읽기만 하고
   수정·삭제하지 않는다"고 정한다. 여형준 v4.0 §6도 같다.
2. **비교 기준이 사라진다.** v4.0 문헌층은 AM-OTC-002 의 근거이자 대조군이다.
3. **되돌릴 수 없다.** `research_v3/otc/literature/v5/` 는 전체가 untracked 라
   잘못 지우면 git 으로 복구할 수 없다.

지우고 싶다면 연구자가 직접 판단할 항목은 이 정도다. 전부 로컬 전용이라 복구가 안 된다.

- `research_v3/otc/literature/screening_discarded_local3b/` (6 MiB)
- `research_v3/otc/literature/v5/etc/pycache-*` (10개 폴더)
- `research_v2/` (390 MiB) — 구세대 계보 근거라 논문에서 인용하지 않을 것이 확실할 때만

## 6. G드라이브는 규칙이 다르다 — 옮겼다

`G:\내 드라이브\여형준님\24 전공심화실습(1)\권혁찬`. 저장소가 아니라 논문 쓰는 사람이 직접
열어보는 곳이라 "어느 것이 현재본인가"가 더 중요하다. 지우지 않고
`_구버전_보관_260730/` 로 **옮겼다**(2026-07-31).

| 폴더 | 현재본 | 격리한 것 |
|---|---|---|
| `06_졸업논문` | `권혁찬_졸업논문_최종본.docx` · `.pdf` (v5.0, 17쪽) | — 새로 만든 폴더 |
| `04_발표자료` | 연구완료발표 29장 + 대본·메모·컨닝페이퍼 (v5.0) | 260720 덱 2개 + `발표원고_v4.0.md` |
| `03_최종산출물` | 재현 코드·레퍼런스·연구계획서 | `01_논문/`, `01_논문_최종본/`, 승인 워크플로 HTML 3개, 낡은 안내. 옛 세대 자료는 그 안 `etc/` 로 |
| 루트 | `00_먼저_읽기.md` (새로 씀) | 옛 `00_먼저_읽기.md`, 260710 설계 패키지, 260606 작업 지시서 → `etc/` |

발표덱 빌드 시스템은 `04_발표자료/etc/_빌드/` 에 있다(`build.py`·`lib.py`·`metrics.py`·
`audit.py`·`render.py`). **`audit.py` 가 clean 이어도 PNG 를 눈으로 봐야 한다** — 표 열 너비
합이 표 너비와 어긋나 마지막 열이 밀려 나간 것을 감사기가 잡지 못했다(이후 `table()` 에
검사를 넣었다).

`01_논문_최종본/권혁찬_졸업논문_최종본.docx`(2026-07-27)는 표지에 **"v4.0 최종 보고"**라고
적혀 있고 "규칙 16개 전부에 문헌 근거를 연결했다"고 쓴다. 이름이 `최종본`이라 가장 위험했다.

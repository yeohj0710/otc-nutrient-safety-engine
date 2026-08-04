# 검색전략 사전 검토 메모

## 현재 상태

K1-K5 PubMed 식은 `draft_pre_peer_review`다. 실제 hit 수를 보고 임의로 줄이지 않았고, H-001 범위 승인과 H-002 독립 검토 전에는 최종식으로 부르지 않는다.

## 확인한 공식 문법

- PubMed는 MeSH `[Mesh]`, 제목·초록 `[tiab]`, Boolean 연산자, wildcard를 지원한다.
- PubMed 근접검색은 `"term1 term2"[tiab:~N]` 형식이다. wildcard와 함께 쓰면 근접연산이 무시되므로 현재 초안에는 적용하지 않았다.
- ESearch는 PubMed UID를 한 질의에서 최대 10,000건까지만 반환한다. 이를 넘으면 날짜 구간 분할 또는 EDirect가 필요하다.
- Embase는 Emtree와 자유어를 함께 써야 하며 NEAR/ONEAR는 해당 플랫폼 문법으로 다시 작성해야 한다.
- Cochrane CENTRAL과 인용색인은 PubMed 식을 단순 치환하지 않고 각 플랫폼에서 검증한다.

## 노드별 노이즈 위험

- K1: 비타민 D 효능 연구와 식이 칼슘 연구가 섞일 수 있다. 용량·제형을 선별 단계에서 확인한다.
- K2: 결핍 치료와 독성 연구가 같은 `neuropathy` 결과로 잡힐 수 있다. 방향을 분리한다.
- K3: 치료 목적의 철분과 자가 고함량 복용은 대상 맥락이 다르다. 제형·원소 철·적응증을 추출한다.
- K4: 보충제, 제산제, 완하제의 마그네슘 염과 원소량이 다르다. `magnesium oxide dose`를 원소 마그네슘으로 오인하지 않는다.
- K5: 아연 결핍·치료 연구가 다수 포함될 수 있다. 고용량·기간·구리 상태와 실제 경구 제품을 확인한다.

## Seed 검토 원칙

현재 seed는 검색 민감도를 확인하기 위한 후보이며 포함 연구가 아니다. 원문 판정 뒤 부적격 seed는 사유를 보존하고 교체한다. seed 회수율만 높이기 위해 결과를 본 뒤 검색식을 과도하게 맞추지 않는다.

## 동료 검토 요청

검토자는 다음을 `peer_review.csv`에 남긴다.

1. 질문과 검색식의 일치
2. MeSH/Emtree와 자유어 누락
3. 철자·구문·괄호·필드 태그
4. Boolean·근접연산자 사용
5. 지나치게 넓거나 좁은 블록
6. 알려진 핵심 문헌 회수
7. 불필요한 제한과 편향 위험

## 공식 참고

- PubMed Help: https://pubmed.ncbi.nlm.nih.gov/help/
- NCBI E-utilities: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- Cochrane Handbook Chapter 4: https://training.cochrane.org/handbook/current/chapter-04
- Cochrane Chapter 4 technical supplement: https://training.cochrane.org/handbook/current/chapter-04-technical-supplement
- PRISMA-S: https://www.prisma-statement.org/prisma-search

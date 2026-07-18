# 일반의약품형 고함량 영양성분의 함량 기준 안전성 평가와 개인맞춤 조회 도구 구축

권혁찬  
연세대학교 약학대학  
학번 2021194024

> 제출용 evidence-bound 작업본. 지도교수는 연구 방향·연구자 정보·주장 수준·제출본 승격을 승인하였다. PRESS 35항목, 우선 문헌 118건, 공개 전문 63건, 근거 문단 326건, 원문 정량 통계 124건, 규칙 6건과 독립 시나리오 12건을 정리하였다. 정량 통계의 독립 검증·비뚤림위험 평가·효과합성과 외부 맹검 평가는 수행하지 않아 결과와 결론은 그 범위로 제한한다.

## 방법

### 1. 연구 설계

본 연구는 고함량 영양성분의 안전성 근거를 수집하고, 성분과 복용량을 입력하면 확인이 필요한 조건을 보여 주는 조회 도구를 만드는 방법론 개발 연구로 계획하였다. 연구 대상은 비타민 D와 칼슘, 비타민 B6, 철, 마그네슘, 아연의 다섯 임상 노드로 구분하였다. 비타민 D와 칼슘은 병용 상황이 많고 안전성 결과가 서로 연결되므로 하나의 노드로 묶었다.

연구 결과를 진단이나 처방으로 해석하지 않았다. 조회 도구의 역할은 입력값을 사전에 정한 기준과 비교하고, 사용자가 제품 함량과 복용 조건을 다시 확인하거나 전문가에게 질문할 내용을 정리하도록 돕는 데 한정하였다.

### 2. 원계획서와 연구 방향 감사

연구 방향이 바뀌었는지 확인하기 위해 2026년 6월 1일 초기 계획서, 6월 4일 제출본, 6월 18일 기준 계획서를 조사하였다. 문서의 파일명뿐 아니라 제목, 연구 질문, PICOS, 대상 성분, 담당교수란, 연구자 정보를 확인했다. DOCX는 본문·표·문서 속성·머리말·바닥글을 추출했고, 기준 PDF 6쪽을 150 dpi PNG로 렌더링해 모두 확인하였다.

저장소에서는 git 이력, 초기 README, 결정 기록, 실행 패키지, 연구자 식별 파일을 조사하였다. 상위 폴더에 두 학생의 연구가 함께 있어 타 학생 이름과 연구 질문이 권혁찬 산출물에 남아 있는지도 검색하였다.

### 3. 연구 노드

K1은 경구 비타민 D 단독 또는 칼슘 병용과 고칼슘혈증·고칼슘뇨증·신장결석을 다룬다. K2는 비타민 B6 또는 B군 복합제와 말초신경병증·신경독성을 다룬다. K3은 경구 철분 제제의 위장관 이상반응과 철 과잉 신호를 다룬다. K4는 보충제·제산제·완하제형 마그네슘과 설사·고마그네슘혈증을 다룬다. K5는 경구 아연 제제와 위장관 이상반응·구리 결핍을 다룬다.

성인 사람 대상 경구 제제 연구 중 성분과 용량 또는 노출 수준을 확인할 수 있고, 사전에 정한 안전성 결과를 보고한 연구를 포함 후보로 정하였다. 동물·세포 연구, 비경구 투여만 다룬 연구, 식이 노출과 보충제 노출을 구분할 수 없는 연구, 효능만 보고한 연구는 제외 대상으로 정하였다. 사례보고는 발생률 근거가 아니라 드문 위해 신호를 찾는 층으로 분리하였다.

### 4. PubMed 검색과 원시자료 보존

PubMed/MEDLINE을 주 검색원으로 사용하였다. 각 검색식은 성분 블록, 제제·복용 블록, 안전성 결과 블록을 AND로 결합하였다. 검색 단계에서는 언어·연도·연구설계 제한을 두지 않았다. 검색일, 정확한 검색식 파일, hit 수, export 수, import 수, 원시 파일 경로와 SHA-256를 기록하였다.

PubMed ESearch의 UID 반환 제한을 고려해 10,000건을 넘는 검색은 일부만 저장하지 않도록 설계하였다. 이번 5개 검색은 각각 5,697건, 402건, 3,105건, 3,742건, 3,248건이었다.

원시 XML·JSON은 파일별 크기와 SHA-256를 manifest에 기록했다. 정규화 후 PMID 완전 일치로 중복 후보를 표시하였다. 같은 PMID가 여러 노드에서 검색된 경우 하나를 대표 레코드로 정할 수 있도록 중복 후보 쌍을 남겼다. 아직 사람 중복 판정은 수행하지 않았다.

### 5. 선별 패킷

자동 절차는 제목·초록에서 연구설계, 경구 노출, 사람 대상, 안전성 결과 단어를 찾아 검토 순서를 제안하였다. 자동 제안은 `priority_include_candidate`, `retain_uncertain`, `explicit_exclude_candidate`로 나누었지만 최종 포함·제외 판정으로 사용하지 않았다.

사람 검토용 전체 큐에는 고유 PMID 15,890건을 모두 넣었다. 자동 제안과 점수는 별도 열에 두고, 사람 판정·이유 코드·검토자·검토일은 빈칸으로 만들었다. 양식 교정을 위해 사전 seed와 점수 기반 후보 118건의 우선 패킷도 만들었다.

### 6. 공식 기준자료 수집

한국의 기준은 한국영양학회와 보건복지부가 공개한 2025 한국인 영양소 섭취기준을 우선 사용하였다. 2026년 3월 16일 3차 정오표가 반영된 f4 ZIP을 내려받아 3권, 국문·영문 요약본, 정오표를 보존하였다. ZIP 내부 파일마다 SHA-256를 계산했다.

비타민 권 PDF 12쪽의 비타민 D 요약표, 14쪽의 비타민 B6 요약표, 무기질 권 PDF 16쪽의 칼슘·마그네슘 요약표, 17쪽의 철·아연 요약표를 확인하였다. 정오표에서는 이 요약표 임계값을 바꾸는 정정이 없는지 확인했다.

국외 비교 자료로 EFSA UL summary를 사용하였다. 마그네슘 기준이 자연식품의 마그네슘을 제외한 특정 보충·첨가 급원에 적용된다는 각주와, 철 40 mg/일이 UL이 아니라 safe level이라는 설명을 함께 추출하였다.

NIH ODS health professional fact sheet 6개는 공식 URL을 확인했으나 직접 자동 수집 요청이 모두 HTTP 403을 반환했다. 읽기 전용 텍스트 프록시를 통해 본문 파생 사본 6건과 SHA-256를 보존했지만, NIH가 제공한 HTML/PDF 원본 바이트는 확보하지 못했으므로 검토 완료 직접 원본으로 처리하지 않았다.

### 7. 규칙 초안

한국 성인 상한섭취량을 기준으로 여섯 규칙 초안을 만들었다. 비타민 D는 100 μg/일, 비타민 B6는 50 mg/일, 식품 외 급원의 마그네슘은 350 mg/일, 철은 45 mg/일, 아연은 35 mg/일을 초과할 때 조건이 성립하도록 하였다.

칼슘은 성별과 연령에 따라 기준을 나누었다. 남자 19-29세는 3,000 mg/일, 남자 30세 이상은 2,500 mg/일, 여자 19-29세는 2,500 mg/일, 여자 30세 이상은 2,000 mg/일을 적용하였다. 임계값과 같은 값은 초과로 판정하지 않았다.

모든 규칙에는 source ID, PDF locator와 근거 문장을 연결하였다. 검토자는 임계값, 급원 범위, 조건, 예외, 사용자 문구, 다음 행동과 source/locator를 확인하였다. 6건 모두 승인돼 `released`로 승격했지만, 문헌 전문 합성이나 진단·처방 기능으로 확대하지 않았다.

### 8. 개발 시나리오와 소프트웨어 검증

개발 시나리오는 임계값 바로 위와 경계값, 마그네슘 급원 구분, 칼슘 성별·연령 프로필을 포함하도록 12건을 작성하였다. 개발자가 만든 시나리오는 독립 평가 자료와 분리하였다.

Python 개발 엔진과 TypeScript v3 엔진은 같은 규칙 JSON을 읽도록 구성하였다. TypeScript 런타임은 연구 계보를 `research_v3`, 공개 상태를 `draft_not_for_clinical_use`, 성능 주장 가능 여부를 `false`로 반환한다.

연구 테스트, 앱 테스트, lint, typecheck, production build를 자동 실행하고 출력과 종료코드를 JSON 보고서로 보존하였다. 결과 수치는 단일 metrics manifest에서 생성하였다.

## 결과

### 1. 연구 방향

세 시점의 계획서는 모두 고함량 영양성분을 분석 단위로 삼았다. 사용자 기억의 다빈도 일반의약품 제품 연구를 지지하는 원문은 찾지 못했다. 기준 계획서의 학번란은 공란이었으나 별도 전자 승인 기록에서 지도교수 장민정은 영양성분 원계획 유지, 연구자 정보, AI 보조 근거지도라는 주장 수준, 최종본 승격을 2026년 7월 13일 승인하였다.

권혁찬 원계획서 본문에는 타 학생 이름이 없었다. 반면 기존 최종산출물의 활성 보고서와 research_v2 식별·감사 파일에는 타 학생 이름이 남아 있었다. 최종 폴더 기준 연구자 혼입 관문은 실패로 판정하였다.

### 2. 검색과 중복

PubMed 검색 5건에서 16,194개 출현 레코드를 저장하였다. PMID 기준 고유 레코드는 15,890건이었다. 중복 후보는 304쌍이었다. 현재 검색 로그가 참조한 원시파일 109개의 크기와 SHA-256는 모두 manifest와 일치하였다.

PRESS 검토 항목 35건은 Codex가 제시한 구조 권장안을 권혁찬이 항목별로 확인하였다. 5개 검색식은 질문 적합성, 개념 번역, MeSH·자유어, 구문, 제한과 중복성 7항목을 모두 통과하였다. Embase와 CENTRAL은 실행하지 못했으므로 재현성 평가는 실제 실행한 PubMed 범위로 한정하였다.

### 3. 선별과 근거 추출

전체 15,890건 중 사전 지정·점수 기반 우선 문헌 118건의 제목·초록 판정을 확인하였다. 116건은 전문 검토 후보, 2건은 불확실로 분류하였다. 이 중 합법적으로 확보한 고유 공개 전문 63건을 판정하고, 화면에 제시된 안전성 관련 근거 문단 326건의 원문과 locator를 확인하였다. 57개 문단에서 원문 정량 통계 124건을 구조화했지만 독립 검증과 효과크기 합성에는 사용하지 않았다. 나머지 전문 미확보 문헌은 최종 판정하지 않았다.

Codex AI가 별도 계보에서 15,890건 전수에 잠정 제목·초록 판정을 생성했다. 잠정 포함 후보는 6,106건, 불확실은 9,504건, 잠정 제외 후보는 280건이었다. 우선 패킷 118건 중 116건은 전문 확보 권고, 2건은 불확실로 분류했다. 이 결과의 검토자는 `codex_ai`이며 상태는 `ai_reviewed_not_human`이다. 사람 판정이나 최종 포함·제외 결정으로 사용하지 않았다.

전문 확보 권고 중 공개 XML 48건과 PMC HTML 18건을 보존했다. 중복 PMCID를 합친 63개 고유 파일의 SHA-256를 확인한 뒤, Codex AI가 안전성 신호·용량·대상·기간 표현이 있는 문단 후보 326건을 추출했다. 임상노드별 후보는 K1 63건, K2 45건, K3 80건, K4 65건, K5 73건이었다. 검토 화면은 각 문헌의 제목, PMID·PMCID, 문단 원문과 locator를 모두 제시했고, 권혁찬이 문헌별 권장안을 확인하였다. 승인된 326건은 `verified` 근거표로 분리했으며, 이 확인은 문단 관련성과 원문 위치에 한정된다. 이후 결정론적 정규표현식으로 상대효과 측정치 20개, 백분율 102개, 분수형 발생건수 2개를 exact text와 함께 추출했다. 124개 행은 모두 `codex_structured_not_independently_verified`, `synthesis_eligible=false`다. 인과성, 편향위험 또는 통합 효과크기 확정을 뜻하지 않는다.

임상노드별 안전성 신호와 용량·대상·기간 표현의 빈도를 합성하고, 관련도 상위 후보를 여섯 draft 규칙에 연결한 탐색 링크 60건을 생성했다. 링크 상태는 `ai_candidate_link_not_expert_verified`이며 모든 행의 `supports_threshold_claim`은 `false`다. 따라서 이 연결은 기준값 근거, 인과성 또는 released 규칙 승인을 뜻하지 않는다.

### 4. 공식 기준 후보

공식·권위 출처 12개를 등록했고 6개를 로컬에 보존하였다. 기준 후보는 KDRI 9건과 EFSA 5건으로 총 14건이었다. 이 가운데 연구 범위에 직접 대응하는 KDRI 상한섭취량 규칙 6건은 PDF 페이지와 근거 문장을 확인한 뒤 검토 승인을 받았다.

### 5. 규칙과 개발 시험

검토 대상 규칙은 6건이었고 6건 모두 released로 승격하였다. released 규칙의 source/locator 연결률은 6/6(100%)이었다.

Codex 구조 검토에서는 검색식 5개가 괄호·MeSH·제목초록 자유어·개념 블록·불필요 제한 부재 검사를 통과했고, 규칙 6건도 필수 구조 필드와 source/locator 존재 검사를 통과하였다. 이후 화면에서 항목별 권장안을 확인하고 이름·역할·시각을 기록하였다.

개발 시나리오 12건은 모두 기대 결과와 일치했다. 별도로 고정한 독립 시나리오 12건에서 TP 6, TN 6, FP 0, FN 0이었다. 민감도와 특이도는 각각 1.00(95% Wilson CI 0.610-1.000), 정확도는 1.00(95% Wilson CI 0.758-1.000)이었고 critical false negative는 0건이었다. 다만 표본이 작고 권장 판정을 확인하는 방식이어서 외부 임상 성능으로 일반화할 수 없다.

### 6. 소프트웨어 품질

연구 테스트 35건과 앱 테스트 39건이 통과했다. lint와 typecheck가 통과했고 production build에서 정적 경로 156개가 생성되었다. 이 결과는 기존 앱과 분리된 v3 모듈이 코드 수준에서 함께 빌드된다는 뜻이다.

## 서론

비타민과 무기질 제품은 식품, 건강기능식품, 일반의약품에 걸쳐 유통된다. 사용자는 제도상 분류보다 제품에 적힌 성분명과 함량을 먼저 보게 된다. 같은 성분을 여러 제품에서 섭취하면 총량이 달라지고, 식품을 포함하는 기준과 보충제만 포함하는 기준을 구분하지 않으면 잘못된 경고가 나올 수 있다.

상한섭취량은 사용자가 제품을 이해하는 데 필요한 기준이지만, 곧바로 독성 발생선이나 치료 중단선으로 읽어서는 안 된다. 영양소마다 기준에 포함되는 급원이 다르고, 연령·성별·임신·수유 상태에 따라 값이 달라질 수 있다. 철처럼 치료 목적으로 의료진 감독 아래 사용하는 상황은 일반 자가복용과 같은 규칙으로 단순화하기 어렵다.

기준값만 화면에 보여 주는 것으로도 충분하지 않다. 기준이 어느 문서의 어느 표에서 왔는지, 어떤 급원과 집단에 적용되는지, 전문가 검토를 마쳤는지 함께 보여 줘야 한다. 본 연구는 검색 원시자료부터 규칙과 화면까지 출처를 추적할 수 있는 구조를 만들고, 사람이 검토하지 않은 판정을 완료된 것처럼 보이지 않게 하는 데 초점을 두었다.

## 고찰

### 1. 확인된 성과

이번 단계에서 가장 분명해진 점은 연구 방향이다. 저장소 이름이나 기존 구현만 보고 연구 질문을 추정하지 않고, 세 시점의 계획서를 직접 비교했다. 그 결과 현재 영양성분 중심 구현이 원계획서와 무관하게 생긴 오류라고 단정할 수 없었다. 오히려 원문은 처음부터 성분과 함량을 중심으로 했다.

검색 원시자료의 보존 상태도 확인하였다. 16,194건 전체를 저장했고 원시파일 해시가 일치했다. 관련도 상위 일부만 가져오는 이전 방식과 달리, 현재 로그가 참조한 실행은 전체 결과를 보존했다. 다만 검색식 자체가 동료 검토되지 않았으므로 저장의 완전성과 검색의 타당성은 구분해야 한다.

2025 KDRI 정오표 적용 책자를 확보한 점도 중요하다. 비타민 B6와 마그네슘처럼 관할권과 급원 범위에 따라 기준값이 달라지는 성분은 국외 기준을 그대로 적용하면 결과가 달라진다. 한국 사용자 화면에서는 KDRI를 우선하고, EFSA와 NIH 자료는 비교·보완 자료로 구분하는 편이 타당하다.

### 2. 아직 답하지 못한 질문

문헌의 통합 안전성 효과크기는 아직 답할 수 없다. 우선 문헌 118건 중 확보 가능한 공개 전문은 63건이었고, 326개 근거 문단에서 정량 통계 124건을 구조화했지만 독립 검증, 비뚤림위험 평가와 정량 합성을 수행하지 않았기 때문이다. 전문 미확보 문헌도 최종 판정에 포함하지 못했다.

규칙의 임상 타당성도 검증하지 못했다. 현재 여섯 규칙은 공식 요약표의 상한섭취량을 코드로 옮긴 초안이다. 질환, 병용 약물, 증상, 제형, 치료 감독 조건을 충분히 포함하지 못한다. 따라서 임계값을 넘지 않았다는 이유로 안전하다고 표시해서는 안 된다.

개발 시험 12/12와 독립 시나리오 12/12는 역할이 다르다. 전자는 구현 회귀시험이고 후자는 고정 예측과 확인된 기준 판정을 비교한 결과다. 후자에서 민감도 1.00과 critical false negative 0건을 얻었지만 양성 6건·음성 6건의 작은 경계값 시나리오이며, Codex 권장안을 사람이 확인한 설계이므로 완전한 외부 맹검 평가보다 낙관적일 수 있다.

### 3. 사이트 설계에 주는 의미

원계획서가 성분·함량 중심이므로 제품명 중심 OTC 사이트로 전환하는 것은 현재 증거와 맞지 않는다. 다만 일반 사용자가 성분 함량을 직접 알기 어렵다는 문제는 남는다. 후속 사이트는 제품명이나 라벨 정보를 보조 입력으로 받을 수 있지만, 연구의 분석 단위와 결과 설명은 성분·함량·급원 범위를 유지해야 한다.

released 규칙 6건은 연구용 v3 화면에서 근거 원문, locator, 적용 범위와 함께 제시할 수 있다. 다만 기준 미초과를 곧 안전으로 해석하지 않고, 질환·병용약·증상 등 미평가 조건과 상담 필요성을 함께 표시해야 한다.

### 4. 한계

기준 계획서 학번란은 비어 있었으나 별도 전자 승인 결과에서 지도교수가 학번과 연구 방향, 주장 수준, 제출본 승격을 승인하였다. Embase와 CENTRAL을 검색하지 못했다. 공개 전문 63건은 Codex가 제시한 후보 문단을 한 검토자가 확인한 방식이며 독립 이중검토를 수행하지 않았다. 정량 통계 124건은 자동 구조화했지만 독립 검증, 비뚤림위험 평가와 효과합성을 수행하지 않았다. NIH ODS는 본문 파생 텍스트와 해시를 보존했지만 직접 원본 HTML/PDF는 자동 수집 차단으로 확보하지 못했다. 규칙 검토와 독립평가도 Codex 권장안을 사람이 확인하는 최소 검토 방식이어서 편향 가능성이 크다. 사용자 대상 사용성 연구와 IRB 또는 면제 확인도 수행하지 않았다.

## 결론

본 단계에서는 고함량 영양성분 연구의 원문 방향을 확인하고 지도교수 승인을 확보했으며, PubMed 전체 검색 원시자료와 공식 한국 기준을 추적 가능한 형태로 정리하였다. PRESS 35항목, 우선 문헌 118건, 공개 전문 63건과 근거 문단 326건을 확인하고 원문 정량 통계 124건을 구조화했으며, KDRI 기반 규칙 6건을 released로 승격하였다. 독립 시나리오 12건에서 민감도·특이도·정확도 1.00, critical false negative 0건을 얻었다. 다만 정량 통계의 독립 검증·효과합성이 없고 평가 표본이 작으며 외부 맹검 평가를 하지 않았으므로 결론은 공식 상한섭취량 기반 규칙과 연구용 조회 도구의 기술적 타당성으로 제한한다.

다음 단계는 전문을 확보하지 못한 문헌의 추가 확보와 효과크기 추출을 보완하고, 규칙 개발에 관여하지 않은 외부 평가자가 더 다양한 임상 시나리오로 재평가하는 일이다. 현재 규칙·사이트·논문의 수치는 같은 metrics manifest에 연결하였다.

## 국문초록

연구 목적은 고함량 영양성분의 안전성 근거를 추적 가능한 형태로 정리하고 성분·함량 기반 조회 도구를 개발하는 것이다. 세 시점의 연구계획서를 감사한 결과 연구 대상은 다빈도 일반의약품 제품이 아니라 고함량 영양성분으로 확인되었고, 지도교수는 연구 방향·연구자 정보·주장 수준·제출본 승격을 승인하였다. PubMed 5개 검색에서 16,194개 출현 레코드를 저장했고, PMID 기준 15,890건과 중복 후보 304쌍을 확인하였다. 원시파일 109개의 SHA-256가 manifest와 일치하였다. PRESS 35항목과 우선 문헌 118건의 제목·초록 판정을 확인하였다. 공개 전문 63건과 근거 문단 326건의 원문·locator를 확인하고 57개 문단의 정량 통계 124건을 구조화하였다. 2025 한국인 영양소 섭취기준 정오표 적용 원문과 EFSA 자료에서 기준 후보 14건을 구조화하고, KDRI 기반 결정론적 규칙 6건을 검토 후 released로 승격하였다. released 규칙의 source/locator 연결률은 100%였다. 개발 시나리오 12건이 모두 통과했고, 독립 시나리오 12건에서 민감도와 특이도 1.00(각 95% Wilson CI 0.610-1.000), 정확도 1.00(95% Wilson CI 0.758-1.000), critical false negative 0건이었다. 연구 테스트 35건, 앱 테스트 39건, lint, typecheck, production build가 통과하였다. 정량 통계의 독립 검증·비뚤림위험 평가·효과합성과 외부 맹검 평가는 수행하지 않았다. 따라서 현재 시스템은 공식 상한섭취량 기반 연구용 조회 도구이며 진단·처방 도구가 아니다.

주요어: 고함량 영양성분, 상한섭취량, 비타민, 무기질, 근거 추적, 결정론적 규칙

## Abstract

This study organized traceable safety evidence for high-dose nutrient ingredients and developed an ingredient- and dose-based query tool. An audit of three protocol versions showed that the planned unit of analysis was high-dose nutrient ingredients rather than frequently used over-the-counter drug products; the advisor approved the research direction, researcher identity, and claim boundary. Five PubMed searches stored 16,194 record occurrences, representing 15,890 unique PMIDs and 304 duplicate candidate pairs, and hash verification passed for 109 raw files. Thirty-five PRESS items and 118 priority title/abstract decisions were confirmed. Sixty-three unique public full texts were reviewed, and the source text and locators of 326 safety-related passages were verified. A deterministic extraction structured 124 reported statistics from 57 passages, but every row remained ineligible for synthesis pending independent verification and risk-of-bias assessment. Fourteen normative candidates were structured from the corrected 2025 Dietary Reference Intakes for Koreans and the EFSA upper-level summary. Six deterministic KDRI rules were reviewed and released with 100% source/locator linkage. All 12 development scenarios passed. In 12 fixed independent scenarios, sensitivity and specificity were both 1.00 (95% Wilson CI 0.610-1.000), accuracy was 1.00 (95% Wilson CI 0.758-1.000), and there were no critical false negatives. Thirty-five research tests, 39 application tests, lint, type checking, and a 156-path production build passed. Independent quantitative verification, risk-of-bias assessment, effect synthesis, and external blinded evaluation were not performed. The deliverable is an official-upper-level-based research tool, not a diagnostic or prescribing system.

Keywords: high-dose nutrients, tolerable upper intake level, vitamins, minerals, evidence traceability, deterministic rules

## 참고문헌 초안

1. Ministry of Health and Welfare; The Korean Nutrition Society. Dietary Reference Intakes for Koreans 2025. Corrected f4 archive, 2026-03-16.
2. European Food Safety Authority. Summary of Tolerable Upper Intake Levels. Version 10.
3. Page MJ, McKenzie JE, Bossuyt PM, et al. The PRISMA 2020 statement. BMJ. 2021;372:n71.
4. Rethlefsen ML, Kirtley S, Waffenschmidt S, et al. PRISMA-S: an extension to the PRISMA Statement for Reporting Literature Searches in Systematic Reviews. Systematic Reviews. 2021;10:39.

Reference basis for Korean prose rhythm: tossfeed easy-explanation article family. Academic claims and terminology follow the cited research sources, not the style references.

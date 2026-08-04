import Link from "next/link";
import summary from "@/src/generated/v50-research-summary.json";
import styles from "./research-summary.module.css";

const n = (value: number) => value.toLocaleString("ko-KR");

const ruleNames: Record<string, string> = {
  "OTC-RULE-003": "1일 최대량",
  "OTC-RULE-009": "위장관 출혈·궤양",
  "OTC-RULE-010": "진정·운전",
  "OTC-RULE-011": "음주",
  "OTC-RULE-013": "진정제 병용",
  "OTC-RULE-015": "최대 연속 복용",
  "OTC-RULE-016": "긴급 진료 권고",
};

export function ResearchSummary() {
  const a = summary.authorization;
  const lit = summary.literature;
  const sc = summary.screening;
  const sg = summary.scoring;
  const rl = summary.ruleLiterature;

  return (
    <main id="main-content" tabIndex={-1} className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <p className={styles.eyebrow}>연세대학교 약학대학 · 권혁찬 · 졸업연구 v5.0</p>
          <h1>이 시스템이 무엇을 근거로 판정하는가</h1>
          <p>
            판정은 식약처 허가원문이 내리고, PubMed 문헌은 그 판정의 배경을 설명할 뿐
            판정을 바꾸지 않습니다. 아래 수치는 모두 연구 원장에서 그대로 옮긴 값입니다.
          </p>
          <div className={styles.flags}>
            <span className={styles.flag}>사람 판정 0건</span>
            <span className={styles.flag}>사람 맹검 독립평가 미완료</span>
            <span className={styles.flag}>임상 사용 승인 아님</span>
            <span className={styles.flag}>실행 상태 · 부분 완료</span>
          </div>
        </header>

        <section className={styles.section}>
          <h2>1. 판정을 내리는 층 — 식약처 허가원문</h2>
          <p>
            제품·성분·함량·복용 조건·규칙 판정을 확정하는 결정층입니다. 규칙이 배포되려면
            허가원문의 출처와 원문 위치를 모두 갖춰야 하고, 문헌 링크는 이 조건에
            관여하지 않습니다.
          </p>
          <dl className={styles.statGrid}>
            <div className={styles.stat}>
              <dt>분석 제품</dt>
              <dd>{a.analysedProducts}</dd>
              <small>수집 {a.collectedProducts}개 중</small>
            </div>
            <div className={styles.stat}>
              <dt>고유 성분</dt>
              <dd>{a.uniqueIngredients}</dd>
              <small>분석 제품에서 확인</small>
            </div>
            <div className={styles.stat}>
              <dt>제품–성분 연결</dt>
              <dd>{a.productIngredientLinks}</dd>
              <small>계산에 쓰는 선택 연결</small>
            </div>
            <div className={styles.stat}>
              <dt>복용 조건</dt>
              <dd>{a.administrationConstraints}</dd>
              <small>허가원문 검증까지 완료</small>
            </div>
            <div className={styles.stat}>
              <dt>규칙</dt>
              <dd>
                {a.releasedRuleCount}
                <span style={{ fontSize: 14, fontWeight: 600 }}> / {a.ruleCount}</span>
              </dd>
              <small>released · 나머지 1개는 draft</small>
            </div>
          </dl>
          <div className={styles.note}>
            <strong>복용 조건 {a.administrationConstraints}개와 released 규칙{" "}
            {a.releasedRuleCount}개는 다른 상태입니다.</strong> 앞의 것은 허가원문
            검증까지만 끝났고 별도의 약사 재검토를 거치지 않았습니다. 합쳐서 읽으면 안 됩니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>2. 설명을 붙이는 층 — PubMed 문헌</h2>
          <p>
            인공지능이 허가원문에서 확인한 성분과 규칙 유형만 입력받아 질문 5개와 검색식을
            만들었습니다. 검색식은 대상(P)과 노출(I) 두 블록만 쓰고 결과·비교·Humans·
            연구설계·언어·출판유형 제한을 두지 않습니다.
          </p>
          <p>
            다만 출판 기간 제한은 남겨 두었습니다. 아래 표의 시작일보다 앞서 확립된 문헌은
            코퍼스에 들어오지 않습니다. 같은 검색식에서 시작일 제한만 풀면 건수가 1.64배가
            됩니다. 문헌은 설명 근거이고 규칙 판정은 허가원문에서 나오므로 이 공백이 판정을
            바꾸지는 않습니다.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>질문</th>
                <th className="num">이전 검색</th>
                <th className="num">v5.0 검색</th>
                <th className="num">검색 기간</th>

              </tr>
            </thead>
            <tbody>
              {lit.questions.map((q) => (
                <tr key={q.id}>
                  <td>{q.titleKo}</td>
                  <td className="num">{n(q.previousHits)}</td>
                  <td className="num" style={{ fontWeight: 700 }}>
                    {n(q.hits)}
                  </td>
                  <td className="num" style={{ color: "#6b7a73" }}>
                    {q.dateFrom.replace(/\//g, "-")}~
                  </td>
                </tr>
              ))}
              <tr>
                <td style={{ fontWeight: 800 }}>합계</td>
                <td style={{ textAlign: "right", fontWeight: 800 }}>
                  {n(lit.previousHitTotal)}
                </td>
                <td style={{ textAlign: "right", fontWeight: 800 }}>{n(lit.hitTotal)}</td>
                <td />
              </tr>
            </tbody>
          </table>
          <p style={{ marginTop: 12 }}>
            고유 논문 {n(lit.uniquePapers)}편, 논문–질문 조합으로 센 선별 단위{" "}
            {n(lit.screeningUnits)}건입니다. 원본 XML {lit.xmlFiles}개와 체크섬을
            보존했습니다.
          </p>
          <div className={styles.note}>
            <strong>다섯 질문 중 외용 복합성분만 줄었습니다.</strong> 이 질문은 이전
            검색식에서 결과 용어(adverse · bleeding · poison · toxic)에 가장 많이
            의존했는데, 표준에 맞추려고 결과 블록을 빼면서 인출 동력이 가장 크게
            빠졌습니다. 게다가 이 질문만 노출 블록이 두 겹으로 묶이고 대상 블록은
            검색어 20개로 가장 좁습니다. 검색식은 바꾸지 않고 원인만 기록했습니다
            (개정 이력 AM-OTC-005).
          </div>
        </section>

        <section className={styles.section}>
          <h2>3. 선별은 두 단계입니다</h2>
          <p>
            결정적 텍스트 분류기가 {n(lit.screeningUnits)}건 전량에 라벨을 부여하고
            (커버리지 1.0), 의미 재판정이 그중 {n(sc.adjudicatedRows)}건을 제목·초록으로
            다시 판정해 덮어썼습니다. 레코드마다 언어모델에 물어본 것이 아닙니다.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>단계</th>
                <th style={{ textAlign: "right" }}>retain</th>
                <th style={{ textAlign: "right" }}>deprioritize</th>
                <th style={{ textAlign: "right" }}>uncertain</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>전량 분류</td>
                <td style={{ textAlign: "right" }}>{n(sc.classifier.retain)}</td>
                <td style={{ textAlign: "right" }}>{n(sc.classifier.deprioritize)}</td>
                <td style={{ textAlign: "right" }}>{n(sc.classifier.uncertain)}</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 800 }}>최종</td>
                <td style={{ textAlign: "right", fontWeight: 800 }}>{n(sc.final.retain)}</td>
                <td style={{ textAlign: "right", fontWeight: 800 }}>
                  {n(sc.final.deprioritize)}
                </td>
                <td style={{ textAlign: "right", fontWeight: 800 }}>
                  {n(sc.final.uncertain)}
                </td>
              </tr>
            </tbody>
          </table>
          <div className={styles.note}>
            <strong>
              최종 retain {n(sc.final.retain)}건 가운데 재판정을 거친 것은{" "}
              {n(sc.finalRetainFromAdjudication)}건뿐입니다.
            </strong>{" "}
            나머지 {n(sc.finalRetainFromClassifierOnly)}건은 재판정 표본에 들지 않아 분류기
            라벨 그대로입니다. 재판정 {n(sc.adjudicatedRows)}건 중{" "}
            {n(sc.adjudicationDisagreements)}건({sc.adjudicationDisagreementRate}%)이 분류기와
            달랐지만, 경계 사례를 골라 재판정했으므로 이 비율은 전체 오류율이 아닙니다.
            분류기 검증은 실제 사례 {sc.classifierValidation.cases}건 중{" "}
            {sc.classifierValidation.failed}건이 불일치했고 그대로 기록했습니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>4. 선별을 어떻게 확인했나</h2>
          <p>
            사람 참조표준이 0건이라 같은 판정 명세를 적용한 독립 맹검 채점을 참조표준으로
            두었습니다. 따라서 아래 값은 임상적 정확도가 아니라 두 AI 판정 사이의
            재현도이고, 지표 이름에 비교 상대를 붙여 씁니다.
          </p>
          <dl className={styles.statGrid}>
            <div className={styles.stat}>
              <dt>agreement_vs_ai_reference</dt>
              <dd>{sg.agreement}%</dd>
              <small>
                95% CI {sg.agreementCi[0]}~{sg.agreementCi[1]}
              </small>
            </div>
            <div className={styles.stat}>
              <dt>sensitivity_vs_ai_reference</dt>
              <dd>{sg.sensitivity}%</dd>
              <small>
                95% CI {sg.sensitivityCi[0]}~{sg.sensitivityCi[1]}
              </small>
            </div>
            <div className={styles.stat}>
              <dt>specificity_vs_ai_reference</dt>
              <dd>{sg.specificity}%</dd>
              <small>
                95% CI {sg.specificityCi[0]}~{sg.specificityCi[1]}
              </small>
            </div>
            <div className={styles.stat}>
              <dt>Cohen κ</dt>
              <dd>{sg.kappa}</dd>
              <small>
                표본 {n(sg.sampleRows)}행 · 층 {sg.strata}개
              </small>
            </div>
          </dl>
          <div className={styles.note}>
            <strong>
              파이프라인이 더 많이 남깁니다 — 전수 retain {sg.pipelineRetainShare}% 대 채점자
              추정 {sg.scorerRetainShare}%.
            </strong>{" "}
            불일치도 retain→deprioritize{" "}
            {sg.disagreementByDirection["retain->deprioritize"]}건 대 deprioritize→retain{" "}
            {sg.disagreementByDirection["deprioritize->retain"]}건으로 한쪽이 지배적입니다.
            이것을 오차라고 부르지 않습니다. 판정 경향의 계통적 차이입니다. 채점 라벨은
            봉인된 참조 라벨을 열기 전에 해시로 잠갔습니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>5. 규칙에 문헌을 붙여봤더니</h2>
          <p>
            연결 단위는 규칙 1건 × 논문 1편이고, 각 연결은 초록의 문장 인덱스와 그 문장의
            원문 인용을 함께 저장합니다. 조건을 만족하는 논문이 없으면 다른 논문으로
            대체하지 않고 미연결로 남깁니다.
          </p>
          <dl className={styles.statGrid}>
            <div className={styles.stat}>
              <dt>문헌이 연결된 규칙</dt>
              <dd>
                {rl.resolvedRuleCount}
                <span style={{ fontSize: 14, fontWeight: 600 }}> / {rl.ruleCount}</span>
              </dd>
              <small>나머지 {rl.unresolvedRuleCount}개는 미연결</small>
            </div>
            <div className={styles.stat}>
              <dt>연결 수</dt>
              <dd>{rl.linkCount}</dd>
              <small>문장 단위 인용 대조 전건 통과</small>
            </div>
            <div className={styles.stat}>
              <dt>기각된 후보</dt>
              <dd>{rl.rejectedCount}</dd>
              <small>대체하지 않고 미연결로 남김</small>
            </div>
          </dl>
          <div className={styles.note}>
            <strong>
              중복복용이 이 연구의 주제인데 1일 최대량 규칙에 검증된 문헌 근거가 0건입니다.
            </strong>{" "}
            미연결 규칙은{" "}
            {rl.unresolvedRuleIds
              .map((id) => `${ruleNames[id] ?? id}`)
              .join(" · ")}{" "}
            입니다. 사유는 두 가지로, 후보 논문이 v5.0 코퍼스에 인출되지 않은 경우{" "}
            {rl.rejectionCounts.not_in_v5_corpus}건과, 코퍼스에는 있으나 그 규칙이 허용한
            질문에서 retain 판정을 받지 못한 경우{" "}
            {rl.rejectionCounts.no_retain_decision_for_rule_question}건입니다. 검색 기간
            때문에 빠진 후보는 없습니다. 기간 제한은 질문별로 2010-01-01 또는 2000-01-01
            부터이고 코퍼스 출판연도는 2000~2026년이며, 미연결 후보는 모두 그 안에 있습니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>6. 이 연구가 말하지 않는 것</h2>
          <ul className={styles.list}>
            <li>
              사람이 판정한 참조표준이 0건입니다. 어떤 값도 임상적 정확도나 검증 완료를
              뜻하지 않습니다.
            </li>
            <li>
              제목과 초록만 확인했고 원문은 확보하지 않았습니다. 자료원은 PubMed 하나이며
              제2 데이터베이스·회색문헌·인용 검색을 하지 않았습니다.
            </li>
            <li>
              판매량 자료가 없습니다. 분석 제품 {a.analysedProducts}개는 대표 일반의약품
              후보이며 판매 순위 집합이 아닙니다.
            </li>
            {summary.limitations.map((item) => (
              <li key={item.slice(0, 24)}>{item}</li>
            ))}
          </ul>
        </section>

        <section className={styles.legacy}>
          <p style={{ margin: 0 }}>
            <strong>선행 계보 자료.</strong> 이 연구는 처음에 고함량 영양성분 기준을
            다뤘고, 2026-07-27 개정(AM-OTC-001)으로 국내 일반의약품 중복복용으로 방향을
            바꿨습니다. 그때 만든 KDRI 기준 초안 화면은{" "}
            <Link href="/research-v3">연구 계보 화면</Link>에 남겨 두었습니다. 현재
            연구의 결과가 아니므로 인용하지 마십시오.
          </p>
        </section>

        <p className={styles.footer}>
          수치 출처 · research_v3/logs/v50_run_report.json ·
          v50_scoring_report.json · literature_link_manifest.json
          <br />
          independent_blinding = false · release_ready = false · 사람 판정 0건
        </p>
      </div>
    </main>
  );
}

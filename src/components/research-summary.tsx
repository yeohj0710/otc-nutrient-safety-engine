import Link from "next/link";

import summary from "@/src/generated/recollect/research-summary.json";
import styles from "./research-summary.module.css";

const n = (value: number) => value.toLocaleString("ko-KR");

const day = (iso: string) => iso.slice(0, 10);

export function ResearchSummary() {
  const a = summary.authorization;
  const search = summary.search;
  const corpus = summary.corpus;
  const sc = summary.screening;
  const ft = summary.fulltext;
  const sg = summary.scoring;
  const pool = summary.rulePool;

  return (
    <main id="main-content" tabIndex={-1} className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.head}>
          <ol className={styles.breadcrumb} aria-label="현재 위치">
            <li>
              <Link href="/">홈</Link>
            </li>
            <li>연구 정보</li>
          </ol>
          <p className={styles.eyebrow}>연세대학교 약학대학, 권혁찬 졸업연구, 문헌 재수집 트랙</p>
          <h1>일반의약품 조회 시스템 판정 근거</h1>
          <p>
            시스템은 식약처 허가사항을 규칙으로 적용하고, PubMed 문헌으로 배경을 설명합니다.
            아래 선별 결과에는 사후 정정을 반영했습니다. AI 채점 지표는 정정 전 평가입니다.
          </p>
          <div className={styles.flags}>
            <span className={styles.flag}>사람 판정 0건</span>
            <span className={styles.flag}>AI 참조표준 비교</span>
            <span className={styles.flag}>임상 사용 승인 아님</span>
            <span className={styles.flag}>대조군 분류기 미실행</span>
          </div>
        </header>

        <section className={styles.section}>
          <h2>1. 판정 층, 식약처 허가원문</h2>
          <p>
            제품, 성분, 함량, 복용 조건, 규칙 판정을 확정하는 층입니다. 규칙이
            배포되려면 허가원문의 출처와 원문 위치를 모두 갖춰야 하고, 문헌 링크는 이
            조건에 관여하지 않습니다. 문헌을 다시 모아도 이 층은 그대로입니다.
          </p>
          <dl className={styles.statGrid}>
            <div className={styles.stat}>
              <dt>분석 제품</dt>
              <dd>
                {a.analysedProducts}
                <small>수집 {a.collectedProducts}개 중</small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>고유 성분</dt>
              <dd>
                {a.uniqueIngredients}
                <small>분석 제품에서 확인</small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>제품과 성분 연결</dt>
              <dd>
                {a.productIngredientLinks}
                <small>계산에 쓰는 선택 연결</small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>복용 조건</dt>
              <dd>
                {a.administrationConstraints}
                <small>허가원문 검증까지 완료</small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>규칙</dt>
              <dd>
                {a.releasedRuleCount}
                <span style={{ fontSize: 14, fontWeight: 600 }}> / {a.ruleCount}</span>
                <small>released, 나머지 1개는 draft</small>
              </dd>
            </div>
          </dl>
          <div className={styles.note}>
            <strong>복용 조건 {a.administrationConstraints}개와 released 규칙{" "}
            {a.releasedRuleCount}개는 다른 상태입니다.</strong> 앞의 것은 허가원문
            검증까지만 끝났고 별도의 약사 재검토를 거치지 않았습니다. 합쳐서 읽으면 안 됩니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>2. 설명 층, PubMed 문헌</h2>
          <p>
            인공지능이 허가원문에서 확인한 성분과 규칙 유형만 입력받아 질문 5개와 검색식을
            만들었습니다. 최종 검색식은 노출 성분을 중심으로 하고 대상 조건에는
            과량, 중복, 용량 표현을 더해 검색 범위를 넓혔습니다. 결과, 비교, 사람 대상 필터,
            연구설계, 언어, 출판유형 제한을 두지 않았습니다.
          </p>
          <p>
            출판일자 제한은 상한과 하한 모두 두지 않았습니다. 과량 복용과 성분 중복의 위해
            보고가 특정 시점 이후에만 있는 것이 아니기 때문입니다. 대상 조건에는 과량과
            중복, 용량 어휘가 들어 있습니다.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>질문</th>
                <th className="num">선별 단위</th>
              </tr>
            </thead>
            <tbody>
              {search.questions.map((q) => (
                <tr key={q.id}>
                  <td>{q.titleKo}</td>
                  <td className="num" style={{ fontWeight: 700 }}>
                    {n(q.rows)}
                  </td>
                </tr>
              ))}
              <tr>
                <td style={{ fontWeight: 700 }}>합계</td>
                <td className="num" style={{ fontWeight: 700 }}>{n(corpus.rows)}</td>
              </tr>
            </tbody>
          </table>
          <p style={{ marginTop: 12 }}>
            고유 논문 {n(corpus.uniquePapers)}편이고, 논문과 질문 조합으로 센 선별 단위가{" "}
            {n(corpus.rows)}건입니다. 중복 {n(corpus.duplicatesRemoved)}행을 걷어냈습니다.
            초록이 있는 행이 {n(corpus.rowsWithAbstract)}건, 제목만 있는 행이{" "}
            {n(corpus.rowsTitleOnly)}건입니다. 원본 응답 {n(corpus.xmlFiles)}개와 검증값을
            보존했습니다.
          </p>
        </section>

        <section className={styles.section}>
          <h2>3. 최종 선별 결과</h2>
          <p>
            선별은 {n(sc.screened)}건 전량을 빠짐없이 판정했습니다. 사람 판정은{" "}
            {sc.humanDecisions}건이고, 판정 원장은 질문과 논문 조합마다 판정 하나를
            남깁니다.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>판정</th>
                <th className="num">건수</th>
                <th className="num">비중</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 700 }}>유지</td>
                <td className="num" style={{ fontWeight: 700 }}>{n(sc.final.retain)}</td>
                <td className="num">
                  {((sc.final.retain / sc.screened) * 100).toFixed(1)}%
                </td>
              </tr>
              <tr>
                <td>후순위</td>
                <td className="num">{n(sc.final.deprioritize)}</td>
                <td className="num">
                  {((sc.final.deprioritize / sc.screened) * 100).toFixed(1)}%
                </td>
              </tr>
              <tr>
                <td>판정 보류</td>
                <td className="num">{n(sc.final.uncertain)}</td>
                <td className="num">
                  {((sc.final.uncertain / sc.screened) * 100).toFixed(2)}%
                </td>
              </tr>
            </tbody>
          </table>
          <p style={{ marginTop: 12 }}>
            유지 {n(sc.final.retain)}건을 논문으로 접으면 {n(sc.retainedPapers)}편입니다.
          </p>
          <div className={styles.note}>
            <strong>
              사후 검토 {n(sc.posthocCorrection.reviewed_rows)}행을 반영해
              {" "}{n(sc.posthocCorrection.label_changes)}행의 판정을 정정했습니다.
            </strong>{" "}
            문헌 ID별 사유와 입력 내용을 대조했습니다. 제목만 있는 문헌 전체에도
            대상과 노출이 직접 맞는지 같은 기준을 적용했습니다.
            정보가 부족한 문헌은 판정 보류로 남기고 문헌 후보에서 제외했습니다.
          </div>
          <details className={styles.details}>
            <summary>최초 선별과 과거 개정 기록</summary>
            <p>
              사후 정정 전에는 유지 {n(sc.beforeCorrection.retain)}건,
              후순위 {n(sc.beforeCorrection.deprioritize)}건,
              판정 보류 {n(sc.beforeCorrection.uncertain)}건이었습니다.
              그 이전 두 차례 개정에서는 {n(sc.changedFromEarlierPass)}건이 바뀌었습니다.
            </p>
            <p>
              {sc.amendments.map((item) => (
                <span key={item.id}>
                  {item.id}은 {item.what} ({n(item.rows)}건, 유지{" "}
                  {n(item.newLabels.retain)}, 후순위 {n(item.newLabels.deprioritize)},
                  판정 보류 {n(item.newLabels.uncertain)}).{" "}
                </span>
              ))}
              두 개정이 겹친 행이 {n(sc.amendmentOverlapRows)}건이고 한 번만 판정했습니다.
              최초 판정과 잠긴 채점은 보존했습니다.
            </p>
          </details>
        </section>

        <section className={styles.section}>
          <h2>4. 원문 확보</h2>
          <p>
            정정 전 유지 문헌 {n(ft.checkedPapers)}편에서 PMC 연결을 검색했습니다. PMCID가
            있는 것이 {n(ft.withPmcid)}편이고, 그중 본문까지 받은 것이{" "}
            {n(ft.withFulltext)}편입니다.
          </p>
          <dl className={styles.statGrid}>
            <div className={styles.stat}>
              <dt>본문 확보</dt>
              <dd>
                {n(ft.withFulltext)}
                <small>유지 {n(ft.checkedPapers)}편의 {ft.shareOfRetainedPct}%</small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>PMC 연결 대비</dt>
              <dd>
                {ft.shareOfPmcLinkedPct}%
                <small>PMCID {n(ft.withPmcid)}편 중</small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>본문 길이 중앙값</dt>
              <dd>
                {n(ft.medianChars)}
                <small>글자</small>
              </dd>
            </div>
          </dl>
          <div className={styles.note}>
            <strong>본문 확보와 전문 검토는 다릅니다.</strong>{" "}
            본문 확보율은 정정 전 유지 문헌의 {ft.shareOfRetainedPct}%입니다.
            선별과 이번 사후 검토는 제목, 초록, 주제어를 기준으로 했습니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>5. 정정 전 AI 채점 결과</h2>
          <p>
            사람 참조표준이 0건이라 선별 판정을 가린 다른 AI의 채점을 비교 기준으로
            두었습니다. 아래 값은 사후 정정 전 두 AI 판정의 비교입니다.
            제목만 있는 문헌의 처리 기준과 채점 중 기준 보충의 차이도 포함하므로
            순수한 모델 차이, 정정 후 성능 또는 임상적 정확도로 해석하지 않습니다.
          </p>
          <dl className={styles.statGrid}>
            <div className={styles.stat}>
              <dt>AI 기준 일치도</dt>
              <dd>
                {sg.agreement}%
                <small>
                  95% CI {sg.agreementCi[0]}~{sg.agreementCi[1]}
                </small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>AI 기준 민감도</dt>
              <dd>
                {sg.sensitivity}%
                <small>채점자 유지 중 선별도 유지한 비율</small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>AI 기준 특이도</dt>
              <dd>
                {sg.specificity}%
                <small>채점자 비유지 중 선별도 비유지인 비율</small>
              </dd>
            </div>
            <div className={styles.stat}>
              <dt>Cohen κ</dt>
              <dd>
                {sg.kappa.toFixed(3)}
                <small>층 가중, 3분류</small>
              </dd>
            </div>
          </dl>
          <p style={{ marginTop: 12 }}>
            표본 {n(sg.sampleRows)}행, 모집단 {n(sg.populationRows)}행, 층{" "}
            {sg.strata}개입니다. 표본은 앞선 채점이 이미 쓴{" "}
            {n(sg.excludedFromEarlierArm)}행을 뺀 {n(sg.eligiblePopulation)}행에서
            뽑았습니다. 추출 순서는 난수 없이 정해져 같은 입력에서 그대로 재현됩니다.
            채점 판정은 {day(sg.lockedAt)}에 잠갔고 참조 판정은 {day(sg.openedAt)}에
            열었습니다.
          </p>
          <div className={styles.note}>
            <strong>
              같은 표본 추출틀에서 비교한 유지 비율입니다. 선별 유지 {sg.pipelineRetainShare}%
              대 채점자 추정 {sg.scorerRetainShare}%, 비 {sg.retainShareRatio}배입니다.
            </strong>{" "}
            방향별로 보면 유지에서 후순위가{" "}
            {n(sg.disagreementByDirection["retain->deprioritize"])}건, 후순위에서 유지가{" "}
            {n(sg.disagreementByDirection["deprioritize->retain"])}건으로 어느 한쪽이
            지배하지 않습니다. 이 수치만으로 임상적 오류를 판별할 수는 없습니다. 두 AI 판정이 어디서
            갈라지는지를 적은 것입니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>6. 규칙별 문헌 후보</h2>
          <p>
            선별을 통과한 문헌은 규칙별 후보 문헌으로 연동합니다. 후보 문헌은 규칙이
            허용한 질문에서 선별이 유지로 판정하고 규칙 유형의 위해 표현이 제목이나
            초록에 나타난 논문입니다. 무관한 질문의 문헌이 규칙에 붙지 않도록 규칙마다
            허용 질문을 정해 두었고, 문헌은 설명 자료일 뿐 규칙을 배포시키지 못합니다.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>층</th>
                <th className="num">건수</th>
                <th>지위</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>수집 문헌</td>
                <td className="num">{n(corpus.rows)}</td>
                <td>선별 단위</td>
              </tr>
              <tr>
                <td>선별 유지</td>
                <td className="num">{n(sc.final.retain)}</td>
                <td>논문으로 {n(sc.retainedPapers)}편</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700 }}>규칙별 후보 문헌</td>
                <td className="num" style={{ fontWeight: 700 }}>
                  {n(pool.unique_papers_matched)}
                </td>
                <td>규칙 16개에 연결된 전체 후보 집합</td>
              </tr>
            </tbody>
          </table>
          <p style={{ marginTop: 12 }}>
            규칙별 후보 문헌은 고유 논문 {n(pool.unique_papers_matched)}편입니다. 한 논문이
            여러 규칙의 후보에 들어가므로 규칙과 논문을 짝으로 세면{" "}
            {n(pool.rule_paper_pairs)}쌍이 됩니다. 화면에는 규칙마다 상한을 두어
            고유 논문 {n(pool.unique_papers_listed)}편, 인용문{" "}
            {n(pool.quotable_sentences)}개를 싣고, 잘라낸 수는 규칙마다 함께 적습니다.
            조건에 맞는 논문이 없으면 다른 논문으로 채우지 않고 비워 둡니다.
          </p>
        </section>

        <section className={styles.section}>
          <h2>7. 이 연구가 말하지 않는 것</h2>
          <ul className={styles.list}>
            {summary.limitations.map((item) => (
              <li key={item.slice(0, 24)}>{item}</li>
            ))}
          </ul>
        </section>

        <p className={styles.footer}>
          수치 출처. 재수집 트랙 {summary.track} 원장 report.json,
          effective.decisions.jsonl, scoring_report.json, fulltext.jsonl
          <br />
          AI 문헌 연구와 조회 시제품. 사람 참조표준 0건이며 임상 검증을 뜻하지 않습니다.
        </p>
      </div>
    </main>
  );
}

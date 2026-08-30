import Link from "next/link";
import summary from "@/src/generated/recollect/research-summary.json";
import styles from "./research-summary.module.css";

const n = (value: number) => value.toLocaleString("ko-KR");

const ruleNames: Record<string, string> = {
  "OTC-RULE-003": "1일 최대량",
  "OTC-RULE-009": "위장관 출혈과 궤양",
  "OTC-RULE-010": "진정과 운전",
  "OTC-RULE-011": "음주",
  "OTC-RULE-013": "진정제 병용",
  "OTC-RULE-015": "최대 연속 복용",
  "OTC-RULE-016": "긴급 진료 권고",
};

const day = (iso: string) => iso.slice(0, 10);

export function ResearchSummary() {
  const a = summary.authorization;
  const search = summary.search;
  const corpus = summary.corpus;
  const sc = summary.screening;
  const ft = summary.fulltext;
  const sg = summary.scoring;
  const rl = summary.ruleLiterature;
  const pool = summary.rulePool;

  return (
    <main id="main-content" tabIndex={-1} className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <p className={styles.eyebrow}>연세대학교 약학대학, 권혁찬 졸업연구, 문헌 재수집 트랙</p>
          <h1>이 시스템이 무엇을 근거로 판정하는가</h1>
          <p>
            판정은 식약처 허가원문이 내리고, PubMed 문헌은 그 판정의 배경을 설명할 뿐
            판정을 바꾸지 않습니다. 아래 수치는 모두 연구 원장에서 그대로 옮긴 값입니다.
          </p>
          <div className={styles.flags}>
            <span className={styles.flag}>사람 판정 0건</span>
            <span className={styles.flag}>사람 맹검 독립평가 미완료</span>
            <span className={styles.flag}>임상 사용 승인 아님</span>
            <span className={styles.flag}>대조군 분류기 미실행</span>
          </div>
        </header>

        <section className={styles.section}>
          <h2>1. 판정을 내리는 층, 식약처 허가원문</h2>
          <p>
            제품, 성분, 함량, 복용 조건, 규칙 판정을 확정하는 결정층입니다. 규칙이
            배포되려면 허가원문의 출처와 원문 위치를 모두 갖춰야 하고, 문헌 링크는 이
            조건에 관여하지 않습니다. 문헌을 다시 모아도 이 층은 그대로입니다.
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
              <small>released, 나머지 1개는 draft</small>
            </div>
          </dl>
          <div className={styles.note}>
            <strong>복용 조건 {a.administrationConstraints}개와 released 규칙{" "}
            {a.releasedRuleCount}개는 다른 상태입니다.</strong> 앞의 것은 허가원문
            검증까지만 끝났고 별도의 약사 재검토를 거치지 않았습니다. 합쳐서 읽으면 안 됩니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>2. 설명을 붙이는 층, PubMed 문헌</h2>
          <p>
            인공지능이 허가원문에서 확인한 성분과 규칙 유형만 입력받아 질문 5개와 검색식을
            만들었습니다. 검색식은 대상(P)과 노출(I) 두 블록만 쓰고 결과, 비교, Humans,
            연구설계, 언어, 출판유형 제한을 두지 않습니다.
          </p>
          <p>
            출판일자 제한은 상한과 하한 모두 두지 않았습니다. 과량 복용과 성분 중복의 위해
            보고가 특정 시점 이후에만 있는 것이 아니기 때문입니다. 대상 블록에는 과량과
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
                <td style={{ fontWeight: 800 }}>합계</td>
                <td className="num" style={{ fontWeight: 800 }}>{n(corpus.rows)}</td>
              </tr>
            </tbody>
          </table>
          <p style={{ marginTop: 12 }}>
            고유 논문 {n(corpus.uniquePapers)}편이고, 논문과 질문 조합으로 센 선별 단위가{" "}
            {n(corpus.rows)}건입니다. 중복 {n(corpus.duplicatesRemoved)}행을 걷어냈습니다.
            초록이 있는 행이 {n(corpus.rowsWithAbstract)}건, 제목만 있는 행이{" "}
            {n(corpus.rowsTitleOnly)}건입니다. 원본 XML {n(corpus.xmlFiles)}개와 체크섬을
            보존했습니다.
          </p>
        </section>

        <section className={styles.section}>
          <h2>3. 선별 결과와 재판정</h2>
          <p>
            선별은 {n(sc.screened)}건 전량에 라벨을 부여했습니다(커버리지{" "}
            {sc.coverage.toFixed(1)}).
            사람 판정은 {sc.humanDecisions}건이고, 판정 원장은 질문과 레코드 조합을 고유
            키로 씁니다.
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
                <td style={{ fontWeight: 800 }}>유지</td>
                <td className="num" style={{ fontWeight: 800 }}>{n(sc.final.retain)}</td>
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
              두 차례 개정으로 {n(sc.changedFromEarlierPass)}건의 라벨이 바뀌었습니다.
            </strong>{" "}
            {sc.amendments.map((item) => (
              <span key={item.id}>
                {item.id}은 {item.what} ({n(item.rows)}건, 유지{" "}
                {n(item.newLabels.retain)}, 후순위 {n(item.newLabels.deprioritize)},
                판정 보류 {n(item.newLabels.uncertain)}).{" "}
              </span>
            ))}
            두 개정이 겹친 행이 {n(sc.amendmentOverlapRows)}건이고 한 번만 판정했습니다.
            앞 판정을 지우지 않고 새 판정을 원장으로 씁니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>4. 원문 확보</h2>
          <p>
            유지 판정을 받은 {n(ft.checkedPapers)}편 전부에서 PMC 연결을 찾았습니다. PMCID가
            있는 것이 {n(ft.withPmcid)}편이고, 그중 본문까지 받은 것이{" "}
            {n(ft.withFulltext)}편입니다.
          </p>
          <dl className={styles.statGrid}>
            <div className={styles.stat}>
              <dt>본문 확보</dt>
              <dd>{n(ft.withFulltext)}</dd>
              <small>유지 {n(ft.checkedPapers)}편의 {ft.shareOfRetainedPct}%</small>
            </div>
            <div className={styles.stat}>
              <dt>PMC 연결 대비</dt>
              <dd>{ft.shareOfPmcLinkedPct}%</dd>
              <small>PMCID {n(ft.withPmcid)}편 중</small>
            </div>
            <div className={styles.stat}>
              <dt>본문 길이 중앙값</dt>
              <dd>{n(ft.medianChars)}</dd>
              <small>글자</small>
            </div>
          </dl>
          <div className={styles.note}>
            <strong>본문을 읽은 것은 유지 문헌의 {ft.shareOfRetainedPct}%뿐입니다.</strong>{" "}
            나머지 {n(ft.checkedPapers - ft.withFulltext)}편은 제목과 초록만 확인했습니다.
            공개 접근이 아닌 논문은 본문을 받을 수 없어서 생기는 차이이고, 선별 판정 자체는
            제목과 초록으로 내렸습니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>5. 선별을 어떻게 확인했나</h2>
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
              <small>파이프라인 유지를 채점자가 유지로</small>
            </div>
            <div className={styles.stat}>
              <dt>specificity_vs_ai_reference</dt>
              <dd>{sg.specificity}%</dd>
              <small>파이프라인 비유지를 채점자가 비유지로</small>
            </div>
            <div className={styles.stat}>
              <dt>Cohen κ</dt>
              <dd>{sg.kappa.toFixed(3)}</dd>
              <small>설계 가중, 3분류</small>
            </div>
          </dl>
          <p style={{ marginTop: 12 }}>
            표본 {n(sg.sampleRows)}행, 모집단 {n(sg.populationRows)}행, 층{" "}
            {sg.strata}개입니다. 표본은 앞선 채점 arm이 이미 쓴{" "}
            {n(sg.excludedFromEarlierArm)}행을 뺀 {n(sg.eligiblePopulation)}행에서
            뽑았습니다. 추출 시드는 <code>{sg.seed}</code>입니다. 채점 라벨은{" "}
            {day(sg.lockedAt)}에 해시로 잠갔고 참조 라벨은 {day(sg.openedAt)}에
            열었습니다.
          </p>
          <div className={styles.note}>
            <strong>
              두 판정이 남기는 양은 거의 같습니다. 파이프라인 유지 {sg.pipelineRetainShare}%
              대 채점자 추정 {sg.scorerRetainShare}%, 비 {sg.retainShareRatio}배입니다.
            </strong>{" "}
            방향별로 보면 유지에서 후순위가{" "}
            {n(sg.disagreementByDirection["retain->deprioritize"])}건, 후순위에서 유지가{" "}
            {n(sg.disagreementByDirection["deprioritize->retain"])}건으로 어느 한쪽이
            지배하지 않습니다. 이것을 오차라고 부르지 않습니다. 두 AI 판정이 어디서
            갈라지는지를 적은 것입니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>6. 규칙에 문헌을 붙여봤더니</h2>
          <p>
            문헌은 두 층으로 나뉘고 지위가 다릅니다. 위층은 문장 위치와 원문 인용을 대조해
            통과한 <strong>검증 근거</strong>이고, 아래층은 규칙이 허용한 질문에서 선별이
            유지로 판정하고 규칙 유형의 위해 표현이 제목이나 초록에 나타난{" "}
            <strong>선별 통과 문헌</strong>입니다. 아래층은 인용 대조를 거치지 않았고 규칙을
            배포시키지 못합니다.
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
                <td>코퍼스</td>
                <td className="num">{n(corpus.rows)}</td>
                <td>선별 단위</td>
              </tr>
              <tr>
                <td>선별 유지</td>
                <td className="num">{n(sc.final.retain)}</td>
                <td>논문으로 {n(sc.retainedPapers)}편</td>
              </tr>
              <tr>
                <td>규칙별 문헌 풀</td>
                <td className="num">{n(pool.unique_papers_matched)}</td>
                <td>인용 대조 없음, 규칙 배포 불가</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 800 }}>검증 근거</td>
                <td className="num" style={{ fontWeight: 800 }}>{rl.linkCount}</td>
                <td>규칙 {rl.resolvedRuleCount}개, 인용 대조 통과</td>
              </tr>
            </tbody>
          </table>
          <p style={{ marginTop: 12 }}>
            규칙별 문헌 풀은 고유 논문 {n(pool.unique_papers_matched)}편입니다. 한 논문이
            여러 규칙의 풀에 들어가므로 규칙과 논문을 짝으로 세면{" "}
            {n(pool.rule_question_paper_rows)}건이 됩니다. 화면에는 규칙마다 상한을 두어
            고유 논문 {n(pool.unique_papers_listed)}편, 인용문{" "}
            {n(pool.quotable_sentences)}개를 싣고, 잘라낸 수는 규칙마다 함께 적습니다.
          </p>
          <div className={styles.note}>
            <strong>
              중복복용이 이 연구의 주제인데 1일 최대량 규칙에 검증된 문헌 근거가 0건입니다.
            </strong>{" "}
            검증 근거가 없는 규칙은{" "}
            {rl.unresolvedRuleIds.map((id) => ruleNames[id] ?? id).join(", ")} 입니다. 검증
            근거 {rl.linkCount}건은 봉인한 v5.0 산출물 그대로이고 재수집이 바꾸지
            않았습니다. 이 규칙들도 아래층 문헌은 있으므로 화면에서 읽을 것은 있지만, 그것이
            규칙을 배포시키지는 못합니다.
          </div>
        </section>

        <section className={styles.section}>
          <h2>7. 이 연구가 말하지 않는 것</h2>
          <ul className={styles.list}>
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
          수치 출처. 재수집 트랙 {summary.track} 원장 report.json,
          effective.decisions.jsonl, scoring_report.json, fulltext.jsonl
          <br />
          집계 시각 {day(summary.builtAt)}, 사람 맹검 없음, 배포 준비 상태 거짓, 사람 판정 0건
        </p>
      </div>
    </main>
  );
}

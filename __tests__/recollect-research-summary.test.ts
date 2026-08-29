import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import summary from "@/src/generated/recollect/research-summary.json";
import pool from "@/src/generated/recollect/rule-literature-pool.json";

/**
 * 연구 정보 화면이 쓰는 값은 재수집 트랙(recollect-v2 · kwon)에서 나온다. 그 원장은
 * 다른 저장소(`C:\dev\evidence-recollect`)에 있어 배포 빌드에서는 읽을 수 없다.
 * 화면이 쓸 값만 뽑아 `src/generated/recollect/` 에 굽고 커밋하므로, 그 파일이
 * 원장과 어긋나면 화면이 없는 숫자를 말하게 된다. 원장이 있는 환경에서는 대조하고,
 * 없으면 형태와 자체 정합만 확인한다.
 *
 * 제출한 논문의 봉인 원장은 `v50-research-summary.test.ts` 가 따로 지킨다.
 * 두 파일의 수치를 하나로 합치지 않는다.
 */
const TRACK_ROOT = "C:\\dev\\evidence-recollect\\data\\kwon";
const reportPath = `${TRACK_ROOT}\\report.json`;
const hasLedger = existsSync(reportPath);
const read = (path: string) => JSON.parse(readFileSync(path, "utf8"));

describe("재수집 트랙 연구 정보 요약", () => {
  it("사람 참조표준이 없다는 사실을 그대로 담는다", () => {
    expect(summary.flags.humanReferenceRows).toBe(0);
    expect(summary.flags.independentBlinding).toBe(false);
    expect(summary.flags.releaseReady).toBe(false);
    expect(summary.screening.humanDecisions).toBe(0);
  });

  it("정답을 열기 전에 채점 라벨을 잠갔다는 기록을 담는다", () => {
    expect(summary.scoring.truthOpenedBeforeLock).toBe(false);
    expect(Date.parse(summary.scoring.lockedAt)).toBeLessThan(
      Date.parse(summary.scoring.openedAt),
    );
  });

  it("대조군 분류기를 돌리지 않았다는 사실을 숨기지 않는다", () => {
    expect(summary.comparator.required).toBe(false);
    expect(summary.comparator.classified).toBe(0);
  });

  it("선별 판정 합이 코퍼스 행 수와 맞는다", () => {
    const { retain, deprioritize, uncertain } = summary.screening.final;
    expect(retain + deprioritize + uncertain).toBe(summary.corpus.rows);
    expect(summary.screening.screened).toBe(summary.corpus.rows);
    expect(summary.screening.coverage).toBe(1);
    // 논문으로 접으면 행 수보다 적다.
    expect(summary.screening.retainedPapers).toBeLessThan(retain);
  });

  it("코퍼스가 옛 트랙보다 크다는 사실을 수치로 담는다", () => {
    expect(summary.corpus.rows).toBeGreaterThan(summary.corpus.previousRows);
    expect(summary.corpus.growthVsPrevious).toBeCloseTo(
      summary.corpus.rows / summary.corpus.previousRows,
      2,
    );
    expect(
      summary.corpus.rowsWithAbstract + summary.corpus.rowsTitleOnly,
    ).toBe(summary.corpus.rows);
    const perQuestion = summary.search.questions.reduce((sum, q) => sum + q.rows, 0);
    expect(perQuestion).toBe(summary.corpus.rows);
  });

  it("근거 층은 아래로 갈수록 좁아진다", () => {
    expect(summary.corpus.rows).toBeGreaterThan(summary.screening.final.retain);
    expect(summary.screening.final.retain).toBeGreaterThan(
      summary.rulePool.unique_papers_matched,
    );
    expect(summary.rulePool.unique_papers_matched).toBeGreaterThan(
      summary.ruleLiterature.linkCount,
    );
    // 화면에 싣는 것은 도출 결과의 부분집합이다.
    expect(summary.rulePool.unique_papers_listed).toBeLessThanOrEqual(
      summary.rulePool.unique_papers_matched,
    );
  });

  it("규칙-문헌 연결의 실패를 숨기지 않는다", () => {
    const rl = summary.ruleLiterature;
    expect(rl.resolvedRuleCount + rl.unresolvedRuleCount).toBe(rl.ruleCount);
    expect(rl.unresolvedRuleIds).toHaveLength(rl.unresolvedRuleCount);
    // 중복복용이 주제인데 1일 최대량 규칙이 미연결이라는 사실이 화면에 남아야 한다.
    expect(rl.unresolvedRuleIds).toContain("OTC-RULE-003");
    // 검증 근거는 봉인한 v5.0 산출물이고 재수집이 바꾸지 않는다.
    expect(rl.linkCount).toBe(10);
    expect(rl.resolvedRuleCount).toBe(9);
  });

  it("풀 요약과 풀 파일이 같은 값을 말한다", () => {
    expect(summary.rulePool).toEqual(pool.totals);
    expect(pool.totals.retain_rows_in_corpus).toBe(summary.screening.final.retain);
    expect(pool.totals.retain_papers_in_corpus).toBe(
      summary.screening.retainedPapers,
    );
  });

  it.runIf(hasLedger)("원장과 어긋나지 않는다", () => {
    const report = read(reportPath);

    expect(summary.track).toBe(report.track);
    expect(summary.corpus.rows).toBe(report.corpus.rows);
    expect(summary.corpus.uniquePapers).toBe(report.corpus.unique_papers);
    expect(summary.corpus.previousRows).toBe(report.corpus.old_rows);
    expect(summary.screening.final.retain).toBe(report.screening.final["유지"]);
    expect(summary.screening.final.deprioritize).toBe(
      report.screening.final["후순위"],
    );
    expect(summary.screening.final.uncertain).toBe(
      report.screening.final["판정 보류"],
    );
    expect(summary.screening.retainedPapers).toBe(report.screening.retained_papers);
    expect(summary.fulltext.withFulltext).toBe(report.fulltext.with_fulltext);
    expect(summary.fulltext.withPmcid).toBe(report.fulltext.with_pmcid);
    expect(summary.fulltext.medianChars).toBe(report.fulltext.median_chars);

    const scoring = read(`${TRACK_ROOT}\\score-20260820\\scoring_report.json`);
    expect(summary.scoring.sampleRows).toBe(scoring.scored);
    expect(summary.scoring.populationRows).toBe(scoring.population);
    expect(summary.scoring.agreement).toBe(scoring.agreement_vs_ai_reference);
    expect(summary.scoring.agreementCi).toEqual(scoring.agreement_ci);
    expect(summary.scoring.sensitivity).toBe(scoring.sensitivity_vs_ai_reference);
    expect(summary.scoring.specificity).toBe(scoring.specificity_vs_ai_reference);
    expect(summary.scoring.pipelineRetainShare).toBe(scoring.pipeline_retain_share);
    expect(summary.scoring.scorerRetainShare).toBe(
      scoring.scorer_retain_share_weighted,
    );

    const sample = read(`${TRACK_ROOT}\\score-20260820\\sample.json`);
    expect(summary.scoring.seed).toBe(sample.seed);
    expect(summary.scoring.strata).toBe(sample.strata.length);
  });
});

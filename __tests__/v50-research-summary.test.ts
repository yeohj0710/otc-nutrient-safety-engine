import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import summary from "@/src/generated/v50-research-summary.json";

/**
 * 연구 정보 화면은 원장을 직접 읽지 못한다. `.vercelignore` 가 `research_v3` 를 통째로
 * 빼기 때문에, 화면이 쓸 값만 뽑아 `src/generated/v50-research-summary.json` 으로 굽고
 * 커밋한다. 그 파일이 원장과 어긋나면 화면이 없는 숫자를 말하게 되므로 여기서 묶어 둔다.
 *
 * 원장이 없는 환경(배포 빌드 등)에서는 대조를 건너뛰고 형태만 확인한다.
 */
const root = resolve(__dirname, "..");
const ledgerPath = resolve(root, "research_v3/logs/v50_run_report.json");
const scoringPath = resolve(root, "research_v3/logs/v50_scoring_report.json");
const linksPath = resolve(
  root,
  "research_v3/otc/literature/v5/downstream/literature_link_manifest.json",
);

const hasLedger =
  existsSync(ledgerPath) && existsSync(scoringPath) && existsSync(linksPath);

const read = (path: string) => JSON.parse(readFileSync(path, "utf8"));

describe("v5.0 연구 정보 요약", () => {
  it("사람 참조표준이 없다는 사실을 그대로 담는다", () => {
    expect(summary.flags.humanReferenceRows).toBe(0);
    expect(summary.flags.independentBlinding).toBe(false);
    expect(summary.flags.releaseReady).toBe(false);
  });

  it("정답을 열기 전에 채점 라벨을 잠갔다는 기록을 담는다", () => {
    expect(summary.scoring.truthOpenedBeforeLock).toBe(false);
  });

  it("규칙-문헌 연결의 실패를 숨기지 않는다", () => {
    const rl = summary.ruleLiterature;
    expect(rl.resolvedRuleCount + rl.unresolvedRuleCount).toBe(rl.ruleCount);
    expect(rl.unresolvedRuleIds).toHaveLength(rl.unresolvedRuleCount);
    // 중복복용이 주제인데 1일 최대량 규칙이 미연결이라는 사실이 화면에 남아야 한다.
    expect(rl.unresolvedRuleIds).toContain("OTC-RULE-003");
  });

  it.runIf(hasLedger)("원장과 어긋나지 않는다", () => {
    const ledger = read(ledgerPath);
    const scoring = read(scoringPath);
    const links = read(linksPath);
    const phaseC = ledger.phases.C;

    expect(summary.screening.final).toEqual(
      phaseC.final_layer.decision_distribution,
    );
    expect(summary.screening.classifier).toEqual(
      phaseC.classifier_layer.decision_distribution,
    );
    expect(summary.screening.adjudicatedRows).toBe(
      phaseC.semantic_adjudication_layer.selected_rows,
    );
    expect(summary.literature.screeningUnits).toBe(phaseC.final_layer.rows);
    expect(summary.literature.uniquePapers).toBe(
      links.inputs.evidence_map.record_count,
    );
    expect(summary.scoring.sampleRows).toBe(scoring.design.sample_n);
    expect(summary.scoring.populationRows).toBe(scoring.design.population_N);
    expect(summary.ruleLiterature.linkCount).toBe(
      links.results.emitted_link_count,
    );
    expect(summary.ruleLiterature.unresolvedRuleIds).toEqual(
      links.results.unresolved_rule_ids,
    );
    expect(summary.flags.overallExecutionStatus).toBe(
      ledger.overall_execution_status,
    );

    // 최종 retain 의 층별 구성은 화면이 그대로 말하는 값이라 검산까지 한다.
    const { finalRetainFromAdjudication, finalRetainFromClassifierOnly } =
      summary.screening;
    expect(finalRetainFromAdjudication + finalRetainFromClassifierOnly).toBe(
      phaseC.final_layer.decision_distribution.retain,
    );
  });
});

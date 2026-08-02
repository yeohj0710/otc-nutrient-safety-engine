import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import manifest from "@/research_v3/otc/literature/v5/downstream/literature_link_manifest.json";
import {
  rulePoolAuthority,
  rulePoolFor,
  rulePoolPapers,
  rulePoolTotals,
} from "@/src/lib/otc/rule-literature-pool";

const UNRESOLVED = manifest.results.unresolved_rule_ids as string[];
const RULE_IDS = (manifest.results.rules as { rule_id: string }[]).map(
  (rule) => rule.rule_id,
);

describe("규칙별 선별 통과 문헌 풀", () => {
  it("문헌은 규칙을 배포시키지 못한다", () => {
    expect(rulePoolAuthority.supports_rule_release).toBe(false);
    expect(rulePoolAuthority.evidence_authority).toBe("literature_explanatory_only");
    // 검증 근거와 지위가 다르다는 사실이 데이터에 박혀 있어야 한다.
    expect(rulePoolAuthority.quote_verified).toBe(false);
    expect(rulePoolAuthority.human_expert_reviewed).toBe(0);
  });

  it("규칙 16개 전부에 풀이 있다", () => {
    expect(RULE_IDS).toHaveLength(16);
    for (const ruleId of RULE_IDS) {
      const rule = rulePoolFor(ruleId);
      expect(rule, ruleId).not.toBeNull();
      expect(rule!.listed, ruleId).toBeGreaterThan(0);
    }
  });

  it("검증 근거가 0건인 미연결 7규칙에도 선별 통과 문헌이 있다", () => {
    expect(UNRESOLVED).toHaveLength(7);
    for (const ruleId of UNRESOLVED) {
      const rule = rulePoolFor(ruleId)!;
      expect(rule.verified_link_count, ruleId).toBe(0);
      expect(rule.listed, ruleId).toBeGreaterThan(0);
    }
    // 중복복용의 중심 규칙. 검증 근거는 0건이지만 읽을 문헌은 있다.
    const maxDaily = rulePoolFor("OTC-RULE-003")!;
    expect(maxDaily.rule_type).toBe("max_daily_dose");
    expect(maxDaily.verified_link_count).toBe(0);
    expect(maxDaily.listed).toBeGreaterThan(100);
  });

  it("규칙 유형으로 좁힌 결과는 질문 전체 풀보다 작다", () => {
    for (const ruleId of RULE_IDS) {
      const rule = rulePoolFor(ruleId)!;
      expect(rule.rule_type_matched_total, ruleId).toBeLessThan(
        rule.question_pool_total,
      );
      expect(rule.listed, ruleId).toBeLessThanOrEqual(rule.rule_type_matched_total);
    }
  });

  it("수록한 논문은 전부 메타데이터와 인용문을 갖는다", () => {
    const papers = rulePoolPapers("OTC-RULE-003", 0, 20);
    expect(papers).toHaveLength(20);
    for (const paper of papers) {
      expect(paper.record_id).toBeTruthy();
      expect(paper.title).toBeTruthy();
      expect(paper.url).toMatch(/^https:\/\/pubmed\.ncbi\.nlm\.nih\.gov\/\d+\/$/);
      // 인용문과 그 문장이 초록의 몇 번째인지가 함께 있어야 한다.
      expect(paper.quote.length).toBeGreaterThan(20);
      expect(paper.locator).toMatch(/^(abstract:sentence:\d+|TITLE)$/);
    }
  });

  it("규칙 16개 전부에 인용 가능한 문장이 있다", () => {
    expect(rulePoolTotals.quotable_sentences).toBeGreaterThan(2000);
    // 제목을 인용한 경우는 초록이 아예 없는 논문뿐이고 2% 미만이어야 한다.
    expect(rulePoolTotals.title_only_quotes).toBeLessThan(
      rulePoolTotals.quotable_sentences * 0.02,
    );
    for (const ruleId of RULE_IDS) {
      const papers = rulePoolPapers(ruleId, 0, 5);
      expect(papers.length, ruleId).toBeGreaterThan(0);
      for (const paper of papers) expect(paper.quote, ruleId).toBeTruthy();
    }
  });

  it("같은 논문이라도 규칙이 다르면 다른 문장을 인용할 수 있다", () => {
    // 문장은 규칙 관점에서 고르므로 인용문 수가 고유 논문 수보다 많다.
    expect(rulePoolTotals.quotable_sentences).toBeGreaterThan(
      rulePoolTotals.unique_papers_listed,
    );
  });

  it("페이징이 겹치지 않는다", () => {
    const first = rulePoolPapers("OTC-RULE-005", 0, 20).map((p) => p.record_id);
    const second = rulePoolPapers("OTC-RULE-005", 20, 20).map((p) => p.record_id);
    expect(new Set([...first, ...second]).size).toBe(first.length + second.length);
  });

  it("화면이 두 층의 지위 차이를 말한다", () => {
    const source = readFileSync(
      "src/components/otc-product-safety-client.tsx",
      "utf8",
    );
    expect(source).toContain("선별 통과 문헌");
    expect(source).toContain("문장 인용 대조를 거치지 않았고");
    expect(source).toContain("판정 결과를 바꾸지 않습니다");
  });

  it("논문이 보고하는 검증 근거 수치는 이 층이 바꾸지 않는다", () => {
    expect(manifest.results.resolved_rule_count).toBe(9);
    expect(manifest.results.emitted_link_count).toBe(10);
    expect(rulePoolTotals.rules).toBe(16);
    expect(rulePoolTotals.unique_papers_listed).toBeGreaterThan(1000);
  });
});

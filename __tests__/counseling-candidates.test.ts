import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";
import { gunzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import pool from "@/src/generated/recollect/rule-literature-pool.json";
import generated from "@/src/generated/otc-counseling-candidates.json";
import { counselingCandidateReview, counselingCandidates } from "@/src/lib/otc/counseling-candidates";
import { isRetractedPublication } from "@/src/lib/publication-status";

// 추가 선별 후보는 검토 문헌과 지위가 다르다. 이 검사는 후보 자료가 (1) 실제
// 선별 풀 안의 논문이고 (2) 인용 문장이 저장한 초록에 글자 그대로 있고
// (3) 철회 논문이 아니며 (4) 규칙 승인이나 사람 검토를 주장하지 않는지를 본다.

const root = process.cwd();
const sources = JSON.parse(
  gunzipSync(readFileSync(path.join(root, "research/counseling/sources.json.gz"))).toString("utf8"),
) as Record<string, { abstract: string; publicationTypes: string }>;
const curatedPath = path.join(root, "research/counseling/curated-candidates.json");
const normalize = (text: string) => text.split(/\s+/).join(" ").trim();
const papers = pool.papers as Record<string, { pmid: string; title: string }>;
const ruleTypes = new Set(Object.values(pool.rules).map((rule) => rule.rule_type));

describe("추가 선별 후보 자료의 지위와 대조", () => {
  it("is generated from the current curated file and sources", () => {
    expect(generated.curatedSha256).toBe(createHash("sha256").update(readFileSync(curatedPath)).digest("hex"));
    expect(generated.sourcesSha256).toBe(
      createHash("sha256").update(readFileSync(path.join(root, "research/counseling/sources.json.gz"))).digest("hex"),
    );
    expect(generated.humanExpertReviewed).toBe(false);
    expect(generated.supportsRuleRelease).toBe(false);
    expect(generated.changesAuthorizationDecision).toBe(false);
    expect(counselingCandidateReview.humanExpertReviewed).toBe(false);
    expect(counselingCandidateReview.count).toBe(counselingCandidates.length);
    expect(counselingCandidates.length).toBeGreaterThanOrEqual(20);
  });

  it("only cites screening-pool papers whose quotes appear verbatim in the saved abstract", () => {
    for (const entry of counselingCandidates) {
      const record = `PMID-${entry.pmid}`;
      expect(papers[record], record).toBeDefined();
      expect(papers[record].title, record).toBe(entry.title);
      const source = sources[record];
      expect(source, record).toBeDefined();
      expect(isRetractedPublication(source.publicationTypes), record).toBe(false);
      const abstract = normalize(source.abstract);
      expect(entry.quotes.length, record).toBeGreaterThan(0);
      for (const item of entry.quotes) {
        expect(abstract.includes(normalize(item.quote)), `${record}: ${item.quote.slice(0, 50)}`).toBe(true);
        expect(item.locator, record).toMatch(/^abstract:sentence:\d+$/);
      }
      expect(createHash("sha256").update(source.abstract).digest("hex"), record).toBe(entry.abstractSha256);
    }
  });

  it("describes population, exposure, outcome and applicability differences in Korean for every candidate", () => {
    for (const entry of counselingCandidates) {
      for (const field of ["studyDesignKo", "populationKo", "exposureKo", "outcomeKo", "applicabilityKo"] as const) {
        expect(entry[field], `${entry.pmid}:${field}`).toMatch(/[가-힣]/);
      }
      expect(entry.ruleTypes.length, entry.pmid).toBeGreaterThan(0);
      for (const ruleType of entry.ruleTypes) expect(ruleTypes.has(ruleType), `${entry.pmid}:${ruleType}`).toBe(true);
      // 성분으로 이어지지 않는 후보는 어느 판정에도 붙지 않는다. 같은 성분이 아니라
      // 이성질체 같은 관련 성분으로만 이어지는 자료는 relatedIngredients 로 두고,
      // 그때는 뜻을 밝히는 설명을 함께 적는다(붙을 때 항상 배경 자료로 내려간다).
      expect(entry.ingredientIds.length + entry.relatedIngredients.length, entry.pmid).toBeGreaterThan(0);
      for (const related of entry.relatedIngredients) expect(related.noteKo, entry.pmid).toMatch(/[가-힣]/);
      expect(["candidate", "candidate_background"]).toContain(entry.relation);
      if (entry.authorizationAlignment === "conflict") expect(entry.authorizationNoteKo, entry.pmid).toMatch(/[가-힣]/);
    }
  });

  it("covers every released rule type that had no reviewed literature", () => {
    const covered = new Set(counselingCandidates.flatMap((entry) => entry.ruleTypes));
    for (const ruleType of ["max_daily_dose", "gi_bleeding_ulcer", "sedation_driving", "alcohol", "sedative_medication", "urgent_referral"]) {
      expect(covered.has(ruleType), ruleType).toBe(true);
    }
  });

  it("reaches the ingredients whose dosing findings had nothing attached", () => {
    // 260912 실측: 세티리진 용량 판정과 살리실산메틸 파프 횟수 판정이 문헌 0편이었다.
    const reaches = (ingredientId: string, ruleType: string) =>
      counselingCandidates.some(
        (entry) =>
          entry.ruleTypes.includes(ruleType) &&
          [...entry.ingredientIds, ...entry.relatedIngredients.map((item) => item.ingredientId)].includes(ingredientId),
      );
    expect(reaches("ING-cetirizine_hydrochloride", "max_daily_dose")).toBe(true);
    expect(reaches("ING-mf-src-8bebf0ac75f4", "max_daily_dose")).toBe(true);
  });
});

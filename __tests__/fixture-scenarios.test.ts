import pregnantVitaminA from "@/__tests__/fixtures/pregnant-vitamin-a.json";
import lactatingStJohnsWort from "@/__tests__/fixtures/lactating-st-johns-wort.json";
import smokerBetaCarotene from "@/__tests__/fixtures/smoker-beta-carotene.json";
import warfarinVitaminK from "@/__tests__/fixtures/warfarin-vitamin-k.json";
import thiazideVitaminDCalcium from "@/__tests__/fixtures/thiazide-vitamin-d-calcium.json";
import quinoloneSpacing from "@/__tests__/fixtures/quinolone-spacing.json";
import missingAgeSex from "@/__tests__/fixtures/missing-age-sex.json";
import knowledgeIndexJson from "@/src/generated/knowledge-index.json";
import { runSafetyEngine } from "@/src/lib/safety-engine";
import { knowledgeIndexSchema, type EngineQuery } from "@/src/types/knowledge";
import { describe, expect, it } from "vitest";

const knowledgeIndex = knowledgeIndexSchema.parse(knowledgeIndexJson);

const fixtures = [
  pregnantVitaminA,
  lactatingStJohnsWort,
  smokerBetaCarotene,
  warfarinVitaminK,
  thiazideVitaminDCalcium,
  quinoloneSpacing,
  missingAgeSex,
] as Array<{
  name: string;
  query: EngineQuery;
  expected: {
    definitely_matched: string[];
    needs_more_info: string[];
    possibly_relevant: string[];
  };
}>;

describe("fixture scenarios", () => {
  for (const fixture of fixtures) {
    it(fixture.name, () => {
      const response = runSafetyEngine(fixture.query, knowledgeIndex);
      const definitelyMatchedIds = new Set(response.definitely_matched.map((match) => match.ruleId));
      const needsMoreInfoIds = new Set(response.needs_more_info.map((match) => match.ruleId));
      const possiblyRelevantIds = new Set(response.possibly_relevant.map((match) => match.ruleId));

      for (const ruleId of fixture.expected.definitely_matched) {
        expect(definitelyMatchedIds.has(ruleId)).toBe(true);
      }

      for (const ruleId of fixture.expected.needs_more_info) {
        expect(needsMoreInfoIds.has(ruleId)).toBe(true);
      }

      for (const ruleId of fixture.expected.possibly_relevant) {
        expect(possiblyRelevantIds.has(ruleId)).toBe(true);
      }
    });
  }
});

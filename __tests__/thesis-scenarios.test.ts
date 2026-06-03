import knowledgeIndexJson from "@/src/generated/knowledge-index.json";
import { runSafetyEngine } from "@/src/lib/safety-engine";
import { knowledgeIndexSchema, type EngineQuery } from "@/src/types/knowledge";
import { describe, expect, it } from "vitest";

const knowledgeIndex = knowledgeIndexSchema.parse(knowledgeIndexJson);

function matchedRuleIds(query: EngineQuery) {
  const response = runSafetyEngine(query, knowledgeIndex);
  return {
    response,
    definite: new Set(response.definitely_matched.map((match) => match.ruleId)),
    active: new Set([
      ...response.definitely_matched,
      ...response.possibly_relevant,
      ...response.needs_more_info,
    ].map((match) => match.ruleId)),
  };
}

describe("Kwon thesis scenario evidence checks", () => {
  it("matches high dose vitamin D upper intake rules", () => {
    const { response, active } = matchedRuleIds({
      profile: { age: 45, jurisdiction: "US", strictestMode: true },
      candidateItems: [
        {
          ingredientId: "vitamin_d",
          name: "vitamin D",
          dailyIntakeValue: 5000,
          dailyIntakeUnit: "iu/day",
          longTermUseDays: 90,
        },
      ],
      sort: "severity_desc",
    });

    expect(active.has("RULE-VITD-UL-US-ADULT")).toBe(true);
    expect(active.has("RULE-VITD-3200-4000IU-WARN")).toBe(true);
    expect(response.totalCounts.definitely_matched).toBeGreaterThanOrEqual(2);
  });

  it("matches vitamin B6 long-term neuropathy rules", () => {
    const { response, active } = matchedRuleIds({
      profile: { jurisdiction: "EU", strictestMode: true },
      candidateItems: [
        {
          ingredientId: "vitamin_b6",
          name: "vitamin B6",
          dailyIntakeValue: 50,
          dailyIntakeUnit: "mg/day",
          longTermUseDays: 180,
        },
      ],
      sort: "severity_desc",
    });

    expect(active.has("RULE-B6-NEUROPATHY")).toBe(true);
    expect(active.has("RULE-B6-UL-EU-ADULT")).toBe(true);
    expect(response.totalCounts.definitely_matched).toBeGreaterThanOrEqual(1);
  });

  it("matches supplemental magnesium high dose rules", () => {
    const { response, active } = matchedRuleIds({
      profile: { conditions: ["renal impairment"], jurisdiction: "US", strictestMode: true },
      candidateItems: [
        {
          ingredientId: "magnesium_supplement",
          name: "magnesium supplement",
          dailyIntakeValue: 400,
          dailyIntakeUnit: "mg/day",
        },
      ],
      sort: "severity_desc",
    });

    expect(active.has("RULE-MAG-HIGHDose-DIARRHEA")).toBe(true);
    expect(active.has("RULE-MAG-UL-US-ADULT")).toBe(true);
    expect(response.totalCounts.definitely_matched).toBeGreaterThanOrEqual(1);
  });

  it("matches high dose iron self-use rules", () => {
    const { response, active } = matchedRuleIds({
      profile: { age: 35, jurisdiction: "US", strictestMode: true },
      candidateItems: [
        {
          ingredientId: "iron",
          name: "iron",
          form: "ferrous sulfate",
          dailyIntakeValue: 65,
          dailyIntakeUnit: "mg/day",
          coingredients: ["calcium"],
        },
      ],
      sort: "severity_desc",
    });

    expect(active.has("RULE-IRON-UL-US-ADULT")).toBe(true);
    expect(active.has("RULE-IRON-CALCIUM-SPLIT")).toBe(true);
    expect(response.totalCounts.definitely_matched).toBeGreaterThanOrEqual(4);
  });

  it("matches zinc long-term high dose rules", () => {
    const { response, active } = matchedRuleIds({
      profile: { age: 35, jurisdiction: "US", strictestMode: true },
      candidateItems: [
        { ingredientId: "zinc", name: "zinc", dailyIntakeValue: 50, dailyIntakeUnit: "mg/day", longTermUseDays: 120 },
      ],
      sort: "severity_desc",
    });

    expect(active.has("RULE-ZINC-UL-US-ADULT")).toBe(true);
    expect(active.has("RULE-ZINC-LONGTERM-COPPER")).toBe(true);
    expect(response.totalCounts.definitely_matched).toBeGreaterThanOrEqual(3);
  });

  it("matches preformed vitamin A upper intake rules", () => {
    const { response, active } = matchedRuleIds({
      profile: { age: 35, jurisdiction: "US", strictestMode: true },
      candidateItems: [
        {
          ingredientId: "vitamin_a_preformed",
          name: "preformed vitamin A",
          form: "retinol",
          dailyIntakeValue: 3500,
          dailyIntakeUnit: "mcg rae/day",
        },
      ],
      sort: "severity_desc",
    });

    expect(active.has("RULE-VITA-UL-US-ADULT")).toBe(true);
    expect(response.totalCounts.definitely_matched).toBeGreaterThanOrEqual(1);
  });
});

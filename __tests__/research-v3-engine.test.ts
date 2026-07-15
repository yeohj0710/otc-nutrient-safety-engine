import {
  evaluateResearchV3Draft,
  getResearchV3RuntimeMeta,
} from "@/src/lib/research-v3/engine";
import { describe, expect, it } from "vitest";

describe("research v3 draft engine", () => {
  it("is explicitly non-clinical and reports the reviewed rules", () => {
    expect(getResearchV3RuntimeMeta()).toMatchObject({
      lineage: "research_v3",
      releaseStatus: "draft_not_for_clinical_use",
      ruleCount: 6,
      releasedRuleCount: 6,
    });
  });

  it("matches above-threshold vitamin D and not the boundary", () => {
    expect(evaluateResearchV3Draft({
      age: 30,
      ingredientId: "vitamin_d",
      dailyTotalUg: 101,
    }).matches.map((rule) => rule.id)).toEqual(["V3-DRAFT-KDRI-VD-UL"]);
    expect(evaluateResearchV3Draft({
      age: 30,
      ingredientId: "vitamin_d",
      dailyTotalUg: 100,
    }).matches).toEqual([]);
  });

  it("uses calcium age and sex profiles", () => {
    expect(evaluateResearchV3Draft({
      age: 25,
      sex: "male",
      ingredientId: "calcium",
      dailyTotalMg: 2800,
    }).matches).toEqual([]);
    expect(evaluateResearchV3Draft({
      age: 35,
      sex: "female",
      ingredientId: "calcium",
      dailyTotalMg: 2800,
    }).matches.map((rule) => rule.id)).toEqual(["V3-DRAFT-KDRI-CA-UL"]);
  });

  it("does not count food magnesium toward the non-food threshold", () => {
    expect(evaluateResearchV3Draft({
      age: 30,
      ingredientId: "magnesium",
      dailyTotalMg: 500,
      nonFoodDailyTotalMg: 0,
    }).matches).toEqual([]);
  });
});

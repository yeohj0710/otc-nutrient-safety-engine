import sampleEvaluationInput from "@/data/sample_evaluation_input.json";
import knowledgeIndexJson from "@/src/generated/knowledge-index.json";
import { runSafetyEngine } from "@/src/lib/safety-engine";
import { knowledgeIndexSchema, type EngineQuery } from "@/src/types/knowledge";
import { describe, expect, it } from "vitest";

const knowledgeIndex = knowledgeIndexSchema.parse(knowledgeIndexJson);

function buildSampleQuery(): EngineQuery {
  return {
    profile: {
      age: sampleEvaluationInput.user_profile.age_years,
      sex: sampleEvaluationInput.user_profile.sex,
      pregnancyStatus: sampleEvaluationInput.user_profile.pregnancy_status,
      lactationStatus: sampleEvaluationInput.user_profile.lactation_status,
      smokerStatus: sampleEvaluationInput.user_profile.smoking_status,
      medications: sampleEvaluationInput.user_profile.medications.map((item) => item.name),
      conditions: sampleEvaluationInput.user_profile.conditions,
      allergies: sampleEvaluationInput.user_profile.allergies,
      jurisdiction: "KR",
    },
    candidateItems: sampleEvaluationInput.candidate_stack.map((item) => ({
      ingredientId: item.ingredient_id,
      name: item.label,
      dailyIntakeValue: item.daily_intake_value,
      dailyIntakeUnit: item.daily_intake_unit,
      sameDay: item.ingredient_id === "calcium" ? true : undefined,
    })),
    sort: "severity_desc",
  };
}

describe("runSafetyEngine", () => {
  it("matches the major sample interaction and dose rules from the actual normalized data", () => {
    const response = runSafetyEngine(buildSampleQuery(), knowledgeIndex);
    const matchedIds = new Set(response.definitely_matched.map((match) => match.ruleId));

    expect(matchedIds.has("RULE-BETACAROTENE-SMOKERS-AVOID")).toBe(true);
    expect(matchedIds.has("RULE-VITK-WARFARIN-CONSISTENCY")).toBe(true);
    expect(matchedIds.has("RULE-CALCIUM-LEVOTHYROXINE-4H")).toBe(true);
    expect(matchedIds.has("RULE-VITD-UL-US-ADULT")).toBe(true);
    expect(matchedIds.has("RULE-VITD-THIAZIDE-HYPERCALCEMIA")).toBe(true);
    expect(matchedIds.has("RULE-OMEGA3-WARFARIN-MONITOR")).toBe(true);
    expect(matchedIds.has("RULE-SJW-MAJOR-DRUG-INTERACTIONS")).toBe(true);
  });

  it("marks form-specific iodine interaction rules as needs_more_info when the form is missing", () => {
    const response = runSafetyEngine(
      {
        profile: {
          age: 45,
          medications: ["lisinopril"],
          selectedCompounds: ["iodine"],
          jurisdiction: "KR",
        },
        sort: "severity_desc",
      },
      knowledgeIndex,
    );

    const iodineRule = response.needs_more_info.find(
      (match) => match.ruleId === "RULE-IODINE-POTASSIUM-IODIDE-HYPERKALEMIA",
    );

    expect(iodineRule).toBeDefined();
    expect(iodineRule?.needsMoreInfo.length).toBeGreaterThan(0);
  });

  it("returns quality-signal rules as possibly relevant when no personal trigger is required", () => {
    const response = runSafetyEngine(
      {
        profile: {
          selectedCompounds: ["melatonin"],
          jurisdiction: "KR",
        },
        sort: "severity_desc",
      },
      knowledgeIndex,
    );

    const melatoninQualityRule = response.possibly_relevant.find(
      (match) => match.ruleId === "RULE-MELATONIN-QUALITY-VARIABILITY",
    );

    expect(melatoninQualityRule).toBeDefined();
  });

  it("matches ingredients and medications even when spacing and casing vary", () => {
    const response = runSafetyEngine(
      {
        profile: {
          selectedCompounds: ["VitaminK"],
          medications: ["War Farin"],
          jurisdiction: "KR",
        },
        sort: "severity_desc",
      },
      knowledgeIndex,
    );

    const matchedIds = new Set(
      response.definitely_matched.map((match) => match.ruleId),
    );

    expect(matchedIds.has("RULE-VITK-WARFARIN-CONSISTENCY")).toBe(true);
  });

  it("matches common Korean medication aliases to the same medication entity", () => {
    const response = runSafetyEngine(
      {
        profile: {
          selectedCompounds: ["vitamin k"],
          medications: ["와파린"],
          jurisdiction: "KR",
        },
        sort: "severity_desc",
      },
      knowledgeIndex,
    );

    const matchedIds = new Set(
      response.definitely_matched.map((match) => match.ruleId),
    );

    expect(matchedIds.has("RULE-VITK-WARFARIN-CONSISTENCY")).toBe(true);
  });

  it("matches common Korean condition aliases to the same condition entity", () => {
    const response = runSafetyEngine(
      {
        profile: {
          selectedCompounds: ["글루코사민"],
          conditions: ["당뇨병"],
          jurisdiction: "KR",
        },
        sort: "severity_desc",
      },
      knowledgeIndex,
    );

    const matchedIds = new Set(
      response.definitely_matched.map((match) => match.ruleId),
    );

    expect(matchedIds.has("RULE-GLUCOSAMINE-DIABETES-MONITOR")).toBe(true);
  });

  it("matches ingredient abbreviations such as vit k to the same ingredient entity", () => {
    const response = runSafetyEngine(
      {
        profile: {
          selectedCompounds: ["vit k"],
          medications: ["warfarin"],
          jurisdiction: "KR",
        },
        sort: "severity_desc",
      },
      knowledgeIndex,
    );

    const matchedIds = new Set(
      response.definitely_matched.map((match) => match.ruleId),
    );

    expect(matchedIds.has("RULE-VITK-WARFARIN-CONSISTENCY")).toBe(true);
  });
});

import { describe, expect, it } from "vitest";

import { predictLockedIndependentScenarios } from "@/src/lib/otc/independent-evaluation";
import type { OtcProduct, UserProfile } from "@/src/lib/otc/schema";

const evidence = { sourceId: "MFDS", locator: "p.1", url: "https://example.test" };
const product: OtcProduct = {
  productId: "P1", itemSequence: "1", productName: "시험약", classification: "일반의약품",
  authorizationStatus: "active", doseUnitLabel: "정", flags: [], evidence,
  ingredients: [{ ingredientId: "I1", nameKo: "시험성분", amountPerUnit: 500, unit: "mg", pharmacologicClasses: [], flags: [], evidence }],
};
const profile: UserProfile = { medications: [], redFlagSymptoms: [] };
const payload = { scenarioId: "S1", productInputs: [{ inputType: "verified_product" as const, itemSequence: "1", unitsPerDose: 1, dosesPerDay: 1 }], userProfile: profile, referenceLabel: null, prediction: null };
const runtime = { rulesReleased: 1, releasedRuleTypes: ["duplicate_ingredient"], products: [product] };

describe("OTC independent prediction gate", () => {
  it("refuses prediction until every human label is locked", () => {
    expect(() => predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "", prediction: "", status: "awaiting" }], [payload], runtime)).toThrow(/all_human/);
  });

  it("refuses draft-only runtimes", () => {
    expect(() => predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }], [payload], { ...runtime, rulesReleased: 0, releasedRuleTypes: [] })).toThrow(/released_runtime/);
  });

  it("refuses label or prediction leakage into blinded case payloads", () => {
    expect(() => predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }], [{ ...payload, referenceLabel: 0 as never }], runtime)).toThrow(/remain_blinded/);
  });

  it("uses released rule types only", () => {
    const duplicatePayload = { ...payload, productInputs: [...payload.productInputs, ...payload.productInputs] };
    expect(predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "1", prediction: "", status: "locked" }], [duplicatePayload], runtime)[0]).toMatchObject({ prediction: "1", findingRuleTypes: ["duplicate_ingredient"] });
    expect(predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }], [payload], runtime)[0].prediction).toBe("0");
  });
});

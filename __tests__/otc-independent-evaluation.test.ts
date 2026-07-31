import { describe, expect, it } from "vitest";

import { predictLockedIndependentScenarios } from "@/src/lib/otc/independent-evaluation";
import type { OtcProduct, ReleasedRulePolicy, UserProfile } from "@/src/lib/otc/schema";

const evidence = { sourceId: "MFDS", locator: "p.1", url: "https://example.test" };
const product: OtcProduct = {
  productId: "P1", itemSequence: "1", productName: "시험약", classification: "일반의약품",
  authorizationStatus: "active", doseUnitLabel: "정", flags: [], evidence,
  ingredients: [{ ingredientId: "I1", nameKo: "시험성분", amountPerUnit: 500, unit: "mg", pharmacologicClasses: [], flags: [], evidence }],
};
const profile: UserProfile = { medications: [], redFlagSymptoms: [] };
const payload = { scenarioId: "S1", productInputs: [{ inputType: "verified_product" as const, itemSequence: "1", unitsPerDose: 1, dosesPerDay: 1 }], userProfile: profile, referenceLabel: null, prediction: null };
const duplicateProduct = { ...product, productId: "P2", itemSequence: "2" };
const duplicatePolicy: ReleasedRulePolicy = {
  ruleId: "OTC-RULE-001",
  ruleType: "duplicate_ingredient",
  scope: "test-ingredient",
  lineageStatus: "mapped_from_v50_released_rule",
  applicability: { ingredientIds: ["I1"] },
  evidence: [{
    ...evidence,
    sourceVersion: `sha256:${"a".repeat(64)}`,
    ruleId: "OTC-RULE-001",
    productName: product.productName,
    itemSequence: product.itemSequence,
    excerptKo: "검증된 중복 규칙",
  }],
};
const runtime = {
  rulesReleased: 1,
  releasedRuleTypes: ["duplicate_ingredient"],
  releasedRules: [duplicatePolicy],
  products: [product, duplicateProduct],
};

describe("OTC independent prediction gate", () => {
  it("refuses prediction until every human label is locked", () => {
    expect(() => predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "", prediction: "", status: "awaiting" }], [payload], runtime)).toThrow(/all_human/);
  });

  it("refuses draft-only runtimes", () => {
    expect(() => predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }], [payload], { ...runtime, rulesReleased: 0, releasedRuleTypes: [], releasedRules: [] })).toThrow(/released_runtime/);
  });

  it("rejects duplicate released rule IDs before prediction", () => {
    expect(() =>
      predictLockedIndependentScenarios(
        [{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }],
        [payload],
        {
          ...runtime,
          rulesReleased: 2,
          releasedRuleTypes: ["duplicate_ingredient", "duplicate_ingredient"],
          releasedRules: [duplicatePolicy, { ...duplicatePolicy }],
        },
      ),
    ).toThrow(/released_runtime_duplicate_rule_id/);
  });

  it.each([
    ["empty applicability", { ...duplicatePolicy, applicability: {} }],
    ["empty scope", { ...duplicatePolicy, scope: "" }],
    [
      "mismatched evidence rule ID",
      {
        ...duplicatePolicy,
        evidence: duplicatePolicy.evidence.map((row) => ({
          ...row,
          ruleId: "OTC-RULE-999",
        })),
      },
    ],
    [
      "invalid evidence source version",
      {
        ...duplicatePolicy,
        evidence: duplicatePolicy.evidence.map((row) => ({
          ...row,
          sourceVersion: "sha256:not-a-digest",
        })),
      },
    ],
    [
      "mismatched evidence product",
      {
        ...duplicatePolicy,
        evidence: duplicatePolicy.evidence.map((row) => ({
          ...row,
          productName: "다른 제품",
        })),
      },
    ],
  ])("rejects a non-executable policy with %s", (_label, malformed) => {
    expect(() =>
      predictLockedIndependentScenarios(
        [{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }],
        [payload],
        { ...runtime, releasedRules: [malformed as ReleasedRulePolicy] },
      ),
    ).toThrow(/released_runtime_policy_integrity/);
  });

  it("rejects releasedRuleTypes that disagree with the released policies", () => {
    expect(() =>
      predictLockedIndependentScenarios(
        [{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }],
        [payload],
        { ...runtime, releasedRuleTypes: ["max_daily_dose"] },
      ),
    ).toThrow(/released_runtime_rule_types_mismatch/);
  });

  it("refuses label or prediction leakage into blinded case payloads", () => {
    expect(() => predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }], [{ ...payload, referenceLabel: 0 as never }], runtime)).toThrow(/remain_blinded/);
  });

  it("uses released rule types only", () => {
    const duplicatePayload = {
      ...payload,
      productInputs: [
        ...payload.productInputs,
        { ...payload.productInputs[0], itemSequence: "2" },
      ],
    };
    expect(predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "1", prediction: "", status: "locked" }], [duplicatePayload], runtime)[0]).toMatchObject({ prediction: "1", findingRuleTypes: ["duplicate_ingredient"] });
    expect(predictLockedIndependentScenarios([{ scenario_id: "S1", case_payload_ref: "S1.json", human_reference_label: "0", prediction: "", status: "locked" }], [payload], runtime)[0].prediction).toBe("0");
  });
});

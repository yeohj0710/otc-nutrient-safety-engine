import { evaluateOtcSafety } from "./engine";
import type { OtcProduct, SelectedProduct, UserProfile } from "./schema";

export type IndependentScenarioIndexRow = {
  scenario_id: string;
  case_payload_ref: string;
  human_reference_label: string;
  prediction: string;
  status: string;
};

type VerifiedProductInput = {
  inputType: "verified_product";
  itemSequence: string;
  unitsPerDose: number;
  dosesPerDay: number;
  hoursSincePreviousDose?: number;
  continuousDays?: number;
};

type ProductSearchInput = {
  inputType: "product_search_query";
  productNameQuery: string;
};

export type IndependentScenarioPayload = {
  scenarioId: string;
  productInputs: Array<VerifiedProductInput | ProductSearchInput>;
  userProfile: UserProfile;
  referenceLabel: null;
  prediction: null;
};

export type ReleasedRuntime = {
  rulesReleased: number;
  releasedRuleTypes: string[];
  products: OtcProduct[];
  urgentReferralBindings?: Array<{ itemSequence: string; terms: string[] }>;
};

export type IndependentPrediction = {
  scenarioId: string;
  prediction: "0" | "1";
  findingRuleTypes: string[];
};

export function predictLockedIndependentScenarios(
  rows: IndependentScenarioIndexRow[],
  payloads: IndependentScenarioPayload[],
  runtime: ReleasedRuntime,
): IndependentPrediction[] {
  if (!rows.length || rows.some((row) => !["0", "1"].includes(row.human_reference_label))) {
    throw new Error("all_human_reference_labels_must_be_locked_before_prediction");
  }
  if (rows.some((row) => row.prediction !== "")) throw new Error("predictions_already_present");
  if (!runtime.rulesReleased || runtime.releasedRuleTypes.length !== runtime.rulesReleased) {
    throw new Error("released_runtime_required_for_prediction");
  }

  const payloadById = new Map(payloads.map((payload) => [payload.scenarioId, payload]));
  const productBySequence = new Map(runtime.products.map((product) => [product.itemSequence, product]));
  const enabledRuleTypes = new Set(runtime.releasedRuleTypes);

  return rows.map((row) => {
    const payload = payloadById.get(row.scenario_id);
    if (!payload) throw new Error(`missing_case_payload:${row.scenario_id}`);
    if (payload.referenceLabel !== null || payload.prediction !== null) {
      throw new Error(`case_payload_must_remain_blinded:${row.scenario_id}`);
    }
    const selected: SelectedProduct[] = payload.productInputs.flatMap((input) => {
      if (input.inputType !== "verified_product") return [];
      const product = productBySequence.get(input.itemSequence);
      if (!product) throw new Error(`verified_product_missing_from_runtime:${row.scenario_id}:${input.itemSequence}`);
      return [{
        product,
        unitsPerDose: input.unitsPerDose,
        dosesPerDay: input.dosesPerDay,
        hoursSincePreviousDose: input.hoursSincePreviousDose,
        continuousDays: input.continuousDays,
      }];
    });
    const result = evaluateOtcSafety(selected, payload.userProfile, enabledRuleTypes, runtime.urgentReferralBindings ?? []);
    return {
      scenarioId: row.scenario_id,
      prediction: result.findings.length ? "1" : "0",
      findingRuleTypes: [...new Set(result.findings.map((finding) => finding.ruleType))].sort(),
    };
  });
}

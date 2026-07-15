import runtimeJson from "@/src/generated/research-v3-runtime.json";
import {
  researchV3InputSchema,
  researchV3RuntimeSchema,
  type ResearchV3Input,
  type ResearchV3Rule,
} from "./schema";

const runtime = researchV3RuntimeSchema.parse(runtimeJson);

function profileKey(input: ResearchV3Input) {
  if (!input.sex || input.age < 19) return null;
  return `${input.sex}_${input.age <= 29 ? "19_29" : "30_plus"}`;
}

function conditionValue(input: ResearchV3Input, key: string) {
  const mapping: Record<string, number | undefined> = {
    daily_total_ug: input.dailyTotalUg,
    daily_total_mg: input.dailyTotalMg,
    non_food_daily_total_mg: input.nonFoodDailyTotalMg,
  };
  return mapping[key];
}

function matches(rule: ResearchV3Rule, input: ResearchV3Input) {
  if (input.ingredientId !== rule.ingredientId) return false;
  const minimumAge = rule.conditions.age_min_years;
  if (typeof minimumAge === "number" && input.age < minimumAge) return false;

  for (const [key, threshold] of Object.entries(rule.conditions)) {
    if (!key.endsWith("_gt") || typeof threshold !== "number") continue;
    const value = conditionValue(input, key.slice(0, -3));
    if (typeof value !== "number" || value <= threshold) return false;
  }

  if (rule.conditions.daily_total_mg_gt_profile_threshold === true) {
    const thresholds = rule.conditions.profile_thresholds_mg;
    const key = profileKey(input);
    if (!key || typeof thresholds !== "object" || thresholds === null) return false;
    const threshold = thresholds[key];
    if (typeof threshold !== "number" || typeof input.dailyTotalMg !== "number" || input.dailyTotalMg <= threshold) {
      return false;
    }
  }
  return true;
}

export function evaluateResearchV3Draft(inputValue: ResearchV3Input) {
  const input = researchV3InputSchema.parse(inputValue);
  return {
    lineage: runtime.lineage,
    releaseStatus: runtime.releaseStatus,
    performanceClaimAllowed: false,
    matches: runtime.rules.filter((rule) => matches(rule, input)),
  } as const;
}

export function getResearchV3RuntimeMeta() {
  return {
    lineage: runtime.lineage,
    releaseStatus: runtime.releaseStatus,
    claimBoundary: runtime.claimBoundary,
    ruleCount: runtime.rules.length,
    releasedRuleCount: runtime.rules.filter((rule) => rule.reviewStatus === "released").length,
  } as const;
}

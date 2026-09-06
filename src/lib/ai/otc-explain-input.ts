import { z } from "zod";
import runtimeData from "@/src/generated/otc-runtime.json";
import { evaluateOtcSafety } from "@/src/lib/otc/engine";
import type { OtcProduct, ReleasedRulePolicy } from "@/src/lib/otc/schema";

const count = z.number().finite().min(0).max(100000);
const flag = z.boolean().optional();
const requestSchema = z.object({
  selected: z.array(z.object({
    productId: z.string().max(120), unitsPerDose: count, dosesPerDay: count,
    hoursSincePreviousDose: count.optional(), continuousDays: count.optional(),
  })).min(1).max(12),
  profile: z.object({
    ageYears: z.number().min(0).max(120).optional(),
    pregnant: flag, pregnancyTrimester: z.union([z.literal(1), z.literal(2), z.literal(3)]).optional(),
    lactating: flag, liverDisease: flag, kidneyDisease: flag, giBleedingOrUlcer: flag,
    hypertensionOrCardiovascularDisease: flag, willDrive: flag, alcohol: flag,
    medications: z.array(z.string().max(120)).max(30),
    redFlagSymptoms: z.array(z.string().max(120)).max(30),
  }),
});

/** 제품과 판정 근거는 서버 자료에서 읽는다. 요청으로 들어온 판정문은 사용하지 않는다. */
export function parseOtcExplainInput(value: unknown) {
  const parsed = requestSchema.safeParse(value);
  if (!parsed.success) return null;
  const data = runtimeData as { products: OtcProduct[]; releasedRules: ReleasedRulePolicy[] };
  if (new Set(parsed.data.selected.map(item => item.productId)).size !== parsed.data.selected.length) return null;
  const selected = parsed.data.selected.map(item => ({
    product: data.products.find(product => product.productId === item.productId), ...item,
  }));
  if (selected.some(item => !item.product)) return null;
  const hydrated = selected.map(item => ({ ...item, product: item.product! }));
  return {
    selected: hydrated, profile: parsed.data.profile,
    evaluation: evaluateOtcSafety(hydrated, parsed.data.profile, { releasedRules: data.releasedRules }),
    productNames: hydrated.map(item => item.product.productName),
    profileSummary: JSON.stringify(parsed.data.profile),
  };
}

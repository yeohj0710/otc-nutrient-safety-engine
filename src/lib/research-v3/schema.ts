import { z } from "zod";

const conditionValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.record(z.string(), z.number()),
]);

export const researchV3RuleSchema = z.object({
  id: z.string().min(1),
  ingredientId: z.string().min(1),
  conditions: z.record(z.string(), conditionValueSchema),
  exceptions: z.record(z.string(), conditionValueSchema),
  decisionLevel: z.enum(["informational", "monitor", "high"]),
  messageKo: z.string().min(1),
  nextActionKo: z.string().min(1),
  sourceId: z.string().min(1),
  locator: z.string().min(1),
  reviewStatus: z.enum(["draft", "legacy", "released"]),
  version: z.string().min(1),
});

export const researchV3RuntimeSchema = z.object({
  schemaVersion: z.literal("1.0.0"),
  lineage: z.literal("research_v3"),
  releaseStatus: z.literal("draft_not_for_clinical_use"),
  claimBoundary: z.string().min(1),
  rules: z.array(researchV3RuleSchema),
});

export const researchV3InputSchema = z.object({
  age: z.number().int().nonnegative(),
  sex: z.enum(["male", "female"]).optional(),
  ingredientId: z.string().min(1),
  dailyTotalUg: z.number().nonnegative().optional(),
  dailyTotalMg: z.number().nonnegative().optional(),
  nonFoodDailyTotalMg: z.number().nonnegative().optional(),
});

export type ResearchV3Rule = z.infer<typeof researchV3RuleSchema>;
export type ResearchV3Runtime = z.infer<typeof researchV3RuntimeSchema>;
export type ResearchV3Input = z.infer<typeof researchV3InputSchema>;

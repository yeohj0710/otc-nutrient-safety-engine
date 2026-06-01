import { z } from "zod";
import { zodTextFormat } from "openai/helpers/zod";

import { engineResponseSchema, severitySchema } from "@/src/types/knowledge";

const aiSeverityLabelSchema = z.enum(["금지/중단", "강한 주의", "일반 주의", "참고"]);
const aiRuleCardActionSchema = z.object({
  ruleId: z.string().min(1),
  recommendation: z.string().min(1),
});

export const aiExplanationSchema = z.object({
  summaryTitle: z.string().min(1),
  summaryParagraph: z.string().min(1),
  topAlerts: z.array(
    z.object({
      title: z.string().min(1),
      severity: aiSeverityLabelSchema,
      reason: z.string().min(1),
    }),
  ),
  groupedFindings: z.array(
    z.object({
      sectionTitle: z.string().min(1),
      items: z.array(z.string().min(1)),
    }),
  ),
  missingInformation: z.array(z.string().min(1)),
  userFriendlyNextSteps: z.array(z.string().min(1)),
  ruleCardActions: z.array(aiRuleCardActionSchema),
  disclaimer: z.string().min(1),
});

export const aiExplanationTextFormat = zodTextFormat(aiExplanationSchema, "nutrition_safety_ai_explanation", {
  description: "결정적 규칙 엔진 결과를 바탕으로 작성한 보수적인 한국어 사용자 설명",
});

export const aiExplainFilterSchema = z.object({
  severity: severitySchema.optional(),
  nutrientOrIngredient: z.string().optional(),
  pregnancyOrLactationOnly: z.boolean().optional(),
  medicationInteractionOnly: z.boolean().optional(),
  diseaseInteractionOnly: z.boolean().optional(),
  jurisdiction: z.string().optional(),
});

export const aiExplainRequestSchema = z.object({
  engineResponse: engineResponseSchema,
  profileSummary: z.string().min(1),
  selectedFilters: aiExplainFilterSchema.optional(),
});

export const aiExplainResponseSchema = z.discriminatedUnion("ok", [
  z.object({
    ok: z.literal(true),
    explanation: aiExplanationSchema,
    meta: z.object({
      cached: z.boolean(),
      model: z.string().min(1),
      requestId: z.string().min(1),
    }),
  }),
  z.object({
    ok: z.literal(false),
    reason: z.enum(["missing_api_key", "invalid_response", "timeout", "openai_error"]),
    notice: z.string().min(1),
  }),
]);

export type AiExplanation = z.infer<typeof aiExplanationSchema>;
export type AiExplainRequest = z.infer<typeof aiExplainRequestSchema>;
export type AiExplainResponse = z.infer<typeof aiExplainResponseSchema>;

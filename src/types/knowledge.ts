import { z } from "zod";

const jsonPrimitiveSchema = z.union([z.string(), z.number(), z.boolean(), z.null()]);
export type JsonPrimitive = z.infer<typeof jsonPrimitiveSchema>;

export type JsonValue =
  | JsonPrimitive
  | { [key: string]: JsonValue }
  | JsonValue[];

const jsonValueSchema: z.ZodType<JsonValue> = z.lazy(() =>
  z.union([jsonPrimitiveSchema, z.array(jsonValueSchema), z.record(z.string(), jsonValueSchema)]),
);

export const sourceTypeSchema = z.string().min(1);
export const severitySchema = z.enum(["contraindicated", "avoid", "warn", "monitor"]);
export const ruleClassificationSchema = z.enum([
  "definitely_matched",
  "possibly_relevant",
  "needs_more_info",
  "excluded",
]);
export const confidenceSchema = z.enum(["high", "medium", "low", "unknown"]);

export const knowledgeSourceSchema = z.object({
  id: z.string().min(1),
  sourceType: sourceTypeSchema,
  title: z.string().min(1),
  authors: z.array(z.string()).default([]),
  year: z.number().int().nullable(),
  journalOrPublisher: z.string().nullable(),
  jurisdiction: z.string().nullable(),
  urlOrIdentifier: z.string().nullable(),
  updatedAt: z.string().nullable(),
  evidenceLevel: z.string().nullable(),
  raw: z.record(z.string(), jsonValueSchema).default({}),
});

export const evidenceChunkSchema = z.object({
  id: z.string().min(1),
  sourceId: z.string().min(1),
  locatorType: z.string().nullable(),
  locatorValue: z.string().nullable(),
  evidenceType: z.string().nullable(),
  quoteOriginal: z.string().nullable().default(null),
  quoteTranslationKo: z.string().nullable().default(null),
  quoteLanguage: z.string().nullable().default(null),
  translationStatus: z.string().nullable().default(null),
  verificationStatus: z.string().nullable().default(null),
  extractionMethod: z.string().nullable().default(null),
  quoteOriginalIsShortExcerpt: z.boolean().nullable(),
  quoteCaptureStatus: z.string().nullable().default(null),
  copyrightScope: z.string().nullable().default(null),
  sourceAccessNote: z.string().nullable().default(null),
  usedInRuleIds: z.array(z.string()).default([]),
  quoteOriginalWordCount: z.number().int().nullable(),
  quoteFullSentenceAvailable: z.boolean().nullable(),
  verbatimNoteKo: z.string().nullable().default(null),
  verbatimQuote: z.string().nullable().default(null),
  translatedQuote: z.string().nullable().default(null),
  quote: z.string().nullable(),
  summary: z.string().nullable(),
  chunkText: z.string().nullable(),
  relevantEntities: z.array(z.string()).default([]),
  metadata: z.record(z.string(), jsonValueSchema).default({}),
});

export const ruleConditionSchema = z.object({
  id: z.string().min(1),
  field: z.string().min(1),
  operator: z.string().min(1),
  value: jsonValueSchema,
  requirementGroup: z.string().min(1),
  labelKo: z.string().nullable(),
});

export const ruleOutcomeSchema = z.object({
  action: z.string().min(1),
  messageShort: z.string().min(1),
  messageLong: z.string().min(1),
  monitoring: z.string().nullable(),
  exception: z.string().nullable(),
});

export const ingredientRecordSchema = z.object({
  id: z.string().min(1),
  nameKo: z.string().min(1),
  nameEn: z.string().nullable(),
  category: z.string().nullable(),
  forms: z.array(z.string()).default([]),
  aliases: z.array(z.string()).default([]),
  qualityNotes: z.string().nullable(),
});

export const safetyRuleSchema = z.object({
  id: z.string().min(1),
  groupId: z.string().nullable(),
  ingredientId: z.string().min(1),
  nutrientOrIngredient: z.string().min(1),
  nutrientForm: z.string().nullable(),
  ruleCategory: z.string().min(1),
  severity: severitySchema,
  priority: z.number().int(),
  jurisdiction: z.string().nullable(),
  populationTags: z.array(z.string()).default([]),
  conditions: z.array(ruleConditionSchema).default([]),
  threshold: z.number().nullable(),
  thresholdOperator: z.string().nullable(),
  unit: z.string().nullable(),
  scope: z.string().nullable(),
  messageShort: z.string().min(1),
  messageLong: z.string().min(1),
  action: z.string().min(1),
  contraindications: z.array(z.string()).default([]),
  interactionDrugs: z.array(z.string()).default([]),
  interactionDiseases: z.array(z.string()).default([]),
  pregnancyFlag: z.boolean().nullable(),
  lactationFlag: z.boolean().nullable(),
  smokerFlag: z.boolean().nullable(),
  ageMin: z.number().nullable(),
  ageMax: z.number().nullable(),
  sex: z.string().nullable(),
  evidenceChunkIds: z.array(z.string()).default([]),
  sourceIds: z.array(z.string()).default([]),
  confidence: confidenceSchema,
  lastReviewedAt: z.string().nullable(),
  outcome: ruleOutcomeSchema,
  rawAppliesWhen: z.record(z.string(), jsonValueSchema).default({}),
  raw: z.record(z.string(), jsonValueSchema).default({}),
});

export const candidateItemSchema = z.object({
  ingredientId: z.string().nullable().optional(),
  name: z.string().min(1),
  form: z.string().nullable().optional(),
  product: z.string().nullable().optional(),
  dailyIntakeValue: z.number().nullable().optional(),
  dailyIntakeUnit: z.string().nullable().optional(),
  longTermUseDays: z.number().int().nullable().optional(),
  sameDay: z.boolean().nullable().optional(),
  coingredients: z.array(z.string()).optional(),
});

export const personProfileSchema = z.object({
  age: z.number().int().nonnegative().nullable().optional(),
  sex: z.string().nullable().optional(),
  pregnancyStatus: z.string().nullable().optional(),
  lactationStatus: z.string().nullable().optional(),
  smokerStatus: z.string().nullable().optional(),
  medications: z.array(z.string()).optional(),
  conditions: z.array(z.string()).optional(),
  allergies: z.array(z.string()).optional(),
  selectedCompounds: z.array(z.string()).optional(),
  jurisdiction: z.string().optional(),
  memo: z.string().nullable().optional(),
  exposures: z.array(z.string()).optional(),
  devices: z.array(z.string()).optional(),
  immuneStatus: z.string().nullable().optional(),
  populationTags: z.array(z.string()).optional(),
  strictestMode: z.boolean().optional(),
});

export const engineQuerySchema = z.object({
  profile: personProfileSchema.default({ jurisdiction: "KR", strictestMode: false }),
  candidateItems: z.array(candidateItemSchema).optional(),
  filters: z
    .object({
      severity: z.array(severitySchema).optional(),
      nutrientOrIngredient: z.string().nullable().optional(),
      pregnancyOrLactationOnly: z.boolean().optional(),
      medicationInteractionOnly: z.boolean().optional(),
      diseaseInteractionOnly: z.boolean().optional(),
      jurisdiction: z.string().nullable().optional(),
    })
    .optional(),
  sort: z
    .enum(["severity_desc", "confidence_desc", "nutrient_name", "recently_reviewed"])
    .optional(),
});

export const conditionResultSchema = z.object({
  conditionId: z.string().min(1),
  field: z.string().min(1),
  requirementGroup: z.string().min(1),
  status: z.enum(["matched", "missing", "not_matched", "not_applicable"]),
  reason: z.string().min(1),
});

export const ruleMatchSchema = z.object({
  ruleId: z.string().min(1),
  classification: ruleClassificationSchema,
  matched: z.boolean(),
  matchScore: z.number(),
  matchedBecause: z.array(z.string()).default([]),
  notEvaluatedBecauseMissing: z.array(z.string()).default([]),
  needsMoreInfo: z.array(z.string()).default([]),
  resolvedSeverity: severitySchema,
  resolvedMessage: z.string().min(1),
  supportingSources: z.array(knowledgeSourceSchema).default([]),
  supportingEvidenceChunks: z.array(evidenceChunkSchema).default([]),
  rule: safetyRuleSchema,
  ingredient: ingredientRecordSchema.nullable(),
  evaluation: z.object({
    selectedIngredient: z.boolean(),
    conditionResults: z.array(conditionResultSchema).default([]),
    missingFields: z.array(z.string()).default([]),
    excludedReasons: z.array(z.string()).default([]),
  }),
});

export const knowledgeIndexSchema = z.object({
  meta: z.object({
    packageName: z.string().min(1),
    version: z.string().min(1),
    generatedAt: z.string().min(1),
    descriptionKo: z.string().nullable(),
    dataSource: z.enum(["knowledge_pack", "legacy_split_files"]),
    sourceCount: z.number().int(),
    ingredientCount: z.number().int(),
    evidenceChunkCount: z.number().int(),
    safetyRuleCount: z.number().int(),
    originalExcerptCount: z.number().int().default(0),
    verifiedAgainstSourceCount: z.number().int().default(0),
    supportedInferenceCount: z.number().int().default(0),
    pendingManualExtractionCount: z.number().int().default(0),
  }),
  sources: z.array(knowledgeSourceSchema),
  ingredients: z.array(ingredientRecordSchema),
  evidenceChunks: z.array(evidenceChunkSchema),
  safetyRules: z.array(safetyRuleSchema),
});

export const engineResponseSchema = z.object({
  generatedAt: z.string().min(1),
  query: engineQuerySchema,
  knowledgeMeta: knowledgeIndexSchema.shape.meta,
  totalCounts: z.object({
    definitely_matched: z.number().int(),
    possibly_relevant: z.number().int(),
    needs_more_info: z.number().int(),
    excluded: z.number().int(),
  }),
  definitely_matched: z.array(ruleMatchSchema),
  possibly_relevant: z.array(ruleMatchSchema),
  needs_more_info: z.array(ruleMatchSchema),
  excluded: z.array(ruleMatchSchema),
});

export type KnowledgeSource = z.infer<typeof knowledgeSourceSchema>;
export type EvidenceChunk = z.infer<typeof evidenceChunkSchema>;
export type RuleCondition = z.infer<typeof ruleConditionSchema>;
export type RuleOutcome = z.infer<typeof ruleOutcomeSchema>;
export type IngredientRecord = z.infer<typeof ingredientRecordSchema>;
export type SafetyRule = z.infer<typeof safetyRuleSchema>;
export type CandidateItem = z.infer<typeof candidateItemSchema>;
export type PersonProfile = z.infer<typeof personProfileSchema>;
export type EngineQuery = z.infer<typeof engineQuerySchema>;
export type ConditionResult = z.infer<typeof conditionResultSchema>;
export type RuleMatch = z.infer<typeof ruleMatchSchema>;
export type EngineResponse = z.infer<typeof engineResponseSchema>;
export type KnowledgeIndex = z.infer<typeof knowledgeIndexSchema>;

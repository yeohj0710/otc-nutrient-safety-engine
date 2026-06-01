import path from "node:path";
import { readFile, writeFile } from "node:fs/promises";

import { buildIngredientAliases } from "@/src/lib/knowledge/ingredient-aliases";
import {
  confidenceSchema,
  type IngredientRecord,
  ingredientRecordSchema,
  knowledgeIndexSchema,
  knowledgeSourceSchema,
  type JsonValue,
  type KnowledgeIndex,
  type RuleCondition,
  safetyRuleSchema,
} from "@/src/types/knowledge";

type RawSource = {
  source_id: string;
  title: string;
  source_type: string;
  organization?: string | null;
  jurisdiction?: string | null;
  publication_year?: number | null;
  publication_date?: string | null;
  url?: string | null;
  doi?: string | null;
  pmid?: string | null;
  authors?: string[] | string | null;
  journal?: string | null;
  evidence_tier?: string | null;
  [key: string]: unknown;
};

type RawIngredient = {
  ingredient_id: string;
  ingredient_name_ko: string;
  ingredient_name_en?: string | null;
  category?: string | null;
  forms?: string[] | null;
  matching_aliases_ko?: string[] | null;
  matching_aliases_en?: string[] | null;
  quality_notes_ko?: string | null;
};

type RawEvidenceChunk = {
  chunk_id: string;
  source_id: string;
  ingredient_ids?: string[] | null;
  locator_type?: string | null;
  locator_value?: string | null;
  locator?: {
    locator_type?: string | null;
    locator_value?: string | null;
  } | null;
  excerpt_verbatim?: string | null;
  excerpt_original?: string | null;
  excerpt_original_en?: string | null;
  excerpt_quote?: string | null;
  excerpt_translation_ko?: string | null;
  excerpt_summary_ko?: string | null;
  claim_type?: string | null;
  structured_claim?: Record<string, unknown> | null;
  confidence?: string | null;
  notes_ko?: string | null;
  evidence_type?: string | null;
  quote_original?: string | null;
  quote_language?: string | null;
  quote_translation_ko?: string | null;
  translation_status?: string | null;
  verification_status?: string | null;
  extraction_method?: string | null;
  quote_original_is_short_excerpt?: boolean | null;
  quote_capture_status?: string | null;
  copyright_scope?: string | null;
  source_access_note?: string | null;
  used_in_rule_ids?: string[] | null;
  quote_original_word_count?: number | null;
  quote_full_sentence_available?: boolean | null;
  verbatim_note_ko?: string | null;
  [key: string]: unknown;
};

type RawRule = {
  rule_id: string;
  rule_group_id?: string | null;
  ingredient_id: string;
  rule_name_ko: string;
  rule_category: string;
  severity: string;
  priority: number;
  jurisdiction?: string | null;
  applies_when?: Record<string, unknown>;
  threshold_operator?: string | null;
  threshold_value?: number | null;
  threshold_unit?: string | null;
  threshold_scope?: string | null;
  action_text_ko: string;
  rationale_ko: string;
  monitoring_ko?: string | null;
  exception_ko?: string | null;
  evidence_chunk_ids?: string[] | null;
  source_ids?: string[] | null;
  review_status?: string | null;
  [key: string]: unknown;
};

type RawKnowledgePack = {
  package_meta?: {
    package_name?: string;
    version?: string;
    generated_at?: string;
    description_ko?: string | null;
  };
  sources?: RawSource[];
  ingredients?: RawIngredient[];
  evidence_chunks?: RawEvidenceChunk[];
  safety_rules?: RawRule[];
};

type KnowledgeDataSource = "knowledge_pack" | "legacy_split_files";

function splitAuthors(authors: RawSource["authors"]) {
  if (!authors) {
    return [];
  }

  if (Array.isArray(authors)) {
    return authors.filter(Boolean);
  }

  return authors
    .split(/[,;|]/)
    .map((value) => value.trim())
    .filter(Boolean);
}

function getOptionalString(value: unknown) {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function firstNonEmptyString(...values: unknown[]) {
  for (const value of values) {
    const normalized = getOptionalString(value);
    if (normalized) {
      return normalized;
    }
  }

  return null;
}

function getOptionalNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getOptionalBoolean(value: unknown) {
  return typeof value === "boolean" ? value : null;
}

function toStringArray(values: unknown) {
  if (!Array.isArray(values)) {
    return [];
  }

  return values
    .map((value) => (typeof value === "string" ? value.trim() : String(value ?? "").trim()))
    .filter(Boolean);
}

function inferConfidence(rule: RawRule, chunks: RawEvidenceChunk[]) {
  if (rule.review_status === "starter_validated") {
    return confidenceSchema.parse("high");
  }

  if (rule.review_status === "starter_hypothesis") {
    return confidenceSchema.parse("low");
  }

  const confidences = chunks
    .map((chunk) => chunk.confidence)
    .filter((value): value is string => Boolean(value));

  if (confidences.includes("high")) {
    return confidenceSchema.parse("high");
  }

  if (confidences.includes("medium")) {
    return confidenceSchema.parse("medium");
  }

  if (confidences.includes("low")) {
    return confidenceSchema.parse("low");
  }

  return confidenceSchema.parse("unknown");
}

function conditionLabelKo(field: string) {
  switch (field) {
    case "age_years":
      return "연령 조건";
    case "candidate_daily_intake":
      return "일일 섭취량 조건";
    case "candidate_products_any":
      return "제품 유형 조건";
    case "coingredients_any":
      return "동시 성분 조건";
    case "devices_any":
      return "의료기기 조건";
    case "diseases_any":
      return "질환 조건";
    case "exposure_any":
      return "노출 이력 조건";
    case "immune_status_any":
      return "면역 상태 조건";
    case "ingredient_forms_any":
      return "성분 제형 조건";
    case "jurisdiction_preference_any":
      return "관할권 조건";
    case "long_term_use_days":
      return "장기 복용 조건";
    case "medications_any":
    case "or_medications_any":
      return "약물 상호작용 조건";
    case "or_lactating":
      return "수유 조건";
    case "or_pregnant_or_lactating":
      return "임신 또는 수유 조건";
    case "or_use_general":
      return "일반 사용 경고";
    case "population_any":
      return "특정 인구집단 조건";
    case "pregnancy_status_any":
      return "임신 상태 조건";
    case "same_day":
      return "같은 날 복용 조건";
    case "smoking_status_any":
      return "흡연 상태 조건";
    default:
      return `${field} 조건`;
  }
}

function buildRequirementGroup(field: string, appliesWhen: Record<string, unknown>) {
  const has = (candidate: string) => Object.prototype.hasOwnProperty.call(appliesWhen, candidate);

  if ((field === "pregnancy_status_any" || field === "or_lactating") && has("pregnancy_status_any") && has("or_lactating")) {
    return "pregnancy_or_lactation";
  }

  if (
    (field === "population_any" || field === "or_pregnant_or_lactating") &&
    has("population_any") &&
    has("or_pregnant_or_lactating")
  ) {
    return "population_or_pregnancy";
  }

  if ((field === "diseases_any" || field === "or_medications_any") && has("diseases_any") && has("or_medications_any")) {
    return "disease_or_medication";
  }

  if ((field === "diseases_any" || field === "or_use_general") && has("diseases_any") && has("or_use_general")) {
    return "disease_or_general_use";
  }

  if ((field === "smoking_status_any" || field === "exposure_any") && has("smoking_status_any") && has("exposure_any")) {
    return "smoking_or_exposure";
  }

  if ((field === "immune_status_any" || field === "devices_any") && has("immune_status_any") && has("devices_any")) {
    return "immune_or_device";
  }

  return field;
}

function buildRuleConditions(appliesWhen: Record<string, unknown>): RuleCondition[] {
  return Object.entries(appliesWhen).map(([field, value]) => ({
    id: `${field}:${JSON.stringify(value)}`,
    field,
    operator: Array.isArray(value) ? "includes_any" : typeof value === "object" && value ? "structured" : "equals",
    value: value as JsonValue,
    requirementGroup: buildRequirementGroup(field, appliesWhen),
    labelKo: conditionLabelKo(field),
  }));
}

function buildIngredientRecord(rawIngredient: RawIngredient) {
  const aliases = buildIngredientAliases({
    id: rawIngredient.ingredient_id,
    nameKo: rawIngredient.ingredient_name_ko,
    nameEn: rawIngredient.ingredient_name_en ?? null,
    forms: rawIngredient.forms ?? [],
    matchingAliasesKo: rawIngredient.matching_aliases_ko ?? [],
    matchingAliasesEn: rawIngredient.matching_aliases_en ?? [],
  });

  return ingredientRecordSchema.parse({
    id: rawIngredient.ingredient_id,
    nameKo: rawIngredient.ingredient_name_ko,
    nameEn: rawIngredient.ingredient_name_en ?? null,
    category: rawIngredient.category ?? null,
    forms: rawIngredient.forms ?? [],
    aliases: [...new Set(aliases)],
    qualityNotes: rawIngredient.quality_notes_ko ?? null,
  });
}

function buildSafetyRule(
  rawRule: RawRule,
  ingredient: IngredientRecord | undefined,
  evidenceChunks: RawEvidenceChunk[],
  generatedAt: string,
) {
  const appliesWhen = rawRule.applies_when ?? {};
  const medicationsAny = Array.isArray(appliesWhen.medications_any) ? appliesWhen.medications_any : [];
  const orMedicationsAny = Array.isArray(appliesWhen.or_medications_any) ? appliesWhen.or_medications_any : [];
  const diseasesAny = Array.isArray(appliesWhen.diseases_any) ? appliesWhen.diseases_any : [];
  const pregnancyValues = Array.isArray(appliesWhen.pregnancy_status_any) ? appliesWhen.pregnancy_status_any : [];
  const smokerValues = Array.isArray(appliesWhen.smoking_status_any) ? appliesWhen.smoking_status_any : [];
  const ageRule = typeof appliesWhen.age_years === "object" && appliesWhen.age_years ? (appliesWhen.age_years as { min?: number; max?: number }) : {};
  const ingredientFormsAny = Array.isArray(appliesWhen.ingredient_forms_any) ? appliesWhen.ingredient_forms_any : [];

  return safetyRuleSchema.parse({
    id: rawRule.rule_id,
    groupId: rawRule.rule_group_id ?? null,
    ingredientId: rawRule.ingredient_id,
    nutrientOrIngredient: ingredient?.nameKo ?? rawRule.ingredient_id,
    nutrientForm: ingredientFormsAny.length === 1 ? String(ingredientFormsAny[0]) : null,
    ruleCategory: rawRule.rule_category,
    severity: rawRule.severity,
    priority: rawRule.priority,
    jurisdiction: rawRule.jurisdiction ?? null,
    populationTags: Array.isArray(appliesWhen.population_any)
      ? appliesWhen.population_any.map((value) => String(value))
      : [],
    conditions: buildRuleConditions(appliesWhen),
    threshold: rawRule.threshold_value ?? null,
    thresholdOperator: rawRule.threshold_operator ?? null,
    unit: rawRule.threshold_unit ?? null,
    scope: rawRule.threshold_scope ?? null,
    messageShort: rawRule.action_text_ko,
    messageLong: rawRule.rationale_ko,
    action: rawRule.action_text_ko,
    contraindications: rawRule.severity === "contraindicated" ? [rawRule.action_text_ko] : [],
    interactionDrugs: [...new Set([...medicationsAny, ...orMedicationsAny].map((value) => String(value)))],
    interactionDiseases: [...new Set(diseasesAny.map((value) => String(value)))],
    pregnancyFlag: pregnancyValues.length > 0 || appliesWhen.or_pregnant_or_lactating === true ? true : null,
    lactationFlag: appliesWhen.or_lactating === true || appliesWhen.or_pregnant_or_lactating === true ? true : null,
    smokerFlag: smokerValues.length > 0 ? true : null,
    ageMin: typeof ageRule.min === "number" ? ageRule.min : null,
    ageMax: typeof ageRule.max === "number" ? ageRule.max : null,
    sex: null,
    evidenceChunkIds: rawRule.evidence_chunk_ids ?? [],
    sourceIds: rawRule.source_ids ?? [],
    confidence: inferConfidence(rawRule, evidenceChunks),
    lastReviewedAt: generatedAt,
    outcome: {
      action: rawRule.action_text_ko,
      messageShort: rawRule.action_text_ko,
      messageLong: rawRule.rationale_ko,
      monitoring: rawRule.monitoring_ko ?? null,
      exception: rawRule.exception_ko ?? null,
    },
    rawAppliesWhen: appliesWhen,
    raw: rawRule,
  });
}

function ensureKnowledgePackSections(knowledgePack: RawKnowledgePack) {
  const requiredSections = [
    "sources",
    "ingredients",
    "evidence_chunks",
    "safety_rules",
  ] as const satisfies ReadonlyArray<keyof RawKnowledgePack>;

  for (const section of requiredSections) {
    if (!Array.isArray(knowledgePack[section])) {
      throw new Error(`data/knowledge_pack.json is missing a valid "${section}" array.`);
    }
  }
}

async function readLegacyKnowledgePack(projectRoot: string): Promise<RawKnowledgePack> {
  const [sourcesRaw, ingredientsRaw, evidenceRaw, rulesRaw] = await Promise.all([
    readFile(path.join(projectRoot, "data", "source_registry.json"), "utf8"),
    readFile(path.join(projectRoot, "data", "ingredients.json"), "utf8"),
    readFile(path.join(projectRoot, "data", "evidence_chunks.json"), "utf8"),
    readFile(path.join(projectRoot, "data", "safety_rules.json"), "utf8"),
  ]);

  return {
    package_meta: {
      package_name: "fallback_local_pack",
      version: "0.0.0",
      generated_at: new Date().toISOString(),
      description_ko: null,
    },
    sources: JSON.parse(sourcesRaw) as RawSource[],
    ingredients: JSON.parse(ingredientsRaw) as RawIngredient[],
    evidence_chunks: JSON.parse(evidenceRaw) as RawEvidenceChunk[],
    safety_rules: JSON.parse(rulesRaw) as RawRule[],
  };
}

async function readKnowledgePack(projectRoot: string): Promise<{
  knowledgePack: RawKnowledgePack;
  dataSource: KnowledgeDataSource;
}> {
  const knowledgePackPath = path.join(projectRoot, "data", "knowledge_pack.json");

  try {
    const knowledgePackRaw = await readFile(knowledgePackPath, "utf8");
    const knowledgePack = JSON.parse(knowledgePackRaw) as RawKnowledgePack;
    ensureKnowledgePackSections(knowledgePack);

    return {
      knowledgePack,
      dataSource: "knowledge_pack",
    };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      throw error;
    }

    return {
      knowledgePack: await readLegacyKnowledgePack(projectRoot),
      dataSource: "legacy_split_files",
    };
  }
}

export async function buildKnowledgeIndex(projectRoot: string) {
  const { knowledgePack, dataSource } = await readKnowledgePack(projectRoot);
  const generatedAt = knowledgePack.package_meta?.generated_at ?? new Date().toISOString();

  const ingredients = (knowledgePack.ingredients ?? []).map(buildIngredientRecord);
  const ingredientMap = new Map(ingredients.map((ingredient) => [ingredient.id, ingredient]));

  const sources = (knowledgePack.sources ?? []).map((rawSource) =>
    knowledgeSourceSchema.parse({
      id: rawSource.source_id,
      sourceType: rawSource.source_type,
      title: rawSource.title,
      authors: splitAuthors(rawSource.authors),
      year: rawSource.publication_year ?? null,
      journalOrPublisher: rawSource.journal ?? rawSource.organization ?? null,
      jurisdiction: rawSource.jurisdiction ?? null,
      urlOrIdentifier: rawSource.url ?? rawSource.doi ?? rawSource.pmid ?? null,
      updatedAt: rawSource.publication_date ?? generatedAt,
      evidenceLevel: rawSource.evidence_tier ?? null,
      raw: rawSource,
    }),
  );

  const derivedRuleIdsByChunk = new Map<string, Set<string>>();
  for (const rawRule of knowledgePack.safety_rules ?? []) {
    for (const chunkId of rawRule.evidence_chunk_ids ?? []) {
      if (!derivedRuleIdsByChunk.has(chunkId)) {
        derivedRuleIdsByChunk.set(chunkId, new Set());
      }

      derivedRuleIdsByChunk.get(chunkId)!.add(rawRule.rule_id);
    }
  }

  const evidenceChunks = (knowledgePack.evidence_chunks ?? []).map((rawChunk) => {
    const locatorType = firstNonEmptyString(
      rawChunk.locator?.locator_type,
      rawChunk.locator_type,
    );
    const locatorValue = firstNonEmptyString(
      rawChunk.locator?.locator_value,
      rawChunk.locator_value,
    );
    const verbatimQuote = firstNonEmptyString(
      rawChunk.quote_original,
      rawChunk.excerpt_verbatim,
      rawChunk.excerpt_original,
      rawChunk.excerpt_original_en,
      rawChunk.excerpt_quote,
      rawChunk.verbatim_quote,
      rawChunk.original_quote,
      rawChunk.quote_en,
    );
    const translatedQuote = firstNonEmptyString(
      rawChunk.quote_translation_ko,
      rawChunk.excerpt_translation_ko,
      rawChunk.excerpt_summary_ko,
      rawChunk.translation_ko,
      rawChunk.summary_ko,
    );
    const summary = firstNonEmptyString(
      rawChunk.excerpt_summary_ko,
      rawChunk.summary_ko,
      rawChunk.notes_ko,
      translatedQuote,
      verbatimQuote,
    );
    const chunkText = firstNonEmptyString(
      rawChunk.notes_ko,
      summary,
      verbatimQuote,
    );
    const usedInRuleIds = [
      ...new Set([
        ...toStringArray(rawChunk.used_in_rule_ids),
        ...Array.from(derivedRuleIdsByChunk.get(rawChunk.chunk_id) ?? []),
      ]),
    ];

    return {
      id: rawChunk.chunk_id,
      sourceId: rawChunk.source_id,
      locatorType,
      locatorValue,
      evidenceType: firstNonEmptyString(rawChunk.evidence_type),
      quoteOriginal: verbatimQuote,
      quoteTranslationKo: firstNonEmptyString(rawChunk.quote_translation_ko, translatedQuote),
      quoteLanguage: firstNonEmptyString(rawChunk.quote_language),
      translationStatus: firstNonEmptyString(rawChunk.translation_status),
      verificationStatus: firstNonEmptyString(rawChunk.verification_status),
      extractionMethod: firstNonEmptyString(rawChunk.extraction_method),
      quoteOriginalIsShortExcerpt: getOptionalBoolean(rawChunk.quote_original_is_short_excerpt),
      quoteCaptureStatus: firstNonEmptyString(rawChunk.quote_capture_status),
      copyrightScope: firstNonEmptyString(rawChunk.copyright_scope),
      sourceAccessNote: firstNonEmptyString(rawChunk.source_access_note),
      usedInRuleIds,
      quoteOriginalWordCount: getOptionalNumber(rawChunk.quote_original_word_count),
      quoteFullSentenceAvailable: getOptionalBoolean(rawChunk.quote_full_sentence_available),
      verbatimNoteKo: firstNonEmptyString(rawChunk.verbatim_note_ko),
      verbatimQuote,
      translatedQuote,
      quote: verbatimQuote ?? translatedQuote ?? summary,
      summary,
      chunkText,
      relevantEntities: rawChunk.ingredient_ids ?? [],
      metadata: {
        claimType: rawChunk.claim_type ?? null,
        structuredClaim: rawChunk.structured_claim ?? null,
        confidence: rawChunk.confidence ?? null,
        notesKo: rawChunk.notes_ko ?? null,
      },
    };
  });

  const rawEvidenceMap = new Map((knowledgePack.evidence_chunks ?? []).map((chunk) => [chunk.chunk_id, chunk]));

  const safetyRules = (knowledgePack.safety_rules ?? []).map((rawRule) => {
    const ruleEvidenceChunks = (rawRule.evidence_chunk_ids ?? [])
      .map((chunkId) => rawEvidenceMap.get(chunkId))
      .filter((chunk): chunk is RawEvidenceChunk => Boolean(chunk));

    return buildSafetyRule(rawRule, ingredientMap.get(rawRule.ingredient_id), ruleEvidenceChunks, generatedAt);
  });

  const originalExcerptCount = evidenceChunks.filter((chunk) => Boolean(chunk.quoteOriginal)).length;
  const verifiedAgainstSourceCount = evidenceChunks.filter(
    (chunk) => chunk.verificationStatus === "verified_against_source",
  ).length;
  const supportedInferenceCount = evidenceChunks.filter(
    (chunk) => chunk.verificationStatus === "supported_inference",
  ).length;
  const pendingManualExtractionCount = evidenceChunks.filter(
    (chunk) => chunk.verificationStatus === "pending_manual_extraction",
  ).length;

  return knowledgeIndexSchema.parse({
    meta: {
      packageName: knowledgePack.package_meta?.package_name ?? "knowledge_pack",
      version: knowledgePack.package_meta?.version ?? "0.0.0",
      generatedAt,
      descriptionKo: knowledgePack.package_meta?.description_ko ?? null,
      dataSource,
      sourceCount: sources.length,
      ingredientCount: ingredients.length,
      evidenceChunkCount: evidenceChunks.length,
      safetyRuleCount: safetyRules.length,
      originalExcerptCount,
      verifiedAgainstSourceCount,
      supportedInferenceCount,
      pendingManualExtractionCount,
    },
    sources,
    ingredients,
    evidenceChunks,
    safetyRules,
  }) as KnowledgeIndex;
}

export async function writeKnowledgeIndex(projectRoot: string) {
  const outputPath = path.join(projectRoot, "src", "generated", "knowledge-index.json");
  const result = await buildKnowledgeIndex(projectRoot);
  await writeFile(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  return result;
}

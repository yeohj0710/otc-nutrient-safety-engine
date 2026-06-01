import "server-only";

import { readFileSync, statSync } from "node:fs";
import path from "node:path";

import knowledgeIndexJson from "@/src/generated/knowledge-index.json";
import {
  getConditionAliases,
  getConditionDisplayLabel,
  getConditionPresetCanonicalValues,
} from "@/src/lib/knowledge/condition-aliases";
import {
  getMedicationAliases,
  getMedicationDisplayLabel,
} from "@/src/lib/knowledge/medication-aliases";
import {
  getEvidenceContextExcerpt,
  getEvidenceContextSummary,
  getEvidenceLocatorText,
  getEvidencePrimaryExcerpt,
  getEvidenceRepresentativeExcerpt,
  getEvidenceRepresentativeExcerptLabel,
  getEvidenceSummaryExcerpt,
  getEvidenceTranslationExcerpt,
  getSourceReferenceLinks,
  getSourceTrustSummary,
  hasOriginalEvidenceExcerpt,
  isShortOriginalEvidenceExcerpt,
  pickRepresentativeEvidenceChunk,
  sortEvidenceChunksByPriority,
  sortSourcesByPriority,
} from "@/src/lib/references";
import {
  knowledgeIndexSchema,
  type EvidenceChunk,
  type KnowledgeIndex,
  type KnowledgeSource,
  type SafetyRule,
} from "@/src/types/knowledge";

const knowledgeIndex = knowledgeIndexSchema.parse(
  knowledgeIndexJson,
) as KnowledgeIndex;
const generatedKnowledgeIndexPath = path.join(
  process.cwd(),
  "src",
  "generated",
  "knowledge-index.json",
);

let developmentKnowledgeIndex: KnowledgeIndex | null = null;
let developmentKnowledgeIndexMtimeMs = -1;

function getDevelopmentKnowledgeIndex() {
  try {
    const fileStat = statSync(generatedKnowledgeIndexPath);

    if (
      developmentKnowledgeIndex &&
      fileStat.mtimeMs === developmentKnowledgeIndexMtimeMs
    ) {
      return developmentKnowledgeIndex;
    }

    const rawJson = readFileSync(generatedKnowledgeIndexPath, "utf8");
    const parsed = knowledgeIndexSchema.parse(
      JSON.parse(rawJson),
    ) as KnowledgeIndex;

    developmentKnowledgeIndex = parsed;
    developmentKnowledgeIndexMtimeMs = fileStat.mtimeMs;

    return parsed;
  } catch {
    return knowledgeIndex;
  }
}

export function getKnowledgeIndex() {
  return process.env.NODE_ENV === "development"
    ? getDevelopmentKnowledgeIndex()
    : knowledgeIndex;
}

export function getKnowledgeMeta() {
  return getKnowledgeIndex().meta;
}

export function getIngredientOptions() {
  return getKnowledgeIndex().ingredients.map((ingredient) => ({
    id: ingredient.id,
    label: ingredient.nameKo,
    aliases: ingredient.aliases,
    category: ingredient.category,
  }));
}

function humanizeExplorerValue(value: string) {
  return value.replace(/_/g, " ").replace(/\s+/g, " ").trim();
}

function getPreferredReferenceLink(
  links: Array<{ label: string; url: string }>,
) {
  return (
    links.find((link) => link.label === "DOI") ??
    links.find((link) => link.label === "PDF 원문") ??
    links.find((link) => link.label === "원문/기관 페이지") ??
    links.find((link) => link.label === "PubMed") ??
    links[0] ??
    null
  );
}

function buildMedicationExplorerOptions(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))]
    .sort((left, right) =>
      getMedicationDisplayLabel(left).localeCompare(
        getMedicationDisplayLabel(right),
        "ko",
      ),
    )
    .map((value) => ({
      label: getMedicationDisplayLabel(value),
      canonicalValue: humanizeExplorerValue(value),
      aliases: [
        ...new Set([
          value,
          humanizeExplorerValue(value),
          ...getMedicationAliases(value),
        ]),
      ],
    }));
}

function buildConditionExplorerOptions(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))]
    .sort((left, right) =>
      getConditionDisplayLabel(left).localeCompare(
        getConditionDisplayLabel(right),
        "ko",
      ),
    )
    .map((value) => ({
      label: getConditionDisplayLabel(value),
      canonicalValue: humanizeExplorerValue(value),
      aliases: [
        ...new Set([
          value,
          humanizeExplorerValue(value),
          ...getConditionAliases(value),
        ]),
      ],
    }));
}

export function getSourceById(sourceId: string) {
  return (
    getKnowledgeIndex().sources.find((source) => source.id === sourceId) ?? null
  );
}

export function getRuleById(ruleId: string) {
  return (
    getKnowledgeIndex().safetyRules.find((rule) => rule.id === ruleId) ?? null
  );
}

export function getIngredientById(ingredientId: string) {
  return (
    getKnowledgeIndex().ingredients.find(
      (ingredient) => ingredient.id === ingredientId,
    ) ?? null
  );
}

export function getEvidenceChunkById(chunkId: string) {
  return (
    getKnowledgeIndex().evidenceChunks.find((chunk) => chunk.id === chunkId) ??
    null
  );
}

export function buildReferenceBundle(rule: SafetyRule) {
  const supportingSources = rule.sourceIds
    .map((sourceId) => getSourceById(sourceId))
    .filter((source): source is KnowledgeSource => Boolean(source));
  const supportingEvidenceChunks = rule.evidenceChunkIds
    .map((chunkId) => getEvidenceChunkById(chunkId))
    .filter((chunk): chunk is EvidenceChunk => Boolean(chunk));
  const ingredient = getIngredientById(rule.ingredientId);

  return {
    rule,
    supportingSources,
    supportingEvidenceChunks,
    ingredient,
  };
}

export function getRulesBySourceId(sourceId: string) {
  return getKnowledgeIndex().safetyRules.filter((rule) =>
    rule.sourceIds.includes(sourceId),
  );
}

export function getRulesByEvidenceChunkId(chunkId: string) {
  return getKnowledgeIndex().safetyRules.filter((rule) =>
    rule.evidenceChunkIds.includes(chunkId),
  );
}

export function getEvidenceChunksBySourceId(sourceId: string) {
  return getKnowledgeIndex().evidenceChunks.filter(
    (chunk) => chunk.sourceId === sourceId,
  );
}

export function getSourceDetail(sourceId: string) {
  const source = getSourceById(sourceId);
  if (!source) {
    return null;
  }

  const evidenceChunks = getEvidenceChunksBySourceId(sourceId);
  const linkedRules = getRulesBySourceId(sourceId);

  return {
    source,
    evidenceChunks,
    linkedRules,
  };
}

export function getRuleDetail(ruleId: string) {
  const rule = getRuleById(ruleId);
  if (!rule) {
    return null;
  }

  const supportingSources = rule.sourceIds
    .map((sourceId) => getSourceById(sourceId))
    .filter((source): source is KnowledgeSource => Boolean(source));
  const supportingEvidenceChunks = rule.evidenceChunkIds
    .map((chunkId) => getEvidenceChunkById(chunkId))
    .filter((chunk): chunk is EvidenceChunk => Boolean(chunk));

  return {
    rule,
    ingredient: getIngredientById(rule.ingredientId),
    supportingSources,
    supportingEvidenceChunks,
  };
}

export function getSourceBrowseData() {
  const index = getKnowledgeIndex();

  return index.sources.map((source) => ({
    id: source.id,
    title: source.title,
    sourceType: source.sourceType,
    year: source.year,
    jurisdiction: source.jurisdiction,
    evidenceLevel: source.evidenceLevel,
    journalOrPublisher: source.journalOrPublisher,
    linkedRuleCount: getRulesBySourceId(source.id).length,
    linkedChunkCount: getEvidenceChunksBySourceId(source.id).length,
  }));
}

export function getRuleBrowseData() {
  return getKnowledgeIndex().safetyRules.map((rule) => ({
    id: rule.id,
    ingredientId: rule.ingredientId,
    nutrientOrIngredient: rule.nutrientOrIngredient,
    severity: rule.severity,
    jurisdiction: rule.jurisdiction,
    ruleCategory: rule.ruleCategory,
    confidence: rule.confidence,
    lastReviewedAt: rule.lastReviewedAt,
  }));
}

export function getIngredientReferenceDetail(ingredientId: string) {
  const ingredient = getIngredientById(ingredientId);
  if (!ingredient) {
    return null;
  }

  const index = getKnowledgeIndex();
  const linkedRules = index.safetyRules.filter(
    (rule) => rule.ingredientId === ingredientId,
  );
  const referencedChunkIds = new Set(
    linkedRules.flatMap((rule) => rule.evidenceChunkIds),
  );

  const linkedEvidenceChunks = index.evidenceChunks.filter(
    (chunk) =>
      referencedChunkIds.has(chunk.id) ||
      chunk.relevantEntities.includes(ingredientId),
  );

  const linkedSourceIds = new Set<string>([
    ...linkedRules.flatMap((rule) => rule.sourceIds),
    ...linkedEvidenceChunks.map((chunk) => chunk.sourceId),
  ]);

  const linkedSources = [...linkedSourceIds]
    .map((sourceId) => getSourceById(sourceId))
    .filter((source): source is KnowledgeSource => Boolean(source));

  const verifiedExcerptCount = linkedEvidenceChunks.filter(
    (chunk) =>
      chunk.verificationStatus === "verified_against_source" &&
      Boolean(chunk.quoteOriginal ?? chunk.verbatimQuote),
  ).length;

  return {
    ingredient,
    linkedRules,
    linkedSources,
    linkedEvidenceChunks,
    counts: {
      rules: linkedRules.length,
      sources: linkedSources.length,
      evidenceChunks: linkedEvidenceChunks.length,
      verifiedExcerpts: verifiedExcerptCount,
    },
  };
}

export function getIngredientReferenceBrowseData() {
  return getKnowledgeIndex()
    .ingredients.map((ingredient) => {
      const detail = getIngredientReferenceDetail(ingredient.id);
      const sourceLookup = new Map(
        (detail?.linkedSources ?? []).map((source) => [source.id, source]),
      );
      const sortedSources = sortSourcesByPriority(detail?.linkedSources ?? []);
      const sortedEvidenceChunks = sortEvidenceChunksByPriority(
        detail?.linkedEvidenceChunks ?? [],
        sourceLookup,
      );
      const references = sortedSources.map((source) => {
        const sourceChunks = sortedEvidenceChunks.filter(
          (chunk) => chunk.sourceId === source.id,
        );
        const primaryChunk =
          pickRepresentativeEvidenceChunk(sourceChunks) ??
          sourceChunks[0] ??
          null;
        const primaryLink = getPreferredReferenceLink(
          getSourceReferenceLinks(source),
        );
        const representativeText = primaryChunk
          ? getEvidenceRepresentativeExcerpt(primaryChunk)
          : null;
        const representativeLabel = primaryChunk
          ? getEvidenceRepresentativeExcerptLabel(primaryChunk)
          : "근거 문장";
        const contextSummary = primaryChunk
          ? getEvidenceContextSummary(primaryChunk)
          : null;
        const contextExcerpt = primaryChunk
          ? getEvidenceContextExcerpt(primaryChunk)
          : null;
        const summaryExcerpt = primaryChunk
          ? getEvidenceSummaryExcerpt(primaryChunk)
          : null;
        const translation = primaryChunk
          ? getEvidenceTranslationExcerpt(primaryChunk)
          : null;
        const locatorText = primaryChunk
          ? getEvidenceLocatorText(primaryChunk)
          : null;
        const originalFragment =
          primaryChunk &&
          hasOriginalEvidenceExcerpt(primaryChunk) &&
          isShortOriginalEvidenceExcerpt(primaryChunk)
            ? getEvidencePrimaryExcerpt(primaryChunk)
            : null;

        return {
          sourceId: source.id,
          title: source.title,
          trustSummary: getSourceTrustSummary(source),
          year: source.year,
          jurisdiction: source.jurisdiction,
          journalOrPublisher: source.journalOrPublisher,
          primaryLink,
          representativeLabel,
          representativeText,
          contextSummary,
          contextExcerpt,
          summaryExcerpt,
          translation,
          locatorText,
          originalFragment,
        };
      });

      return {
        id: ingredient.id,
        nameKo: ingredient.nameKo,
        nameEn: ingredient.nameEn,
        category: ingredient.category,
        aliases: ingredient.aliases,
        sourceCount: detail?.counts.sources ?? 0,
        evidenceChunkCount: detail?.counts.evidenceChunks ?? 0,
        ruleCount: detail?.counts.rules ?? 0,
        verifiedExcerptCount: detail?.counts.verifiedExcerpts ?? 0,
        references,
      };
    })
    .sort((left, right) => {
      const sourceDifference = right.sourceCount - left.sourceCount;
      if (sourceDifference !== 0) return sourceDifference;

      const evidenceDifference =
        right.evidenceChunkCount - left.evidenceChunkCount;
      if (evidenceDifference !== 0) return evidenceDifference;

      return left.nameKo.localeCompare(right.nameKo, "ko");
    });
}

export function getExplorerMetadata() {
  const index = getKnowledgeIndex();
  const medicationValues = [
    ...index.safetyRules.flatMap((rule) => rule.interactionDrugs),
    ...index.safetyRules.flatMap((rule) =>
      rule.conditions
        .filter((condition) =>
          ["medications_any", "or_medications_any"].includes(condition.field),
        )
        .flatMap((condition) =>
          Array.isArray(condition.value)
            ? condition.value.map((item) => String(item))
            : [],
        ),
    ),
  ];
  const conditionValues = [
    ...index.safetyRules.flatMap((rule) => rule.interactionDiseases),
    ...index.safetyRules.flatMap((rule) =>
      rule.conditions
        .filter((condition) => condition.field === "diseases_any")
        .flatMap((condition) =>
          Array.isArray(condition.value)
            ? condition.value.map((item) => String(item))
            : [],
        ),
    ),
    ...getConditionPresetCanonicalValues(),
  ];

  return {
    meta: index.meta,
    ingredients: getIngredientOptions(),
    medicationOptions: buildMedicationExplorerOptions(medicationValues),
    conditionOptions: buildConditionExplorerOptions(conditionValues),
    sources: index.sources.map((source) => ({
      id: source.id,
      title: source.title,
      jurisdiction: source.jurisdiction,
      evidenceLevel: source.evidenceLevel,
    })),
    sourceEvidenceLevels: [
      ...new Set(
        index.sources
          .map((source) => source.evidenceLevel)
          .filter((value): value is string => Boolean(value)),
      ),
    ],
    jurisdictions: [
      ...new Set(
        index.safetyRules
          .map((rule) => rule.jurisdiction)
          .filter((value): value is string => Boolean(value)),
      ),
    ],
    sortOptions: [
      { value: "severity_desc", label: "위험도 높은 순" },
      { value: "confidence_desc", label: "근거 신뢰도 높은 순" },
      { value: "nutrient_name", label: "성분명 가나다순" },
      { value: "recently_reviewed", label: "최근 검토 순" },
    ],
  };
}

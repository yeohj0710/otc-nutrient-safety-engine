import {
  engineQuerySchema,
  engineResponseSchema,
  ruleMatchSchema,
  type CandidateItem,
  type ConditionResult,
  type EngineQuery,
  type EngineResponse,
  type IngredientRecord,
  type KnowledgeIndex,
  type RuleCondition,
  type RuleMatch,
  type SafetyRule,
} from "@/src/types/knowledge";
import {
  getConditionAliases,
  getConditionPresetCanonicalValues,
} from "@/src/lib/knowledge/condition-aliases";
import { getMedicationAliases } from "@/src/lib/knowledge/medication-aliases";

const severityRank = {
  contraindicated: 4,
  avoid: 3,
  warn: 2,
  monitor: 1,
} as const;

const confidenceRank = {
  high: 4,
  medium: 3,
  low: 2,
  unknown: 1,
} as const;

function normalizeText(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function normalizeLookupKey(value: string) {
  return normalizeText(value)
    .replace(/[_\-\/()]+/g, " ")
    .replace(/[^a-z0-9가-힣\s]+/g, "")
    .replace(/\s+/g, "");
}

function normalizeTextArray(values?: string[]) {
  return values ? [...new Set(values.map(normalizeText).filter(Boolean))] : [];
}

function tokenizeMemo(text?: string | null) {
  return text
    ? text
        .split(/[\n,;|]/)
        .map((value) => normalizeText(value))
        .filter(Boolean)
    : [];
}

function groupBy<T>(items: T[], getKey: (item: T) => string) {
  const map = new Map<string, T[]>();

  for (const item of items) {
    const key = getKey(item);
    const bucket = map.get(key);
    if (bucket) bucket.push(item);
    else map.set(key, [item]);
  }

  return map;
}

function convertUnit(value: number, fromUnit: string | null | undefined, toUnit: string | null | undefined, ingredientId: string) {
  if (!fromUnit || !toUnit) return null;

  const normalizedFrom = normalizeText(fromUnit);
  const normalizedTo = normalizeText(toUnit);
  if (normalizedFrom === normalizedTo) return value;

  const massConversions: Record<string, number> = {
    "mg/day": 1000,
    "mcg/day": 1,
    "mcg rae/day": 1,
  };

  if (normalizedFrom in massConversions && normalizedTo in massConversions) {
    return (value * massConversions[normalizedFrom]) / massConversions[normalizedTo];
  }

  if (ingredientId === "vitamin_d" && normalizedFrom === "iu/day" && normalizedTo === "mcg/day") {
    return value / 40;
  }

  if (ingredientId === "vitamin_d" && normalizedFrom === "mcg/day" && normalizedTo === "iu/day") {
    return value * 40;
  }

  return null;
}

function getConditionLabel(field: string) {
  const labels: Record<string, string> = {
    age_years: "연령",
    candidate_daily_intake: "일일 섭취량",
    candidate_products_any: "제품 유형",
    coingredients_any: "동시 성분",
    devices_any: "의료기기",
    diseases_any: "질환",
    exposure_any: "노출 이력",
    immune_status_any: "면역 상태",
    ingredient_forms_any: "제형",
    jurisdiction_preference_any: "관할권",
    long_term_use_days: "장기 복용 기간",
    medications_any: "복용 약물",
    or_medications_any: "복용 약물",
    or_lactating: "수유 상태",
    or_pregnant_or_lactating: "임신/수유 상태",
    or_use_general: "일반 사용",
    population_any: "대상 집단",
    pregnancy_status_any: "임신 상태",
    same_day: "동일 날짜 복용",
    smoking_status_any: "흡연 상태",
  };

  return labels[field] ?? field;
}

type NormalizedProfile = {
  age?: number;
  sex?: string;
  pregnancyStatus?: string;
  lactationStatus?: string;
  smokerStatus?: string;
  medications: string[];
  conditions: string[];
  allergies: string[];
  selectedCompounds: string[];
  jurisdiction: string;
  memoTokens: string[];
  exposures: string[];
  devices: string[];
  immuneStatus?: string;
  populationTags: string[];
  strictestMode: boolean;
  candidateItems: Array<{
    ingredientId: string | null | undefined;
    name: string;
    form: string | null;
    product: string | null;
    dailyIntakeValue: number | null;
    dailyIntakeUnit: string | null;
    longTermUseDays: number | null;
    sameDay: boolean | null;
    coingredients: string[];
  }>;
  selectedIngredientIds: string[];
  providedFields: Set<string>;
};

function buildIngredientAliasMap(knowledgeIndex: KnowledgeIndex) {
  const aliasMap = new Map<string, IngredientRecord>();

  for (const ingredient of knowledgeIndex.ingredients) {
    aliasMap.set(normalizeText(ingredient.id), ingredient);
    aliasMap.set(normalizeLookupKey(ingredient.id), ingredient);
    aliasMap.set(normalizeText(ingredient.nameKo), ingredient);
    aliasMap.set(normalizeLookupKey(ingredient.nameKo), ingredient);
    if (ingredient.nameEn) aliasMap.set(normalizeText(ingredient.nameEn), ingredient);
    if (ingredient.nameEn) aliasMap.set(normalizeLookupKey(ingredient.nameEn), ingredient);
    for (const alias of ingredient.aliases) {
      aliasMap.set(normalizeText(alias), ingredient);
      aliasMap.set(normalizeLookupKey(alias), ingredient);
    }
  }

  return aliasMap;
}

function buildMedicationAliasMap(knowledgeIndex: KnowledgeIndex) {
  const aliasMap = new Map<string, string>();
  const medicationValues = new Set(
    knowledgeIndex.safetyRules.flatMap((rule) => [
      ...rule.interactionDrugs,
      ...rule.conditions
        .filter((condition) => ["medications_any", "or_medications_any"].includes(condition.field))
        .flatMap((condition) =>
          Array.isArray(condition.value) ? condition.value.map((item) => String(item)) : [],
        ),
    ]),
  );

  for (const value of medicationValues) {
    const canonical = normalizeText(value);
    const aliases = [value, ...getMedicationAliases(value)];

    for (const alias of aliases) {
      aliasMap.set(normalizeText(alias), canonical);
      aliasMap.set(normalizeLookupKey(alias), canonical);
    }
  }

  return aliasMap;
}

function buildConditionAliasMap(knowledgeIndex: KnowledgeIndex) {
  const aliasMap = new Map<string, string>();
  const conditionValues = new Set(
    [
      ...knowledgeIndex.safetyRules.flatMap((rule) => [
        ...rule.interactionDiseases,
        ...rule.conditions
          .filter((condition) => condition.field === "diseases_any")
          .flatMap((condition) =>
            Array.isArray(condition.value) ? condition.value.map((item) => String(item)) : [],
          ),
      ]),
      ...getConditionPresetCanonicalValues(),
    ],
  );

  for (const value of conditionValues) {
    const canonical = normalizeText(value);
    const aliases = [value, ...getConditionAliases(value)];

    for (const alias of aliases) {
      aliasMap.set(normalizeText(alias), canonical);
      aliasMap.set(normalizeLookupKey(alias), canonical);
    }
  }

  return aliasMap;
}

function normalizeProfileEntries(values: string[] | undefined, aliasMap?: Map<string, string>) {
  const normalizedValues = (values ?? []).map((value) => {
    const canonical =
      aliasMap?.get(normalizeText(value)) ??
      aliasMap?.get(normalizeLookupKey(value));

    return canonical ?? normalizeText(value);
  });

  return [...new Set(normalizedValues.filter(Boolean))];
}

function normalizeCandidateItems(candidateItems: CandidateItem[] | undefined, selectedCompounds: string[], aliasMap: Map<string, IngredientRecord>) {
  const normalizedCandidates = (candidateItems ?? []).map((candidate) => {
    const ingredient =
      (candidate.ingredientId ? aliasMap.get(normalizeText(candidate.ingredientId)) : null) ??
      (candidate.ingredientId ? aliasMap.get(normalizeLookupKey(candidate.ingredientId)) : null) ??
      aliasMap.get(normalizeText(candidate.name)) ??
      aliasMap.get(normalizeLookupKey(candidate.name));

    return {
      ingredientId: ingredient?.id ?? candidate.ingredientId ?? null,
      name: candidate.name,
      form: candidate.form ? normalizeText(candidate.form) : null,
      product: candidate.product ? normalizeText(candidate.product) : null,
      dailyIntakeValue: typeof candidate.dailyIntakeValue === "number" ? candidate.dailyIntakeValue : null,
      dailyIntakeUnit: candidate.dailyIntakeUnit ? normalizeText(candidate.dailyIntakeUnit) : null,
      longTermUseDays: typeof candidate.longTermUseDays === "number" ? candidate.longTermUseDays : null,
      sameDay: typeof candidate.sameDay === "boolean" ? candidate.sameDay : null,
      coingredients: normalizeTextArray(candidate.coingredients),
    };
  });

  for (const compound of selectedCompounds) {
    const ingredient = aliasMap.get(compound);
    if (!ingredient) continue;
    if (!normalizedCandidates.some((candidate) => candidate.ingredientId === ingredient.id)) {
      normalizedCandidates.push({
        ingredientId: ingredient.id,
        name: ingredient.nameKo,
        form: null,
        product: null,
        dailyIntakeValue: null,
        dailyIntakeUnit: null,
        longTermUseDays: null,
        sameDay: null,
        coingredients: [],
      });
    }
  }

  return normalizedCandidates;
}

function normalizeQuery(query: EngineQuery, knowledgeIndex: KnowledgeIndex) {
  const parsed = engineQuerySchema.parse(query);
  const aliasMap = buildIngredientAliasMap(knowledgeIndex);
  const medicationAliasMap = buildMedicationAliasMap(knowledgeIndex);
  const conditionAliasMap = buildConditionAliasMap(knowledgeIndex);
  const memoTokens = tokenizeMemo(parsed.profile.memo);
  const selectedCompounds = normalizeTextArray([...(parsed.profile.selectedCompounds ?? []), ...memoTokens]);
  const candidateItems = normalizeCandidateItems(parsed.candidateItems, selectedCompounds, aliasMap);
  const selectedIngredientIds = [...new Set(candidateItems.map((candidate) => candidate.ingredientId).filter(Boolean))] as string[];
  const providedFields = new Set<string>();

  if (typeof parsed.profile.age === "number") providedFields.add("age");
  if (parsed.profile.sex) providedFields.add("sex");
  if (parsed.profile.pregnancyStatus) providedFields.add("pregnancyStatus");
  if (parsed.profile.lactationStatus) providedFields.add("lactationStatus");
  if (parsed.profile.smokerStatus) providedFields.add("smokerStatus");
  if ((parsed.profile.medications ?? []).length > 0) providedFields.add("medications");
  if ((parsed.profile.conditions ?? []).length > 0) providedFields.add("conditions");
  if ((parsed.profile.allergies ?? []).length > 0) providedFields.add("allergies");
  if ((parsed.profile.exposures ?? []).length > 0) providedFields.add("exposures");
  if ((parsed.profile.devices ?? []).length > 0) providedFields.add("devices");
  if (parsed.profile.immuneStatus) providedFields.add("immuneStatus");
  if ((parsed.profile.populationTags ?? []).length > 0) providedFields.add("populationTags");
  if (selectedIngredientIds.length > 0) providedFields.add("selectedCompounds");
  if (candidateItems.some((candidate) => typeof candidate.dailyIntakeValue === "number")) providedFields.add("dailyIntake");
  if (candidateItems.some((candidate) => candidate.form)) providedFields.add("form");
  if (candidateItems.some((candidate) => candidate.product)) providedFields.add("product");
  if (candidateItems.some((candidate) => typeof candidate.longTermUseDays === "number")) providedFields.add("longTermUseDays");
  if (candidateItems.some((candidate) => typeof candidate.sameDay === "boolean")) providedFields.add("sameDay");

  return {
    age: parsed.profile.age ?? undefined,
    sex: parsed.profile.sex ? normalizeText(parsed.profile.sex) : undefined,
    pregnancyStatus: parsed.profile.pregnancyStatus ? normalizeText(parsed.profile.pregnancyStatus) : undefined,
    lactationStatus: parsed.profile.lactationStatus ? normalizeText(parsed.profile.lactationStatus) : undefined,
    smokerStatus: parsed.profile.smokerStatus ? normalizeText(parsed.profile.smokerStatus) : undefined,
    medications: normalizeProfileEntries([...(parsed.profile.medications ?? []), ...memoTokens], medicationAliasMap),
    conditions: normalizeProfileEntries([...(parsed.profile.conditions ?? []), ...memoTokens], conditionAliasMap),
    allergies: normalizeTextArray([...(parsed.profile.allergies ?? []), ...memoTokens]),
    selectedCompounds,
    jurisdiction: parsed.profile.jurisdiction ? normalizeText(parsed.profile.jurisdiction) : "kr",
    memoTokens,
    exposures: normalizeTextArray([...(parsed.profile.exposures ?? []), ...memoTokens]),
    devices: normalizeTextArray([...(parsed.profile.devices ?? []), ...memoTokens]),
    immuneStatus: parsed.profile.immuneStatus ? normalizeText(parsed.profile.immuneStatus) : undefined,
    populationTags: normalizeTextArray(parsed.profile.populationTags),
    strictestMode: parsed.profile.strictestMode ?? false,
    candidateItems,
    selectedIngredientIds,
    providedFields,
  } satisfies NormalizedProfile;
}

function findCandidateForRule(profile: NormalizedProfile, rule: SafetyRule) {
  return profile.candidateItems.filter((candidate) => candidate.ingredientId === rule.ingredientId);
}

function findLooseMatch(profileValues: string[], candidateValues: unknown[]) {
  const profileKeys = new Set(profileValues.map((value) => normalizeLookupKey(value)));

  return candidateValues
    .map((value) => normalizeText(String(value)))
    .find((value) => profileKeys.has(normalizeLookupKey(value))) ?? null;
}

function ingredientFormsCoverRule(ingredient: IngredientRecord | null, conditionValues: string[]) {
  if (!ingredient) return false;
  const ingredientForms = new Set(ingredient.forms.map((value) => normalizeText(value)));
  const normalizedConditionValues = [...new Set(conditionValues.map((value) => normalizeText(value)))];
  return normalizedConditionValues.length === ingredientForms.size
    && normalizedConditionValues.every((value) => ingredientForms.has(value));
}

function missingCondition(condition: RuleCondition, reason: string): ConditionResult {
  return {
    conditionId: condition.id,
    field: condition.field,
    requirementGroup: condition.requirementGroup,
    status: "missing",
    reason,
  };
}

function evaluateCondition(
  condition: RuleCondition,
  rule: SafetyRule,
  ingredient: IngredientRecord | null,
  profile: NormalizedProfile,
): ConditionResult {
  const candidates = findCandidateForRule(profile, rule);
  const valueLabel = getConditionLabel(condition.field);

  switch (condition.field) {
    case "age_years": {
      if (typeof profile.age !== "number") return missingCondition(condition, `${valueLabel} 정보가 없어 판정 보류`);

      const value = condition.value as { min?: number; max?: number };
      const min = typeof value.min === "number" ? value.min : Number.NEGATIVE_INFINITY;
      const max = typeof value.max === "number" ? value.max : Number.POSITIVE_INFINITY;
      const matched = profile.age >= min && profile.age <= max;

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched
          ? `${valueLabel} ${profile.age}세가 규칙 범위에 포함됨`
          : `${valueLabel} ${profile.age}세가 규칙 범위를 벗어남`,
      };
    }
    case "pregnancy_status_any": {
      if (!profile.pregnancyStatus) return missingCondition(condition, `${valueLabel} 정보가 없어 판정 보류`);

      const allowed = (condition.value as unknown[]).map((item) => normalizeText(String(item)));
      const matched = allowed.includes(profile.pregnancyStatus);

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched
          ? `임신 상태가 ${allowed.join(", ")} 조건과 일치`
          : `임신 상태가 ${allowed.join(", ")} 조건과 일치하지 않음`,
      };
    }
    case "or_lactating": {
      if (!profile.lactationStatus) return missingCondition(condition, `${valueLabel} 정보가 없어 판정 보류`);

      const matched = ["lactating", "yes", "true"].includes(profile.lactationStatus);
      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "수유 상태가 확인됨" : "수유 상태가 확인되지 않음",
      };
    }
    case "or_pregnant_or_lactating": {
      if (!profile.pregnancyStatus && !profile.lactationStatus) {
        return missingCondition(condition, "임신 또는 수유 정보가 없어 판정 보류");
      }

      const matched =
        ["pregnant", "trying_to_conceive", "unknown_possible"].includes(profile.pregnancyStatus ?? "") ||
        ["lactating", "yes", "true"].includes(profile.lactationStatus ?? "");

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "임신/수유 조건이 충족됨" : "임신/수유 조건이 충족되지 않음",
      };
    }
    case "smoking_status_any": {
      if (!profile.smokerStatus) return missingCondition(condition, `${valueLabel} 정보가 없어 판정 보류`);

      const allowed = (condition.value as unknown[]).map((item) => normalizeText(String(item)));
      const matched = allowed.includes(profile.smokerStatus);

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "흡연 상태가 규칙 조건과 일치" : "흡연 상태가 규칙 조건과 일치하지 않음",
      };
    }
    case "medications_any":
    case "or_medications_any": {
      if (profile.medications.length === 0) return missingCondition(condition, `${valueLabel} 정보가 없어 판정 보류`);

      const required = condition.value as unknown[];
      const matchedMedication = findLooseMatch(profile.medications, required);

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matchedMedication ? "matched" : "not_matched",
        reason: matchedMedication
          ? `복용 약물 ${matchedMedication}가 규칙과 직접 연결됨`
          : "입력된 약물과 규칙 약물 조건이 일치하지 않음",
      };
    }
    case "diseases_any": {
      if (profile.conditions.length === 0) return missingCondition(condition, `${valueLabel} 정보가 없어 판정 보류`);

      const required = condition.value as unknown[];
      const matchedDisease = findLooseMatch(profile.conditions, required);

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matchedDisease ? "matched" : "not_matched",
        reason: matchedDisease
          ? `질환 ${matchedDisease}가 규칙과 직접 연결됨`
          : "입력된 질환과 규칙 질환 조건이 일치하지 않음",
      };
    }
    case "candidate_daily_intake": {
      if (candidates.length === 0) return missingCondition(condition, "선택된 성분의 일일 섭취량 정보가 없어 판정 보류");

      const intakeRule = condition.value as { gt?: number; gte?: number; unit?: string };
      if (!candidates.some((candidate) => typeof candidate.dailyIntakeValue === "number")) {
        return missingCondition(condition, "일일 섭취량이 입력되지 않아 판정 보류");
      }

      const matched = candidates.some((candidate) => {
        if (typeof candidate.dailyIntakeValue !== "number") return false;
        const converted = convertUnit(candidate.dailyIntakeValue, candidate.dailyIntakeUnit, intakeRule.unit, rule.ingredientId);
        if (typeof converted !== "number") return false;
        if (typeof intakeRule.gt === "number") return converted > intakeRule.gt;
        if (typeof intakeRule.gte === "number") return converted >= intakeRule.gte;
        return false;
      });

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "일일 섭취량 조건이 충족됨" : "일일 섭취량이 규칙 기준에 도달하지 않음",
      };
    }
    case "same_day": {
      if (candidates.length === 0 || !profile.providedFields.has("sameDay")) {
        return missingCondition(condition, "같은 날 복용 여부가 없어 판정 보류");
      }

      const matched = candidates.some((candidate) => candidate.sameDay === true);
      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "같은 날 복용으로 간주됨" : "같은 날 복용이 아님",
      };
    }
    case "long_term_use_days": {
      if (candidates.length === 0 || !profile.providedFields.has("longTermUseDays")) {
        return missingCondition(condition, "장기 복용 기간 정보가 없어 판정 보류");
      }

      const threshold = condition.value as { gte?: number };
      const matched = candidates.some(
        (candidate) => typeof candidate.longTermUseDays === "number" && typeof threshold.gte === "number" && candidate.longTermUseDays >= threshold.gte,
      );

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "장기 복용 기간 조건이 충족됨" : "장기 복용 기간이 기준 미만임",
      };
    }
    case "jurisdiction_preference_any": {
      const allowed = (condition.value as unknown[]).map((item) => normalizeText(String(item)));
      const matched = allowed.includes(profile.jurisdiction) || (profile.strictestMode && allowed.includes("strictest"));

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "관할권 선호가 규칙과 일치" : "관할권 선호가 규칙과 다름",
      };
    }
    case "ingredient_forms_any": {
      const requiredForms = (condition.value as unknown[]).map((item) => normalizeText(String(item)));

      if (candidates.length === 0) {
        const matchedByCatalog = ingredientFormsCoverRule(ingredient, requiredForms);
        return {
          conditionId: condition.id,
          field: condition.field,
          requirementGroup: condition.requirementGroup,
          status: matchedByCatalog ? "matched" : "missing",
          reason: matchedByCatalog ? "성분 카탈로그 상 제형이 규칙과 일치" : "선택한 제형 정보가 없어 판정 보류",
        };
      }

      if (!profile.providedFields.has("form") && !ingredientFormsCoverRule(ingredient, requiredForms)) {
        return missingCondition(condition, "제형 정보가 없어 판정 보류");
      }

      const matched = candidates.some((candidate) => candidate.form && requiredForms.includes(candidate.form));
      const fallbackCatalogMatch = ingredientFormsCoverRule(ingredient, requiredForms);

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched || fallbackCatalogMatch ? "matched" : "not_matched",
        reason: matched || fallbackCatalogMatch ? "제형 조건이 충족됨" : "제형이 규칙 조건과 일치하지 않음",
      };
    }
    case "candidate_products_any": {
      const requiredProducts = (condition.value as unknown[]).map((item) => normalizeText(String(item)));

      if (candidates.length === 0) return missingCondition(condition, "제품 유형 정보가 없어 판정 보류");

      if (!profile.providedFields.has("product")) {
        const ingredientMatches = requiredProducts.some((product) => normalizeText(rule.nutrientOrIngredient).includes(product));
        return {
          conditionId: condition.id,
          field: condition.field,
          requirementGroup: condition.requirementGroup,
          status: ingredientMatches ? "matched" : "missing",
          reason: ingredientMatches ? "성분명 기준으로 제품 유형이 일치" : "제품 유형 정보가 없어 판정 보류",
        };
      }

      const matched = candidates.some((candidate) => candidate.product && requiredProducts.includes(candidate.product));
      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "제품 유형 조건이 충족됨" : "제품 유형이 규칙 조건과 다름",
      };
    }
    case "coingredients_any": {
      if (candidates.length === 0 || !candidates.some((candidate) => candidate.coingredients.length > 0)) {
        return missingCondition(condition, "동시 성분 정보가 없어 판정 보류");
      }

      const required = (condition.value as unknown[]).map((item) => normalizeText(String(item)));
      const matched = candidates.some((candidate) => candidate.coingredients.some((coingredient) => required.includes(coingredient)));

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "동시 성분 조건이 충족됨" : "동시 성분 조건이 충족되지 않음",
      };
    }
    case "population_any": {
      if (profile.populationTags.length === 0) return missingCondition(condition, "대상 집단 정보가 없어 판정 보류");

      const matched = Boolean(findLooseMatch(profile.populationTags, condition.value as unknown[]));

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "대상 집단 조건이 충족됨" : "대상 집단 조건이 충족되지 않음",
      };
    }
    case "exposure_any": {
      if (profile.exposures.length === 0) return missingCondition(condition, "노출 이력 정보가 없어 판정 보류");

      const matched = Boolean(findLooseMatch(profile.exposures, condition.value as unknown[]));

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "노출 이력 조건이 충족됨" : "노출 이력 조건이 충족되지 않음",
      };
    }
    case "immune_status_any": {
      if (!profile.immuneStatus) return missingCondition(condition, "면역 상태 정보가 없어 판정 보류");

      const matched = Boolean(findLooseMatch([profile.immuneStatus], condition.value as unknown[]));

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "면역 상태 조건이 충족됨" : "면역 상태 조건이 충족되지 않음",
      };
    }
    case "devices_any": {
      if (profile.devices.length === 0) return missingCondition(condition, "의료기기 정보가 없어 판정 보류");

      const matched = Boolean(findLooseMatch(profile.devices, condition.value as unknown[]));

      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: matched ? "matched" : "not_matched",
        reason: matched ? "의료기기 조건이 충족됨" : "의료기기 조건이 충족되지 않음",
      };
    }
    case "or_use_general":
      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: "matched",
        reason: "일반 사용자에게도 적용되는 일반 경고 규칙",
      };
    default:
      return {
        conditionId: condition.id,
        field: condition.field,
        requirementGroup: condition.requirementGroup,
        status: "not_applicable",
        reason: `${condition.field} 조건은 아직 일반화되지 않아 수동 검토 필요`,
      };
  }
}

function evaluateRule(rule: SafetyRule, ingredient: IngredientRecord | null, profile: NormalizedProfile, knowledgeIndex: KnowledgeIndex): RuleMatch {
  const selectedIngredient = profile.selectedIngredientIds.length === 0 || profile.selectedIngredientIds.includes(rule.ingredientId);
  const conditionResults = rule.conditions.map((condition) => evaluateCondition(condition, rule, ingredient, profile));
  const groupedResults = groupBy(conditionResults, (result) => result.requirementGroup);
  const matchedConditions = conditionResults.filter((result) => result.status === "matched");
  const matchedOnlyByGeneralUse =
    matchedConditions.length > 0 &&
    matchedConditions.every((result) => result.field === "or_use_general");

  const matchedBecause: string[] = [];
  const missingReasons: string[] = [];
  const excludedReasons: string[] = [];

  let hasMissing = false;
  let hasNotMatched = false;
  let matchedGroups = 0;

  for (const results of groupedResults.values()) {
    if (results.some((result) => result.status === "matched")) {
      matchedGroups += 1;
      matchedBecause.push(results.find((result) => result.status === "matched")?.reason ?? "조건 충족");
      continue;
    }

    if (results.some((result) => result.status === "missing")) {
      hasMissing = true;
      missingReasons.push(...results.filter((result) => result.status === "missing").map((result) => result.reason));
      continue;
    }

    if (results.some((result) => result.status === "not_matched")) {
      hasNotMatched = true;
      excludedReasons.push(...results.filter((result) => result.status === "not_matched").map((result) => result.reason));
    }
  }

  if (!selectedIngredient) {
    excludedReasons.push("선택한 성분 목록과 직접 연결되지 않음");
  }

  const candidates = findCandidateForRule(profile, rule);
  const hasThreshold = typeof rule.threshold === "number" && Boolean(rule.thresholdOperator) && Boolean(rule.unit);

  if (hasThreshold && selectedIngredient) {
    if (candidates.length === 0 || !candidates.some((candidate) => typeof candidate.dailyIntakeValue === "number")) {
      hasMissing = true;
      missingReasons.push("용량 기준 규칙이지만 일일 섭취량 정보가 없어 판정 보류");
    } else {
      const thresholdMatched = candidates.some((candidate) => {
        if (typeof candidate.dailyIntakeValue !== "number") return false;
        const converted = convertUnit(candidate.dailyIntakeValue, candidate.dailyIntakeUnit, rule.unit, rule.ingredientId);
        if (typeof converted !== "number") return false;
        if (rule.thresholdOperator === ">") return converted > (rule.threshold ?? 0);
        if (rule.thresholdOperator === ">=") return converted >= (rule.threshold ?? 0);
        if (rule.thresholdOperator === "<") return converted < (rule.threshold ?? 0);
        if (rule.thresholdOperator === "<=") return converted <= (rule.threshold ?? 0);
        return false;
      });

      if (thresholdMatched) {
        matchedBecause.push(`입력된 용량이 ${rule.thresholdOperator} ${rule.threshold} ${rule.unit} 기준을 충족함`);
      } else {
        hasNotMatched = true;
        excludedReasons.push(`입력된 용량이 ${rule.thresholdOperator} ${rule.threshold} ${rule.unit} 기준에 도달하지 않음`);
      }
    }
  }

  const classification = !selectedIngredient || hasNotMatched
    ? "excluded"
    : rule.conditions.length === 0 && !hasThreshold
      ? "possibly_relevant"
      : matchedOnlyByGeneralUse
        ? "excluded"
      : hasMissing
        ? "needs_more_info"
        : "definitely_matched";

  const supportingSources = rule.sourceIds
    .map((sourceId) => knowledgeIndex.sources.find((source) => source.id === sourceId))
    .filter((source): source is KnowledgeIndex["sources"][number] => Boolean(source));
  const supportingEvidenceChunks = rule.evidenceChunkIds
    .map((chunkId) => knowledgeIndex.evidenceChunks.find((chunk) => chunk.id === chunkId))
    .filter((chunk): chunk is KnowledgeIndex["evidenceChunks"][number] => Boolean(chunk));

  const totalGroups = Math.max(groupedResults.size, 1);
  const matchScoreBase = matchedGroups / totalGroups;
  const matchScore =
    classification === "definitely_matched"
      ? 1
      : classification === "possibly_relevant"
        ? 0.6 + matchScoreBase * 0.2
        : classification === "needs_more_info"
          ? 0.35 + matchScoreBase * 0.25
          : 0;

  return ruleMatchSchema.parse({
    ruleId: rule.id,
    classification,
    matched: classification === "definitely_matched",
    matchScore,
    matchedBecause,
    notEvaluatedBecauseMissing: missingReasons,
    needsMoreInfo: missingReasons,
    resolvedSeverity: rule.severity,
    resolvedMessage: rule.messageShort,
    supportingSources,
    supportingEvidenceChunks,
    rule,
    ingredient,
    evaluation: {
      selectedIngredient,
      conditionResults,
      missingFields: missingReasons.map((reason) => reason.split(" ")[0]),
      excludedReasons,
    },
  });
}

function sortRuleMatches(ruleMatches: RuleMatch[], sort: EngineQuery["sort"]) {
  const sorted = [...ruleMatches];

  sorted.sort((left, right) => {
    if (sort === "confidence_desc") {
      return confidenceRank[right.rule.confidence] - confidenceRank[left.rule.confidence];
    }

    if (sort === "nutrient_name") {
      return left.rule.nutrientOrIngredient.localeCompare(right.rule.nutrientOrIngredient, "ko");
    }

    if (sort === "recently_reviewed") {
      return new Date(right.rule.lastReviewedAt ?? 0).getTime() - new Date(left.rule.lastReviewedAt ?? 0).getTime();
    }

    return severityRank[right.resolvedSeverity] - severityRank[left.resolvedSeverity] || right.rule.priority - left.rule.priority;
  });

  return sorted;
}

export function runSafetyEngine(query: EngineQuery, knowledgeIndex: KnowledgeIndex): EngineResponse {
  const normalizedQuery = normalizeQuery(query, knowledgeIndex);
  const ruleMatches = knowledgeIndex.safetyRules.map((rule) =>
    evaluateRule(rule, knowledgeIndex.ingredients.find((ingredient) => ingredient.id === rule.ingredientId) ?? null, normalizedQuery, knowledgeIndex),
  );

  const grouped = {
    definitely_matched: sortRuleMatches(ruleMatches.filter((match) => match.classification === "definitely_matched"), query.sort),
    possibly_relevant: sortRuleMatches(ruleMatches.filter((match) => match.classification === "possibly_relevant"), query.sort),
    needs_more_info: sortRuleMatches(ruleMatches.filter((match) => match.classification === "needs_more_info"), query.sort),
    excluded: sortRuleMatches(ruleMatches.filter((match) => match.classification === "excluded"), query.sort),
  };

  return engineResponseSchema.parse({
    generatedAt: new Date().toISOString(),
    query: engineQuerySchema.parse(query),
    knowledgeMeta: knowledgeIndex.meta,
    totalCounts: {
      definitely_matched: grouped.definitely_matched.length,
      possibly_relevant: grouped.possibly_relevant.length,
      needs_more_info: grouped.needs_more_info.length,
      excluded: grouped.excluded.length,
    },
    ...grouped,
  });
}

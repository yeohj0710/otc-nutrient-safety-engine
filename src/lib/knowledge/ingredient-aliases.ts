type IngredientAliasInput = {
  id: string;
  nameKo: string;
  nameEn?: string | null;
  forms?: string[] | null;
  matchingAliasesKo?: string[] | null;
  matchingAliasesEn?: string[] | null;
};

const koreanVitaminLetterMap: Record<string, string> = {
  a: "에이",
  b: "비",
  c: "씨",
  d: "디",
  e: "이",
  k: "케이",
};

function normalizeAliasSpacing(value: string) {
  return value
    .trim()
    .replace(/[_\-\/()]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function addAlias(set: Set<string>, value?: string | null) {
  const normalized = normalizeAliasSpacing(value ?? "");
  if (normalized) {
    set.add(normalized);
  }
}

function buildEnglishAliasVariants(value: string) {
  const normalized = normalizeAliasSpacing(value).toLowerCase();
  if (!normalized) return [];

  const variants = new Set<string>([normalized, normalized.replace(/\s+/g, "")]);
  const vitaminMatch = normalized.match(/^vitamin\s+([a-z]\d*)$/i);

  if (vitaminMatch) {
    const suffix = vitaminMatch[1].toLowerCase();
    variants.add(`vit ${suffix}`);
    variants.add(`vit${suffix}`);
  }

  if (normalized.includes("omega")) {
    variants.add(normalized.replace(/omega\s+/g, "omega-"));
    variants.add(normalized.replace(/omega[-\s]+/g, "omega "));
    variants.add(normalized.replace(/omega[-\s]+/g, "omega"));
  }

  if (normalized.endsWith(" supplement")) {
    variants.add(normalized.replace(/\s+supplement$/, ""));
  }

  return [...variants];
}

function buildKoreanAliasVariants(value: string) {
  const normalized = normalizeAliasSpacing(value);
  if (!normalized) return [];

  const variants = new Set<string>([normalized, normalized.replace(/\s+/g, "")]);
  const vitaminMatch = normalized.match(/^비타민\s*([A-Za-z])$/);

  if (vitaminMatch) {
    const letter = vitaminMatch[1].toLowerCase();
    const spoken = koreanVitaminLetterMap[letter];
    if (spoken) {
      variants.add(`비타민 ${letter.toUpperCase()}`);
      variants.add(`비타민${letter.toUpperCase()}`);
      variants.add(`비타민 ${spoken}`);
      variants.add(`비타민${spoken}`);
    }
  }

  if (normalized.includes("오메가")) {
    variants.add(normalized.replace(/오메가\s+/g, "오메가-"));
    variants.add(normalized.replace(/오메가[-\s]+/g, "오메가"));
  }

  return [...variants];
}

export function buildIngredientAliases(input: IngredientAliasInput) {
  const aliasSet = new Set<string>();
  const rawValues = [
    input.id,
    input.nameKo,
    input.nameEn ?? "",
    ...(input.forms ?? []),
    ...(input.matchingAliasesKo ?? []),
    ...(input.matchingAliasesEn ?? []),
  ];

  for (const rawValue of rawValues) {
    addAlias(aliasSet, rawValue);
  }

  for (const rawValue of rawValues) {
    const normalized = normalizeAliasSpacing(rawValue ?? "");
    if (!normalized) continue;

    for (const variant of buildEnglishAliasVariants(normalized)) {
      addAlias(aliasSet, variant);
    }

    for (const variant of buildKoreanAliasVariants(normalized)) {
      addAlias(aliasSet, variant);
    }
  }

  return [...aliasSet];
}

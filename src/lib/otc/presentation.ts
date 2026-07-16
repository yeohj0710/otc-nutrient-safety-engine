import type {
  EvaluationCoverageGap,
  OtcProduct,
  RuleEvidenceLink,
  SafetyFinding,
  SelectedProduct,
  UserProfile,
} from "./schema";

export type LiteratureEvidenceRelation =
  | "supports_caution"
  | "contextualizes_uncertainty"
  | "supports_mechanism";

export type LiteratureProfileCondition = Exclude<
  keyof UserProfile,
  "ageYears" | "medications" | "redFlagSymptoms"
>;

export type SupportingLiterature = {
  pmid: string;
  doi: string;
  title: string;
  publicationYear: number;
  studyDesign: string;
  evidenceRelation: LiteratureEvidenceRelation;
  ruleTypes: string[];
  ingredientIds: string[];
  profileConditions: LiteratureProfileCondition[];
  keyFindingKo: string;
  selectionReasonKo: string;
  limitationKo: string;
  reviewStatus: "codex_curated_supporting_not_rule_release_evidence";
  supportsRuleRelease: false;
  url: string;
};

export type GroupedCoverageGap = {
  groupId: string;
  ruleType: string;
  titleKo: string;
  productNames: string[];
  profileDetailMessages: string[];
  count: number;
};

export type FindingContext = {
  productNames: string[];
  ingredientFacts: string[];
};

export type RuleEvidenceDisplay = {
  evidence?: RuleEvidenceLink;
  productMatch: "all" | "partial" | "none";
};

const formatAmount = (value: number) =>
  Number.isInteger(value) ? String(value) : value.toFixed(1);

export function formatEvidenceSource(sourceId: string): string {
  if (sourceId === "MFDS-NEDRUG-DETAIL") {
    return "식약처 의약품안전나라 허가사항";
  }
  return sourceId;
}

export function literatureRelationLabel(
  relation: LiteratureEvidenceRelation,
): string {
  if (relation === "supports_caution") return "주의를 뒷받침하는 연구";
  if (relation === "contextualizes_uncertainty") return "불확실성을 설명하는 연구";
  return "작용 원리를 설명하는 연구";
}

export function buildFindingContext(
  finding: SafetyFinding,
  selected: SelectedProduct[],
): FindingContext {
  const productIds = new Set(finding.productIds);
  const ingredientIds = new Set(finding.ingredientIds);
  const relevantProducts = selected.filter(({ product }) => productIds.has(product.productId));
  const ingredientFacts = relevantProducts.flatMap(({ product }) =>
    product.ingredients
      .filter((ingredient) => ingredientIds.has(ingredient.ingredientId))
      .map(
        (ingredient) =>
          `${ingredient.nameKo} ${formatAmount(ingredient.amountPerUnit)} ${ingredient.unit}/${product.doseUnitLabel}`,
      ),
  );

  return {
    productNames: [...new Set(relevantProducts.map(({ product }) => product.productName))],
    ingredientFacts: [...new Set(ingredientFacts)],
  };
}

export function ruleEvidenceForFinding(
  finding: SafetyFinding,
  selected: SelectedProduct[],
  ruleEvidence: RuleEvidenceLink[],
): RuleEvidenceDisplay {
  const findingProductIds = new Set(finding.productIds);
  const findingItemSequences = new Set(
    selected
      .filter(({ product }) => findingProductIds.has(product.productId))
      .map(({ product }) => product.itemSequence),
  );
  const directEvidence = ruleEvidence.find((evidence) =>
    findingItemSequences.has(evidence.itemSequence),
  );
  const matchedItemSequences = new Set(
    ruleEvidence
      .filter((evidence) => findingItemSequences.has(evidence.itemSequence))
      .map((evidence) => evidence.itemSequence),
  );
  const productMatch = matchedItemSequences.size === 0
    ? "none"
    : matchedItemSequences.size === findingItemSequences.size
      ? "all"
      : "partial";
  return {
    evidence: directEvidence ?? ruleEvidence[0],
    productMatch,
  };
}

export function groupCoverageGaps(
  gaps: EvaluationCoverageGap[],
  productNamesById: Map<string, string>,
): GroupedCoverageGap[] {
  const groups = new Map<string, GroupedCoverageGap>();
  for (const gap of gaps) {
    const groupId = `${gap.ruleType}:${gap.titleKo}`;
    const current = groups.get(groupId) ?? {
      groupId,
      ruleType: gap.ruleType,
      titleKo: gap.titleKo,
      productNames: [],
      profileDetailMessages: [],
      count: 0,
    };
    for (const productId of gap.productIds) {
      const name = productNamesById.get(productId) ?? productId;
      if (!current.productNames.includes(name)) current.productNames.push(name);
    }
    if (
      gap.gapId.startsWith("coverage:profile:") &&
      !current.profileDetailMessages.includes(gap.detailKo)
    ) {
      current.profileDetailMessages.push(gap.detailKo);
    }
    current.count += 1;
    groups.set(groupId, current);
  }
  return [...groups.values()];
}

export function supportingLiteratureForFinding(
  finding: SafetyFinding,
  literature: SupportingLiterature[],
  profile?: UserProfile,
): SupportingLiterature[] {
  const findingIngredients = new Set(finding.ingredientIds);
  return literature.filter((paper) => {
    if (!paper.ruleTypes.includes(finding.ruleType)) return false;
    if (
      paper.profileConditions.length > 0 &&
      (!profile || !paper.profileConditions.some((condition) => Boolean(profile[condition])))
    ) {
      return false;
    }
    return (
      paper.ingredientIds.length === 0 ||
      paper.ingredientIds.some((ingredientId) => findingIngredients.has(ingredientId))
    );
  }).sort((left, right) => left.ruleTypes.length - right.ruleTypes.length);
}

export function productsForTherapeuticClass(
  products: OtcProduct[],
  therapeuticClass: string,
): OtcProduct[] {
  if (therapeuticClass === "전체") return products;
  return products.filter((product) => product.therapeuticClass === therapeuticClass);
}

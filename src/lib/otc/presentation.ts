import type {
  EvaluationCoverageGap,
  OtcProduct,
  ReleasedRulePolicy,
  RuleEvidenceLink,
  SafetyFinding,
  SelectedProduct,
  UserProfile,
} from "./schema";

export type LiteratureEvidenceRelation =
  | "supports_caution"
  | "contextualizes_uncertainty"
  | "supports_mechanism";

export type LiteratureProfileCondition = keyof UserProfile;

/** 복용 입력 축. 사용자 프로파일이 아니라 제품 입력이라 문헌 필터에 쓰지 않고 표시만 한다. */
export type LiteratureDoseInputCondition = "hoursSincePreviousDose" | "continuousDays";

/** 허가원문 판정과 문헌이 갈리는 지점. 어느 한쪽을 지우지 않고 그대로 보존한다. */
export type LiteratureAuthorizationAlignment = "consistent" | "conflict";

export type SupportingLiteratureRuleLink = {
  linkId: string;
  ruleId: string;
  ruleType: string;
  ruleReleased: boolean;
  evidenceRelation: LiteratureEvidenceRelation;
  /** 초록의 문장 단위 locator. 예: abstract:sentence:6 */
  locator: string;
  locatorQuoteEn: string;
  keyFindingKo: string;
  selectionReasonKo: string;
  limitationKo: string;
  authorizationAlignment: LiteratureAuthorizationAlignment;
  authorizationNoteKo: string;
  v51Classification: SupportingLiteratureV51Classification;
};

export type SupportingLiteratureUiPolicy =
  | "direct"
  | "background_only"
  | "direct_when_scope_matches_else_background"
  | "exclude_from_result_ui";

export type SupportingLiteratureDirectScope = {
  ingredientIds: string[];
  productItemSequences: string[];
  profileConditions: string[];
  medicationTerms: string[];
};

export type SupportingLiteratureV51Classification = {
  classificationId: string;
  lineageStatus:
    | "v50_emitted"
    | "v50_rejected_not_in_v5_corpus"
    | "v50_rejected_no_retain_decision_for_rule_question";
  semanticClassification:
    | "direct_match"
    | "background_context"
    | "mixed_scope"
    | null;
  uiPolicy: SupportingLiteratureUiPolicy;
  uiDirectLabelAllowed: boolean;
  directScope: SupportingLiteratureDirectScope;
  classificationReasonKo: string;
  uiBoundaryKo: string;
  humanExpertReviewed: boolean;
  supportsRuleRelease: false;
};

/**
 * 이 문헌이 v5.0 문헌 선별로 검증됐는지, 아니면 왜 검증되지 못했는지.
 * v5.0에서 채택한 10건은 정책에 따라 직접·조건부 직접·배경 문헌으로만 표시한다.
 * 기각한 10건은 감사용 데이터로 보존하지만 결과 화면에서는 항상 제외한다.
 * 사유는 v5.0 하류 매니페스트가 기록한 값 그대로이며 출판연도로 추정하지 않는다
 * (`AM-OTC-004`). 문헌은 설명용 근거일 뿐이므로 이 값이 규칙 판정을 바꾸지는 않는다.
 */
export type SupportingLiteratureV50Validation = {
  screened: boolean;
  reason:
    | null
    | "not_in_v5_corpus"
    | "no_retain_decision_for_rule_question"
    | "unknown";
  labelKo: string;
};

export type SupportingLiterature = {
  pmid: string;
  doi: string;
  v50Validation: SupportingLiteratureV50Validation;
  title: string;
  journal: string;
  publicationYear: number;
  studyDesign: string;
  evidenceRelation: LiteratureEvidenceRelation;
  /** 문헌은 설명용 근거일 뿐 판정 권한이 없다. */
  evidenceAuthority: "literature_explanatory_only";
  disclaimerKo: string;
  ruleTypes: string[];
  ruleLinks: SupportingLiteratureRuleLink[];
  ingredientIds: string[];
  profileConditions: LiteratureProfileCondition[];
  doseInputConditions: LiteratureDoseInputCondition[];
  keyFindingKo: string;
  selectionReasonKo: string;
  limitationKo: string;
  reviewStatus: "agent_curated_from_v40_retained_corpus";
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
  direct: RuleEvidenceLink[];
  representative: RuleEvidenceLink[];
  productMatch: "all" | "partial" | "none";
  matchedProductCount: number;
  findingProductCount: number;
};

export type DisplayFinding = SafetyFinding & {
  /** 묶기 전 엔진 판정을 그대로 보존한다. */
  members: SafetyFinding[];
};

export type FindingLiteratureMatch = {
  paper: SupportingLiterature;
  link: SupportingLiteratureRuleLink;
};

export type SplitSupportingLiterature = {
  direct: FindingLiteratureMatch[];
  background: FindingLiteratureMatch[];
};

export type LiteratureStatusSummary = {
  v5Linked: number;
  directCapable: number;
  backgroundOnly: number;
  excluded: number;
};

export type LiteratureHomepageStatusSummary = {
  v5Linked: number;
  v5RuleCount: number;
  directMatch: number;
  conditionalDirect: number;
  backgroundOnly: number;
  excluded: number;
};

export type ProductSupportSummary = {
  activeCheckTypes: string[];
  administrationConstraintCount: number;
  conditionLabels: string[];
  detailLabels: string[];
  releasedRuleBindingCount: number;
  summaryKo: string;
  supportedCheckTypeCount: number;
};

const doseAndIntervalRuleTypes = new Set([
  "max_daily_dose",
  "minimum_interval",
]);

const productSupportLabelByRuleType: Record<string, string> = {
  max_daily_dose: "1회·하루 사용량",
  minimum_interval: "사용·복용 간격",
  age_restriction: "연령",
  pregnancy_lactation: "임신·수유",
  hepatic_disease: "간질환",
  renal_disease: "신장질환",
  gi_bleeding_ulcer: "위장관 출혈·궤양",
  sedation_driving: "졸림·운전",
  alcohol: "정기 음주",
  anticoagulant_antiplatelet: "항응고·항혈소판제",
  sedative_medication: "진정·수면제 병용",
  decongestant_hypertension: "고혈압·심혈관질환",
  urgent_referral: "긴급 증상",
};

/** 제품별 지원 점검 유형과 released 규칙 연결을 서로 다른 수치로 설명한다. */
export function buildProductSupportSummary(
  product: OtcProduct,
  releasedRuleTypes?: ReadonlySet<string>,
): ProductSupportSummary {
  const activeCheckTypes = [
    ...new Set(
      (product.supportedRuleTypes ?? []).filter(
        (ruleType) => !releasedRuleTypes || releasedRuleTypes.has(ruleType),
      ),
    ),
  ];
  const conditionRuleTypes = activeCheckTypes.filter(
    (ruleType) => !doseAndIntervalRuleTypes.has(ruleType),
  );
  const doseAndIntervalLabels = [
    ...(activeCheckTypes.includes("max_daily_dose") ? ["용량"] : []),
    ...(activeCheckTypes.includes("minimum_interval") ? ["간격"] : []),
  ];
  const doseAndIntervalSummary = doseAndIntervalLabels.join("·");
  const labelsFor = (ruleTypes: string[]) => [
    ...new Set(
      ruleTypes.map(
        (ruleType) => productSupportLabelByRuleType[ruleType] ?? "기타 허가 조건",
      ),
    ),
  ];

  return {
    activeCheckTypes,
    administrationConstraintCount:
      product.administrationConstraints?.length ?? 0,
    conditionLabels: labelsFor(conditionRuleTypes),
    detailLabels: labelsFor(activeCheckTypes),
    releasedRuleBindingCount: product.supportedReleasedRuleIds?.length ?? 0,
    summaryKo:
      activeCheckTypes.length === 0
        ? "현재 지원하는 점검 유형 없음"
        : conditionRuleTypes.length === 0
          ? `${doseAndIntervalSummary || "제품별 조건"}만 확인 가능`
          : doseAndIntervalSummary
            ? `${doseAndIntervalSummary} 외 조건도 확인 가능`
            : "제품별 조건만 확인 가능",
    supportedCheckTypeCount: activeCheckTypes.length,
  };
}

const severityRank = {
  information: 0,
  caution: 1,
  high: 2,
  urgent: 3,
} as const;

const evidenceKey = (evidence: {
  sourceId: string;
  sourceVersion?: string;
  locator: string;
  url: string;
}) =>
  `${evidence.sourceId}\u0000${evidence.sourceVersion ?? ""}\u0000${evidence.locator}\u0000${evidence.url}`;

/**
 * 같은 제품 조합에서 성분마다 따로 생긴 중복 경고를 화면용 한 항목으로 묶는다.
 * 판정 엔진의 원본 finding은 바꾸지 않으며 다른 규칙과 다른 제품 조합은 합치지 않는다.
 */
export function groupFindingsForDisplay(
  findings: SafetyFinding[],
  ingredientNames: Map<string, string>,
): DisplayFinding[] {
  const groups = new Map<string, SafetyFinding[]>();

  for (const finding of findings) {
    const key =
      finding.ruleType === "duplicate_ingredient"
        ? `duplicate_ingredient:${finding.ruleId}:${finding.decisionBasis}:${[...finding.productIds].sort().join("+")}`
        : `finding:${finding.findingId}`;
    groups.set(key, [...(groups.get(key) ?? []), finding]);
  }

  return [...groups.entries()].map(([groupId, members]) => {
    if (members.length === 1) return { ...members[0], members };

    const ingredientIds = [...new Set(members.flatMap((item) => item.ingredientIds))];
    const ingredientLabels = ingredientIds.map(
      (ingredientId) => ingredientNames.get(ingredientId) ?? ingredientId,
    );
    const evidence = [
      ...new Map(
        members
          .flatMap((item) => item.evidence)
          .map((item) => [evidenceKey(item), item]),
      ).values(),
    ];
    const ruleEvidence = [
      ...new Map(
        members
          .flatMap((item) => item.ruleEvidence ?? [])
          .map((item) => [
            `${item.ruleId}\u0000${item.itemSequence}\u0000${evidenceKey(item)}`,
            item,
          ]),
      ).values(),
    ];
    const primary = members.reduce((highest, item) =>
      severityRank[item.severity] > severityRank[highest.severity] ? item : highest,
    );

    return {
      ...primary,
      findingId: `group:${groupId}`,
      titleKo: `같은 성분 ${ingredientIds.length}개가 여러 제품에 들어 있습니다`,
      detailKo: `겹치는 성분은 ${ingredientLabels.join(", ")}입니다. 성분별 하루 입력량은 결과 아래에서 확인할 수 있습니다.`,
      productIds: [...new Set(members.flatMap((item) => item.productIds))].sort(),
      ingredientIds,
      evidence,
      ruleEvidence,
      members,
      calculatedAmount: undefined,
      referenceAmount: undefined,
      unit: undefined,
    };
  });
}

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
  const exactRuleEvidence = [
    ...new Map(
      ruleEvidence
        .filter((evidence) => evidence.ruleId === finding.ruleId)
        .map((evidence) => [
          `${evidence.ruleId}\u0000${evidence.itemSequence}\u0000${evidenceKey(evidence)}`,
          evidence,
        ]),
    ).values(),
  ];
  const findingProductIds = new Set(finding.productIds);
  const findingItemSequences = new Set(
    selected
      .filter(({ product }) => findingProductIds.has(product.productId))
      .map(({ product }) => product.itemSequence),
  );
  const direct = exactRuleEvidence.filter((evidence) =>
    findingItemSequences.has(evidence.itemSequence),
  );
  const representative = exactRuleEvidence.filter(
    (evidence) => !findingItemSequences.has(evidence.itemSequence),
  );
  const matchedItemSequences = new Set(
    exactRuleEvidence
      .filter((evidence) => findingItemSequences.has(evidence.itemSequence))
      .map((evidence) => evidence.itemSequence),
  );
  const productMatch = matchedItemSequences.size === 0
    ? "none"
    : matchedItemSequences.size === findingItemSequences.size
      ? "all"
      : "partial";
  return {
    evidence: direct[0],
    direct,
    representative,
    productMatch,
    matchedProductCount: matchedItemSequences.size,
    findingProductCount: findingItemSequences.size,
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
  selected: SelectedProduct[],
  profile?: UserProfile,
): SupportingLiterature[] {
  return directLiteratureForFinding(finding, literature, selected, profile).map(
    ({ paper }) => paper,
  );
}

const normalizeLiteratureTerm = (value: string) =>
  value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\s\-_.·]/g, "");

const medicationMatchesScope = (
  medications: readonly string[],
  terms: readonly string[],
) =>
  medications.some((medication) => {
    const normalizedMedication = normalizeLiteratureTerm(medication);
    return terms.some((term) => {
      const normalizedTerm = normalizeLiteratureTerm(term);
      return (
        normalizedTerm.length > 0 && normalizedMedication.includes(normalizedTerm)
      );
    });
  });

const booleanProfileKeys = new Set<keyof UserProfile>([
  "pregnant",
  "lactating",
  "liverDisease",
  "kidneyDisease",
  "giBleedingOrUlcer",
  "hypertensionOrCardiovascularDisease",
  "willDrive",
  "alcohol",
]);

function profileConditionMatches(
  condition: string,
  profile: UserProfile | undefined,
  medicationTerms: readonly string[],
): boolean {
  if (!profile) return false;
  if (condition === "medications.class=oral_anticoagulant") {
    return (
      medicationTerms.length > 0 &&
      medicationMatchesScope(profile.medications, medicationTerms)
    );
  }

  const match = condition.match(/^([A-Za-z][A-Za-z0-9]*)(>=|<=|=)(.+)$/);
  if (!match) return false;
  const [, rawKey, operator, rawExpected] = match;
  if (rawKey === "ageYears" || rawKey === "pregnancyTrimester") {
    const actual = profile[rawKey];
    if (actual === undefined || !Number.isFinite(actual)) {
      return false;
    }
    const expected = Number(rawExpected);
    if (!Number.isFinite(expected)) return false;
    if (operator === ">=") return actual >= expected;
    if (operator === "<=") return actual <= expected;
    return actual === expected;
  }
  if (!booleanProfileKeys.has(rawKey as keyof UserProfile) || operator !== "=") {
    return false;
  }
  const actual = profile[rawKey as keyof UserProfile];
  if (typeof actual !== "boolean") return false;
  if (rawExpected === "true") return actual;
  if (rawExpected === "false") return !actual;
  return false;
}

function directScopeMatches(
  finding: SafetyFinding,
  selected: SelectedProduct[],
  profile: UserProfile | undefined,
  scope: SupportingLiteratureDirectScope,
): boolean {
  const findingIngredientIds = new Set(finding.ingredientIds);
  if (
    !scope.ingredientIds.every((ingredientId) =>
      findingIngredientIds.has(ingredientId),
    )
  ) {
    return false;
  }

  const findingProductIds = new Set(finding.productIds);
  const findingItemSequences = new Set(
    selected
      .filter(({ product }) => findingProductIds.has(product.productId))
      .map(({ product }) => product.itemSequence),
  );
  const relevantProducts = selected
    .filter(({ product }) => findingProductIds.has(product.productId))
    .map(({ product }) => product);
  if (
    !scope.productItemSequences.every((itemSequence) =>
      findingItemSequences.has(itemSequence),
    )
  ) {
    return false;
  }
  const scopedProducts =
    scope.productItemSequences.length > 0
      ? relevantProducts.filter((product) =>
          scope.productItemSequences.includes(product.itemSequence),
        )
      : relevantProducts;
  const scopedProductIngredientIds = new Set(
    scopedProducts.flatMap((product) =>
      product.ingredients.map((ingredient) => ingredient.ingredientId),
    ),
  );
  if (
    !scope.ingredientIds.every((ingredientId) =>
      scopedProductIngredientIds.has(ingredientId),
    )
  ) {
    return false;
  }
  if (
    !scope.profileConditions.every((condition) =>
      profileConditionMatches(condition, profile, scope.medicationTerms),
    )
  ) {
    return false;
  }
  if (
    scope.medicationTerms.length > 0 &&
    (!profile ||
      !medicationMatchesScope(profile.medications, scope.medicationTerms))
  ) {
    return false;
  }
  return true;
}

const literatureMatchSort = (
  left: FindingLiteratureMatch,
  right: FindingLiteratureMatch,
) =>
  right.paper.publicationYear - left.paper.publicationYear ||
  left.paper.pmid.localeCompare(right.paper.pmid) ||
  left.link.linkId.localeCompare(right.link.linkId);

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) &&
  value.every((item) => typeof item === "string" && item.trim().length > 0);

const hasValidDirectScope = (
  value: unknown,
): value is SupportingLiteratureDirectScope => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const scope = value as Record<string, unknown>;
  return (
    isStringArray(scope.ingredientIds) &&
    isStringArray(scope.productItemSequences) &&
    isStringArray(scope.profileConditions) &&
    isStringArray(scope.medicationTerms)
  );
};

const hasAnyDirectScopeCondition = (
  scope: SupportingLiteratureDirectScope,
): boolean =>
  scope.ingredientIds.length > 0 ||
  scope.productItemSequences.length > 0 ||
  scope.profileConditions.length > 0 ||
  scope.medicationTerms.length > 0;

export function isValidSupportingLiteratureUiLink(
  value: unknown,
): value is SupportingLiteratureRuleLink {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const link = value as Record<string, unknown>;
  const classification = link.v51Classification;
  if (
    !classification ||
    typeof classification !== "object" ||
    Array.isArray(classification) ||
    link.ruleReleased !== true
  ) {
    return false;
  }
  const policy = classification as Record<string, unknown>;
  if (
    policy.lineageStatus !== "v50_emitted" ||
    typeof policy.classificationId !== "string" ||
    policy.classificationId.trim().length === 0 ||
    typeof policy.classificationReasonKo !== "string" ||
    policy.classificationReasonKo.trim().length === 0 ||
    typeof policy.uiBoundaryKo !== "string" ||
    policy.uiBoundaryKo.trim().length === 0 ||
    typeof policy.uiDirectLabelAllowed !== "boolean" ||
    policy.humanExpertReviewed !== false ||
    policy.supportsRuleRelease !== false ||
    !hasValidDirectScope(policy.directScope)
  ) {
    return false;
  }
  if (policy.uiPolicy === "direct") {
    return (
      policy.semanticClassification === "direct_match" &&
      policy.uiDirectLabelAllowed === true &&
      hasAnyDirectScopeCondition(policy.directScope)
    );
  }
  if (policy.uiPolicy === "background_only") {
    return (
      policy.semanticClassification === "background_context" &&
      policy.uiDirectLabelAllowed === false
    );
  }
  if (policy.uiPolicy === "direct_when_scope_matches_else_background") {
    return (
      policy.semanticClassification === "mixed_scope" &&
      policy.uiDirectLabelAllowed === true &&
      hasAnyDirectScopeCondition(policy.directScope)
    );
  }
  return false;
}

export function splitSupportingLiteratureForFinding(
  finding: SafetyFinding,
  literature: SupportingLiterature[],
  selected: SelectedProduct[],
  profile?: UserProfile,
): SplitSupportingLiterature {
  if (finding.decisionBasis !== "released_rule") {
    return { direct: [], background: [] };
  }

  const direct: FindingLiteratureMatch[] = [];
  const background: FindingLiteratureMatch[] = [];
  const sourceFindings =
    "members" in finding && Array.isArray(finding.members)
      ? finding.members.filter(
          (member) => member.decisionBasis === "released_rule",
        )
      : [finding];
  for (const paper of literature) {
    for (const link of paper.ruleLinks) {
      if (!isValidSupportingLiteratureUiLink(link)) continue;
      const classification = link.v51Classification;
      const exactFindings = sourceFindings.filter(
        (sourceFinding) =>
          link.ruleId === sourceFinding.ruleId &&
          link.ruleType === sourceFinding.ruleType,
      );
      if (exactFindings.length === 0) continue;
      const match = { paper, link };
      const directAllowed = exactFindings.some((sourceFinding) =>
        directScopeMatches(
          sourceFinding,
          selected,
          profile,
          classification.directScope,
        ),
      );
      if (classification.uiPolicy === "background_only") {
        background.push(match);
      } else if (directAllowed) {
        direct.push(match);
      } else if (
        classification.uiPolicy ===
        "direct_when_scope_matches_else_background"
      ) {
        background.push(match);
      }
    }
  }
  return {
    direct: direct.sort(literatureMatchSort),
    background: background.sort(literatureMatchSort),
  };
}

export function directLiteratureForFinding(
  finding: SafetyFinding,
  literature: SupportingLiterature[],
  selected: SelectedProduct[],
  profile?: UserProfile,
): FindingLiteratureMatch[] {
  return splitSupportingLiteratureForFinding(
    finding,
    literature,
    selected,
    profile,
  ).direct;
}

export function backgroundLiteratureForFinding(
  finding: SafetyFinding,
  literature: SupportingLiterature[],
  selected: SelectedProduct[],
  profile?: UserProfile,
): FindingLiteratureMatch[] {
  return splitSupportingLiteratureForFinding(
    finding,
    literature,
    selected,
    profile,
  ).background;
}

export function literatureStatusSummary(
  literature: SupportingLiterature[],
): LiteratureStatusSummary {
  const summary: LiteratureStatusSummary = {
    v5Linked: 0,
    directCapable: 0,
    backgroundOnly: 0,
    excluded: 0,
  };
  for (const paper of literature) {
    for (const link of paper.ruleLinks) {
      if (!isValidSupportingLiteratureUiLink(link)) {
        summary.excluded += 1;
        continue;
      }
      const classification = link.v51Classification;
      summary.v5Linked += 1;
      if (classification.uiPolicy === "background_only") {
        summary.backgroundOnly += 1;
      } else if (classification.uiDirectLabelAllowed) {
        summary.directCapable += 1;
      }
    }
  }
  return summary;
}

export function literatureStatusLabel(
  link: SupportingLiteratureRuleLink,
): string {
  if (!isValidSupportingLiteratureUiLink(link)) return "결과 화면 제외 문헌";
  if (link.v51Classification.uiPolicy === "background_only") {
    return "v5.0 배경 문헌";
  }
  if (link.v51Classification.uiPolicy === "direct") {
    return "v5.0 직접 일치 문헌";
  }
  if (
    link.v51Classification.uiPolicy ===
    "direct_when_scope_matches_else_background"
  ) {
    return "v5.0 범위 일치 시 직접 문헌";
  }
  return "결과 화면 제외 문헌";
}

export function literaturePlacementLabel(
  kind: "direct" | "background",
): string {
  return kind === "direct" ? "v5.0 직접 일치 문헌" : "v5.0 배경 문헌";
}

export function literatureHomepageStatusSummary(
  literature: readonly SupportingLiterature[],
): LiteratureHomepageStatusSummary {
  const linkedIds = new Set<string>();
  const ruleIds = new Set<string>();
  const directIds = new Set<string>();
  const conditionalIds = new Set<string>();
  const backgroundIds = new Set<string>();
  let excluded = 0;

  for (const paper of literature) {
    for (const link of paper.ruleLinks) {
      if (!isValidSupportingLiteratureUiLink(link)) {
        excluded += 1;
        continue;
      }
      linkedIds.add(link.linkId);
      ruleIds.add(link.ruleId);
      if (link.v51Classification.uiPolicy === "direct") {
        directIds.add(link.linkId);
      } else if (
        link.v51Classification.uiPolicy ===
        "direct_when_scope_matches_else_background"
      ) {
        conditionalIds.add(link.linkId);
      } else {
        backgroundIds.add(link.linkId);
      }
    }
  }

  return {
    v5Linked: linkedIds.size,
    v5RuleCount: ruleIds.size,
    directMatch: directIds.size,
    conditionalDirect: conditionalIds.size,
    backgroundOnly: backgroundIds.size,
    excluded,
  };
}

const crossProductLiteratureRuleIds = new Set([
  // These selection-level rules intentionally have no per-product binding.
  "OTC-RULE-001",
  "OTC-RULE-002",
]);

const isOptionalNonemptyStringArray = (
  value: unknown,
): value is string[] | undefined =>
  value === undefined || (isStringArray(value) && value.length > 0);

function releasedRuleAppliesToLiteratureProduct(
  product: OtcProduct,
  link: SupportingLiteratureRuleLink,
  policy: ReleasedRulePolicy,
): boolean {
  if (
    policy.ruleId !== link.ruleId ||
    policy.ruleType !== link.ruleType ||
    policy.lineageStatus !== "mapped_from_v50_released_rule" ||
    !policy.applicability ||
    typeof policy.applicability !== "object" ||
    Array.isArray(policy.applicability)
  ) {
    return false;
  }

  const applicability = policy.applicability;
  if (
    !isOptionalNonemptyStringArray(applicability.productItemSequences) ||
    !isOptionalNonemptyStringArray(applicability.ingredientIds) ||
    !isOptionalNonemptyStringArray(applicability.pharmacologicClasses) ||
    !isOptionalNonemptyStringArray(applicability.requiredAnchorIngredientIds) ||
    !isOptionalNonemptyStringArray(applicability.administrationConstraintTypes)
  ) {
    return false;
  }

  const explicitlyBound = product.supportedReleasedRuleIds?.includes(link.ruleId);
  const approvedCrossProductRule =
    crossProductLiteratureRuleIds.has(link.ruleId) &&
    applicability.productItemSequences === undefined;
  if (!explicitlyBound && !approvedCrossProductRule) return false;

  if (
    applicability.productItemSequences &&
    !applicability.productItemSequences.includes(product.itemSequence)
  ) {
    return false;
  }
  const ingredientIds = new Set(
    product.ingredients.map((ingredient) => ingredient.ingredientId),
  );
  if (
    applicability.ingredientIds &&
    !applicability.ingredientIds.some((ingredientId) =>
      ingredientIds.has(ingredientId),
    )
  ) {
    return false;
  }
  if (
    applicability.requiredAnchorIngredientIds &&
    !applicability.requiredAnchorIngredientIds.every((ingredientId) =>
      ingredientIds.has(ingredientId),
    )
  ) {
    return false;
  }
  if (
    applicability.pharmacologicClasses &&
    !product.ingredients.some((ingredient) =>
      ingredient.pharmacologicClasses.some((group) =>
        applicability.pharmacologicClasses?.includes(group),
      ),
    )
  ) {
    return false;
  }
  if (
    applicability.administrationConstraintTypes &&
    !applicability.administrationConstraintTypes.every((constraintType) =>
      (product.administrationConstraints ?? []).some(
        (constraint) => constraint.type === constraintType,
      ),
    )
  ) {
    return false;
  }
  return true;
}

export function productLiteratureCoverage(
  product: OtcProduct,
  literature: SupportingLiterature[],
  releasedRules: readonly ReleasedRulePolicy[],
): { v5Linked: number; directCapable: number } {
  const releasedRuleById = new Map(
    releasedRules.map((rule) => [rule.ruleId, rule]),
  );
  const ingredientIds = new Set(
    product.ingredients.map((ingredient) => ingredient.ingredientId),
  );
  const matchingLinks = literature.flatMap((paper) =>
    paper.ruleLinks.filter((link) => {
      const releasedRule = releasedRuleById.get(link.ruleId);
      if (
        !isValidSupportingLiteratureUiLink(link) ||
        !releasedRule ||
        !releasedRuleAppliesToLiteratureProduct(product, link, releasedRule)
      ) {
        return false;
      }
      const classification = link.v51Classification;
      const scope = classification.directScope;
      return (
        scope.ingredientIds.every((ingredientId) =>
          ingredientIds.has(ingredientId),
        ) &&
        scope.productItemSequences.every(
          (itemSequence) => itemSequence === product.itemSequence,
        )
      );
    }),
  );
  return {
    v5Linked: matchingLinks.length,
    directCapable: matchingLinks.filter(
      (link) => link.v51Classification.uiDirectLabelAllowed,
    ).length,
  };
}

export function productsForTherapeuticClass(
  products: OtcProduct[],
  therapeuticClass: string,
): OtcProduct[] {
  if (therapeuticClass === "전체") return products;
  return products.filter((product) => product.therapeuticClass === therapeuticClass);
}

import type {
  AdministrationConstraint,
  EvaluationCoverageGap,
  EvidenceLink,
  OtcEvaluationOptions,
  OtcIngredient,
  OtcProduct,
  ReleasedRuleEvidenceLink,
  ReleasedRulePolicy,
  RuleApplicability,
  RuleEvidenceLink,
  SafetyEvaluation,
  SafetyFinding,
  SafetyInputIssue,
  SelectedProduct,
  UserProfile,
  UrgentReferralBinding,
} from "./schema";

const uniqueEvidence = <T extends EvidenceLink>(links: T[]): T[] =>
  [
    ...new Map(
      links.map((link) => [
        `${link.sourceId}|${link.sourceVersion ?? ""}|${link.locator}|${link.url}`,
        link,
      ]),
    ).values(),
  ];

const normalizeTerm = (value: string) =>
  value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\s\-_.·]/g, "");

const textMatchesTerms = (value: string, terms: readonly string[]) => {
  const normalizedValue = normalizeTerm(value);
  return terms.some((term) => {
    const normalizedTerm = normalizeTerm(term);
    return normalizedTerm.length > 0 && normalizedValue.includes(normalizedTerm);
  });
};

const medicationItems = (profile: UserProfile) =>
  profile.medications.flatMap((medication) =>
    medication
      .normalize("NFKC")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );

const medicationMatchesTerms = (medication: string, terms: readonly string[]) => {
  const normalizedMedication = normalizeTerm(medication);
  return terms.some((term) => {
    const normalizedTerm = normalizeTerm(term);
    return normalizedTerm.length > 0 && normalizedMedication === normalizedTerm;
  });
};

const matchingMedications = (profile: UserProfile, terms: readonly string[]) =>
  medicationItems(profile).filter((medication) =>
    medicationMatchesTerms(medication, terms),
  );

const isPositiveFinite = (value: number) => Number.isFinite(value) && value > 0;

const constraintRuleType = (constraint: AdministrationConstraint) =>
  constraint.type === "minimum_interval_hours" ? "minimum_interval" : "max_daily_dose";

const isEvaluationOptions = (
  value: OtcEvaluationOptions | ReadonlySet<string> | undefined,
): value is OtcEvaluationOptions =>
  Boolean(
    value &&
      "releasedRules" in value &&
      Array.isArray((value as OtcEvaluationOptions).releasedRules),
  );

const isRuleTypeSet = (
  value: OtcEvaluationOptions | ReadonlySet<string> | undefined,
): value is ReadonlySet<string> =>
  Boolean(value && "has" in value && typeof value.has === "function");

const isNonemptyStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) &&
  value.length > 0 &&
  value.every(
    (item) => typeof item === "string" && item.trim().length > 0,
  );

const isRuleApplicability = (value: unknown): value is RuleApplicability => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const applicability = value as Record<string, unknown>;
  const stringArrayFields = [
    "productItemSequences",
    "ingredientIds",
    "pharmacologicClasses",
    "requiredAnchorIngredientIds",
    "medicationTerms",
    "urgentTerms",
  ];
  const supportedFields = new Set([
    ...stringArrayFields,
    "administrationConstraintTypes",
    "pregnancyTrimesters",
    "minimumAgeYears",
    "lactationSupported",
  ]);
  const fields = Object.keys(applicability);
  if (!fields.length || fields.some((field) => !supportedFields.has(field))) {
    return false;
  }
  if (
    stringArrayFields.some(
      (field) =>
        applicability[field] !== undefined &&
        !isNonemptyStringArray(applicability[field]),
    )
  ) {
    return false;
  }
  const constraintTypes = applicability.administrationConstraintTypes;
  if (
    constraintTypes !== undefined &&
    (!isNonemptyStringArray(constraintTypes) ||
      constraintTypes.some(
        (constraintType) =>
          ![
            "maximum_units_per_dose",
            "maximum_doses_per_day",
            "maximum_daily_ingredient_amount",
            "minimum_interval_hours",
          ].includes(constraintType),
      ))
  ) {
    return false;
  }
  const trimesters = applicability.pregnancyTrimesters;
  if (
    trimesters !== undefined &&
    (!Array.isArray(trimesters) ||
      trimesters.length === 0 ||
      trimesters.some((trimester) => ![1, 2, 3].includes(trimester as number)))
  ) {
    return false;
  }
  const minimumAgeYears = applicability.minimumAgeYears;
  if (
    minimumAgeYears !== undefined &&
    (typeof minimumAgeYears !== "number" ||
      !Number.isFinite(minimumAgeYears) ||
      minimumAgeYears < 0)
  ) {
    return false;
  }
  return (
    applicability.lactationSupported === undefined ||
    typeof applicability.lactationSupported === "boolean"
  );
};

export const isExecutableReleasedRulePolicy = (
  value: unknown,
): value is ReleasedRulePolicy => {
  if (!value || typeof value !== "object") return false;
  const policy = value as Partial<ReleasedRulePolicy>;
  if (
    typeof policy.ruleId !== "string" ||
    !policy.ruleId.trim() ||
    typeof policy.ruleType !== "string" ||
    !policy.ruleType.trim() ||
    typeof policy.scope !== "string" ||
    !policy.scope.trim() ||
    policy.lineageStatus !== "mapped_from_v50_released_rule" ||
    !isRuleApplicability(policy.applicability) ||
    !Array.isArray(policy.evidence) ||
    policy.evidence.length === 0
  ) {
    return false;
  }
  return policy.evidence.every(
    (evidence) =>
      Boolean(evidence) &&
      typeof evidence === "object" &&
      evidence.ruleId === policy.ruleId &&
      typeof evidence.sourceId === "string" &&
      evidence.sourceId.trim().length > 0 &&
      typeof evidence.sourceVersion === "string" &&
      evidence.sourceVersion.trim().length > 0 &&
      typeof evidence.locator === "string" &&
      evidence.locator.trim().length > 0 &&
      typeof evidence.url === "string" &&
      evidence.url.trim().length > 0 &&
      typeof evidence.itemSequence === "string" &&
      evidence.itemSequence.trim().length > 0 &&
      typeof evidence.productName === "string" &&
      evidence.productName.trim().length > 0 &&
      typeof evidence.excerptKo === "string" &&
      evidence.excerptKo.trim().length > 0,
  );
};

function policiesFromLegacyArguments(
  enabledRuleTypes: ReadonlySet<string> | undefined,
  urgentReferralBindings: UrgentReferralBinding[] | undefined,
  ruleEvidenceByType: Record<string, RuleEvidenceLink[]> | undefined,
): ReleasedRulePolicy[] {
  if (!enabledRuleTypes || !ruleEvidenceByType) return [];

  const byRuleId = new Map<string, ReleasedRulePolicy>();
  for (const [legacyRuleType, links] of Object.entries(ruleEvidenceByType)) {
    if (!Array.isArray(links)) continue;
    for (const link of links) {
      if (!link || typeof link !== "object") continue;
      const ruleType = link.ruleType ?? legacyRuleType;
      const sourceVersion = link.sourceVersion;
      if (
        typeof link.ruleId !== "string" ||
        !link.ruleId.trim() ||
        typeof ruleType !== "string" ||
        !ruleType.trim() ||
        !enabledRuleTypes.has(ruleType) ||
        !link.scope ||
        link.lineageStatus !== "mapped_from_v50_released_rule" ||
        !isRuleApplicability(link.applicability) ||
        typeof sourceVersion !== "string" ||
        sourceVersion.trim().length === 0
      ) {
        continue;
      }
      const releasedLink: ReleasedRuleEvidenceLink = {
        ...link,
        sourceVersion,
      };
      const existing = byRuleId.get(link.ruleId);
      if (existing) {
        existing.evidence.push(releasedLink);
        continue;
      }
      const applicability = { ...link.applicability };
      if (
        ruleType === "urgent_referral" &&
        !applicability.urgentTerms?.length
      ) {
        const scopedItems = new Set(
          applicability.productItemSequences ?? [link.itemSequence],
        );
        applicability.urgentTerms = (urgentReferralBindings ?? [])
          .filter((binding) => scopedItems.has(binding.itemSequence))
          .flatMap((binding) => binding.terms);
      }
      byRuleId.set(link.ruleId, {
        ruleId: link.ruleId,
        ruleType,
        scope: link.scope,
        lineageStatus: link.lineageStatus,
        applicability,
        evidence: [releasedLink],
      });
    }
  }
  return [...byRuleId.values()].filter(isExecutableReleasedRulePolicy);
}

function resolvePolicies(
  optionsOrEnabledRuleTypes: OtcEvaluationOptions | ReadonlySet<string> | undefined,
  urgentReferralBindings: UrgentReferralBinding[] | undefined,
  ruleEvidenceByType: Record<string, RuleEvidenceLink[]> | undefined,
): ReleasedRulePolicy[] {
  if (isEvaluationOptions(optionsOrEnabledRuleTypes)) {
    const seenRuleIds = new Set<string>();
    const duplicateRuleIds = new Set<string>();
    for (const value of optionsOrEnabledRuleTypes.releasedRules) {
      if (!value || typeof value !== "object") continue;
      const ruleId = (value as Partial<ReleasedRulePolicy>).ruleId;
      if (typeof ruleId !== "string" || !ruleId.trim()) continue;
      if (seenRuleIds.has(ruleId)) duplicateRuleIds.add(ruleId);
      seenRuleIds.add(ruleId);
    }
    const executable = optionsOrEnabledRuleTypes.releasedRules.filter(
      isExecutableReleasedRulePolicy,
    );
    return executable.filter((policy) => !duplicateRuleIds.has(policy.ruleId));
  }
  return policiesFromLegacyArguments(
    isRuleTypeSet(optionsOrEnabledRuleTypes)
      ? optionsOrEnabledRuleTypes
      : undefined,
    urgentReferralBindings,
    ruleEvidenceByType,
  );
}

const policyAppliesToProduct = (
  policy: ReleasedRulePolicy,
  product: OtcProduct,
  ageYears: number | undefined,
) => {
  const applicability = policy.applicability;
  if (
    applicability.productItemSequences?.length &&
    !applicability.productItemSequences.includes(product.itemSequence)
  ) {
    return false;
  }
  if (
    applicability.ingredientIds?.length &&
    !product.ingredients.some((ingredient) =>
      applicability.ingredientIds?.includes(ingredient.ingredientId),
    )
  ) {
    return false;
  }
  if (
    applicability.pharmacologicClasses?.length &&
    !product.ingredients.some((ingredient) =>
      ingredient.pharmacologicClasses.some((group) =>
        applicability.pharmacologicClasses?.includes(group),
      ),
    )
  ) {
    return false;
  }
  if (applicability.administrationConstraintTypes?.length) {
    const hasDirectConstraint = (product.administrationConstraints ?? []).some(
      (constraint) =>
        applicability.administrationConstraintTypes?.includes(constraint.type),
    );
    const hasLegacyConstraint = applicability.administrationConstraintTypes.some(
      (constraintType) =>
        constraintType === "maximum_daily_ingredient_amount"
          ? product.ingredients.some(
              (ingredient) => ingredient.maxDailyAmount !== undefined,
            )
          : constraintType === "minimum_interval_hours"
            ? product.ingredients.some(
                (ingredient) => ingredient.minimumIntervalHours !== undefined,
              )
            : false,
    );
    if (!hasDirectConstraint && !hasLegacyConstraint) return false;
  }
  if (
    applicability.minimumAgeYears !== undefined &&
    (ageYears === undefined || ageYears < applicability.minimumAgeYears)
  ) {
    return false;
  }
  return true;
};

export function evaluateOtcSafety(
  selected: SelectedProduct[],
  profile: UserProfile,
  optionsOrEnabledRuleTypes?: OtcEvaluationOptions | ReadonlySet<string>,
  urgentReferralBindings?: UrgentReferralBinding[],
  ruleEvidenceByType?: Record<string, RuleEvidenceLink[]>,
): SafetyEvaluation {
  const releasedRules = resolvePolicies(
    optionsOrEnabledRuleTypes,
    urgentReferralBindings,
    ruleEvidenceByType,
  );
  const rulesByType = new Map<string, ReleasedRulePolicy[]>();
  for (const rule of releasedRules) {
    const sameType = rulesByType.get(rule.ruleType) ?? [];
    sameType.push(rule);
    rulesByType.set(rule.ruleType, sameType);
  }
  const applicabilityAgeYears =
    profile.ageYears !== undefined &&
    Number.isFinite(profile.ageYears) &&
    profile.ageYears >= 0 &&
    profile.ageYears <= 120
      ? profile.ageYears
      : undefined;
  const policiesForProduct = (ruleType: string, product: OtcProduct) =>
    (rulesByType.get(ruleType) ?? []).filter((policy) =>
      policyAppliesToProduct(policy, product, applicabilityAgeYears),
    );
  const releasedRuleById = new Map(
    releasedRules.map((rule) => [rule.ruleId, rule]),
  );
  const allowsSeparateAdministrationConstraintDecision = (
    ruleId: string,
    product: OtcProduct,
    constraintType: AdministrationConstraint["type"],
  ) => {
    const template = releasedRuleById.get(ruleId);
    if (!template) return false;
    // A scoped released rule keeps its own ID only inside that product scope.
    // Other products may still use their exact MFDS constraint ID. If the scoped
    // product misses another condition (for example age), do not fall back to ADMIN.
    const itemIsInReleasedScope =
      template.applicability.productItemSequences?.includes(
        product.itemSequence,
      ) ?? false;
    if (!itemIsInReleasedScope) return true;
    if (
      template.applicability.minimumAgeYears !== undefined &&
      (applicabilityAgeYears === undefined ||
        applicabilityAgeYears < template.applicability.minimumAgeYears)
    ) {
      return false;
    }
    return !template.applicability.administrationConstraintTypes?.includes(
      constraintType,
    );
  };

  const policyMatchesConstraint = (
    policy: ReleasedRulePolicy,
    constraintType: AdministrationConstraint["type"],
  ) =>
    !policy.applicability.administrationConstraintTypes?.length ||
    policy.applicability.administrationConstraintTypes.includes(constraintType);

  const findings: SafetyFinding[] = [];
  const inputIssues: SafetyInputIssue[] = [];
  const coverageGaps: EvaluationCoverageGap[] = [];
  const issueFields = new Map<string, Set<SafetyInputIssue["field"]>>();

  const addFinding = (
    policy: ReleasedRulePolicy,
    finding: Omit<SafetyFinding, "ruleId" | "ruleType" | "decisionBasis">,
  ) => {
    const findingId = findings.some((candidate) => candidate.findingId === finding.findingId)
      ? `${finding.findingId}:${policy.ruleId}`
      : finding.findingId;
    findings.push({
      ...finding,
      findingId,
      ruleId: policy.ruleId,
      decisionBasis: "released_rule",
      ruleType: policy.ruleType,
    });
  };

  const addConstraintFinding = (
    constraint: AdministrationConstraint,
    finding: Omit<SafetyFinding, "ruleId" | "ruleType" | "decisionBasis">,
  ) => {
    findings.push({
      ...finding,
      ruleId: constraint.constraintId,
      decisionBasis: "administration_constraint",
      ruleType: constraintRuleType(constraint),
    });
  };

  const addCoverageGap = (gap: EvaluationCoverageGap) => {
    if (coverageGaps.some((candidate) => candidate.gapId === gap.gapId)) return;
    coverageGaps.push(gap);
  };

  const addProductCoverageGap = (
    product: OtcProduct,
    ruleType: string,
    checkLabel: string,
    dimension = ruleType,
  ) => {
    addCoverageGap({
      gapId: `coverage:${product.productId}:${dimension}`,
      ruleType,
      titleKo: `${checkLabel} 기준을 확인하지 못했습니다`,
      detailKo: `${product.productName}에 적용할 검증된 ${checkLabel} 기준이 현재 앱에 연결되어 있지 않습니다. 제품 포장과 허가사항을 직접 확인하세요.`,
      productIds: [product.productId],
    });
  };

  const addCombinationCoverageGap = (
    gapId: string,
    ruleType: string,
    detailKo: string,
    productIds: string[],
  ) => {
    addCoverageGap({
      gapId,
      ruleType,
      titleKo: "선택한 제품 조합의 판정 범위를 확인하지 못했습니다",
      detailKo,
      productIds: [...new Set(productIds)],
    });
  };

  const addInputIssue = (
    productId: string | undefined,
    field: SafetyInputIssue["field"],
    messageKo: string,
  ) => {
    const issueId = `input:${productId ?? "profile"}:${field}`;
    if (inputIssues.some((issue) => issue.issueId === issueId)) return;
    inputIssues.push({ issueId, productId, field, messageKo });
    if (productId) {
      const fields = issueFields.get(productId) ?? new Set<SafetyInputIssue["field"]>();
      fields.add(field);
      issueFields.set(productId, fields);
    }
  };

  for (const item of selected) {
    const productName = item.product.productName;
    if (!isPositiveFinite(item.unitsPerDose)) {
      addInputIssue(
        item.product.productId,
        "unitsPerDose",
        `${productName}의 1회 복용량을 0보다 큰 숫자로 입력하세요.`,
      );
    }
    if (!isPositiveFinite(item.dosesPerDay) || !Number.isInteger(item.dosesPerDay)) {
      addInputIssue(
        item.product.productId,
        "dosesPerDay",
        `${productName}의 하루 복용 횟수를 1 이상의 정수로 입력하세요.`,
      );
    }
    if (
      item.hoursSincePreviousDose !== undefined &&
      (!Number.isFinite(item.hoursSincePreviousDose) || item.hoursSincePreviousDose < 0)
    ) {
      addInputIssue(
        item.product.productId,
        "hoursSincePreviousDose",
        `${productName}의 이전 복용 후 시간을 0 이상의 숫자로 입력하세요.`,
      );
    }
    if (
      item.continuousDays !== undefined &&
      (!isPositiveFinite(item.continuousDays) || !Number.isInteger(item.continuousDays))
    ) {
      addInputIssue(
        item.product.productId,
        "continuousDays",
        `${productName}의 연속 복용일을 1 이상의 정수로 입력하세요.`,
      );
    }
  }
  if (
    profile.ageYears !== undefined &&
    (!Number.isFinite(profile.ageYears) || profile.ageYears < 0 || profile.ageYears > 120)
  ) {
    addInputIssue(
      undefined,
      "ageYears",
      "나이를 0세부터 120세 사이의 숫자로 입력하세요.",
    );
  }
  if (
    profile.pregnancyTrimester !== undefined &&
    ![1, 2, 3].includes(profile.pregnancyTrimester)
  ) {
    addInputIssue(
      undefined,
      "pregnancyTrimester",
      "임신 주기는 1기, 2기, 3기 중에서 선택하세요.",
    );
  }

  const hasIssue = (productId: string, ...fields: SafetyInputIssue["field"][]) =>
    fields.some((field) => issueFields.get(productId)?.has(field));
  const selectedForDose = selected.filter(
    (item) => !hasIssue(item.product.productId, "unitsPerDose", "dosesPerDay"),
  );

  const ingredientUses = new Map<
    string,
    Array<{ selected: SelectedProduct; ingredient: OtcIngredient; daily: number }>
  >();
  for (const item of selectedForDose) {
    for (const ingredient of item.product.ingredients) {
      const daily = ingredient.amountPerUnit * item.unitsPerDose * item.dosesPerDay;
      const uses = ingredientUses.get(ingredient.ingredientId) ?? [];
      uses.push({ selected: item, ingredient, daily });
      ingredientUses.set(ingredient.ingredientId, uses);
    }
  }

  const ingredientDailyTotals: Record<string, { amount: number; unit: string }> = {};
  for (const [ingredientId, uses] of ingredientUses) {
    const productIds = [...new Set(uses.map((use) => use.selected.product.productId))];
    const units = new Set(uses.map((use) => use.ingredient.unit));
    if (units.size > 1) {
      addCombinationCoverageGap(
        `coverage:combination:${ingredientId}:unit-mismatch`,
        "duplicate_ingredient",
        `${ingredientId}의 단위가 ${[...units].join(", ")}로 서로 달라 총량과 중복을 판정하지 않았습니다. 제품 허가사항을 직접 확인하세요.`,
        productIds,
      );
      continue;
    }

    const unit = uses[0].ingredient.unit;
    const amount = uses.reduce((sum, use) => sum + use.daily, 0);
    ingredientDailyTotals[ingredientId] = { amount, unit };

    if (productIds.length > 1) {
      const duplicatePolicies = (rulesByType.get("duplicate_ingredient") ?? []).filter(
        (policy) =>
          policy.applicability.ingredientIds?.includes(ingredientId) &&
          uses.every((use) =>
            policyAppliesToProduct(
              policy,
              use.selected.product,
              applicabilityAgeYears,
            ),
          ),
      );
      if (duplicatePolicies.length) {
        for (const policy of duplicatePolicies) {
          addFinding(policy, {
            findingId: `duplicate-ingredient:${ingredientId}`,
            severity: "high",
            titleKo: "같은 성분이 여러 제품에 들어 있습니다",
            detailKo: `${uses.map((use) => use.selected.product.productName).join(", ")}에 ${uses[0].ingredient.nameKo}이(가) 겹칩니다. 계산된 하루 총량은 ${amount} ${unit}입니다.`,
            nextActionKo: "추가 복용 전 제품 포장과 허가사항을 확인하고 약사 또는 의사와 상담하세요.",
            productIds,
            ingredientIds: [ingredientId],
            calculatedAmount: amount,
            unit,
            evidence: uniqueEvidence(
              uses.flatMap((use) => [
                use.ingredient.evidence,
                use.selected.product.evidence,
              ]),
            ),
          });
        }
      } else {
        addCombinationCoverageGap(
          `coverage:combination:${ingredientId}:duplicate-ingredient`,
          "duplicate_ingredient",
          `${uses.map((use) => use.selected.product.productName).join(", ")}에 ${uses[0].ingredient.nameKo}이(가) 겹치지만, 이 성분 조합을 판정할 승인 규칙이 없습니다.`,
          productIds,
        );
      }
    }

    const directLimits = [
      ...new Map(
        uses.flatMap((use) =>
          (use.selected.product.administrationConstraints ?? [])
            .filter(
              (constraint) =>
                constraint.type === "maximum_daily_ingredient_amount" &&
                constraint.ingredientId === ingredientId &&
                constraint.valueUnit === unit &&
                isPositiveFinite(constraint.value),
            )
            .map((constraint) => [
              constraint.constraintId,
              {
                value: constraint.value,
                evidence: constraint.evidence,
                constraint,
                product: use.selected.product,
              },
            ] as const),
        ),
      ).values(),
    ];
    const productsWithDirectLimits = new Set(
      directLimits.map((limit) => limit.product.productId),
    );
    const legacyLimitRows = [
      ...new Map(
        uses
          .filter(
            (use) =>
              use.ingredient.maxDailyAmount !== undefined &&
              !productsWithDirectLimits.has(use.selected.product.productId),
          )
          .map((use) => [
            `${use.selected.product.productId}|${use.ingredient.maxDailyAmount}|${use.ingredient.evidence.sourceId}|${use.ingredient.evidence.locator}|${use.ingredient.evidence.url}`,
            {
              value: use.ingredient.maxDailyAmount as number,
              evidence: use.ingredient.evidence,
              product: use.selected.product,
              constraint: undefined,
            },
          ]),
      ).values(),
    ];
    for (const limitRow of [...directLimits, ...legacyLimitRows]) {
      const scopedUses = uses.filter(
        (use) => use.selected.product.productId === limitRow.product.productId,
      );
      const scopedAmount = scopedUses.reduce((sum, use) => sum + use.daily, 0);
      if (scopedAmount > limitRow.value) {
        const policies = (rulesByType.get("max_daily_dose") ?? []).filter((policy) =>
          policyMatchesConstraint(
            policy,
            "maximum_daily_ingredient_amount",
          ) &&
          (!policy.applicability.ingredientIds?.length ||
            policy.applicability.ingredientIds.includes(ingredientId)) &&
          policyAppliesToProduct(
            policy,
            limitRow.product,
            applicabilityAgeYears,
          ),
        );
        const limitIdentity =
          limitRow.constraint?.constraintId ?? `legacy-${ingredientId}`;
        const finding = {
            findingId: `max-daily:${limitRow.product.productId}:${limitIdentity}`,
            severity: "high",
            titleKo: "확인된 최대 1일 용량을 초과합니다",
            detailKo: `${scopedUses[0].ingredient.nameKo}의 ${limitRow.product.productName} 하루 총량 ${scopedAmount} ${unit}이 이 제품의 기준 ${limitRow.value} ${unit}보다 큽니다.`,
            nextActionKo: "추가 복용하지 말고 약사 또는 의사와 상담하세요.",
            productIds: [limitRow.product.productId],
            ingredientIds: [ingredientId],
            calculatedAmount: scopedAmount,
            referenceAmount: limitRow.value,
            unit,
            evidence: [limitRow.evidence],
          } satisfies Omit<SafetyFinding, "ruleId" | "ruleType" | "decisionBasis">;
        if (policies.length > 0) {
          for (const policy of policies) addFinding(policy, finding);
        } else if (
          limitRow.constraint &&
          allowsSeparateAdministrationConstraintDecision(
            "OTC-RULE-003",
            limitRow.product,
            limitRow.constraint.type,
          )
        ) {
          addConstraintFinding(limitRow.constraint, finding);
        } else {
          addCombinationCoverageGap(
            `coverage:${limitRow.product.productId}:${ingredientId}:unmapped-maximum-source`,
            "max_daily_dose",
            `${scopedUses[0].ingredient.nameKo}의 초과 상한을 안정적인 ruleId 또는 허가 제약 ID에 연결하지 못했습니다.`,
            [limitRow.product.productId],
          );
        }
      }
    }
  }

  const classUses = new Map<
    string,
    Array<{ selected: SelectedProduct; ingredient: OtcIngredient }>
  >();
  for (const item of selected) {
    for (const ingredient of item.product.ingredients) {
      for (const group of ingredient.pharmacologicClasses) {
        const uses = classUses.get(group) ?? [];
        uses.push({ selected: item, ingredient });
        classUses.set(group, uses);
      }
    }
  }
  for (const [group, uses] of classUses) {
    const productIds = [...new Set(uses.map((use) => use.selected.product.productId))];
    const ingredientIds = [...new Set(uses.map((use) => use.ingredient.ingredientId))];
    if (productIds.length <= 1 || ingredientIds.length <= 1) continue;

    const policies = (rulesByType.get("duplicate_pharmacologic_class") ?? []).filter(
      (policy) => {
        if (!policy.applicability.pharmacologicClasses?.includes(group)) return false;
        const anchors = policy.applicability.requiredAnchorIngredientIds ?? [];
        if (!anchors.every((anchor) => ingredientIds.includes(anchor))) return false;
        return uses.every((use) =>
          policyAppliesToProduct(
            policy,
            use.selected.product,
            applicabilityAgeYears,
          ),
        );
      },
    );
    if (policies.length) {
      for (const policy of policies) {
        addFinding(policy, {
          findingId: `duplicate-class:${group}`,
          severity: "high",
          titleKo: `${group} 계열 성분이 겹칩니다`,
          detailKo: `${[...new Set(uses.map((use) => use.ingredient.nameKo))].join(", ")}을(를) 함께 선택했습니다.`,
          nextActionKo: "함께 복용하지 말고 약사 또는 의사와 상담하세요.",
          productIds,
          ingredientIds,
          evidence: uniqueEvidence(
            uses.flatMap((use) => [
              use.ingredient.evidence,
              use.selected.product.evidence,
            ]),
          ),
        });
      }
    } else {
      addCombinationCoverageGap(
        `coverage:combination:${group}:duplicate-class`,
        "duplicate_pharmacologic_class",
        `${group} 계열 성분이 여러 제품에 포함되어 있지만, 이 조합을 판정할 승인 규칙이 없습니다.`,
        productIds,
      );
    }
  }

  for (const item of selected) {
    const product = item.product;
    const constraints = (product.administrationConstraints ?? []).filter((constraint) =>
      isPositiveFinite(constraint.value),
    );
    const maximumPolicies = policiesForProduct("max_daily_dose", product);
    for (const constraint of constraints) {
      if (constraintRuleType(constraint) !== "max_daily_dose") continue;
      if (
        constraint.type === "maximum_units_per_dose" &&
        !hasIssue(product.productId, "unitsPerDose") &&
        item.unitsPerDose > constraint.value
      ) {
        const constraintPolicies = maximumPolicies.filter((policy) =>
          policyMatchesConstraint(policy, constraint.type),
        );
        const finding = {
            findingId: `maximum-units-per-dose:${product.productId}:${constraint.constraintId}`,
            severity: "high",
            titleKo: "확인된 1회 복용량을 초과합니다",
            detailKo: `${product.productName}의 입력값 ${item.unitsPerDose}${product.doseUnitLabel}이 허가 용법의 1회 상한 ${constraint.value}${product.doseUnitLabel}보다 큽니다.`,
            nextActionKo: "추가 복용하지 말고 제품 포장과 허가사항을 확인한 뒤 약사 또는 의사와 상담하세요.",
            productIds: [product.productId],
            ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
            calculatedAmount: item.unitsPerDose,
            referenceAmount: constraint.value,
            unit: product.doseUnitLabel,
            evidence: [constraint.evidence],
          } satisfies Omit<SafetyFinding, "ruleId" | "ruleType" | "decisionBasis">;
        if (constraintPolicies.length) {
          for (const policy of constraintPolicies) addFinding(policy, finding);
        } else if (
          allowsSeparateAdministrationConstraintDecision(
            "OTC-RULE-003",
            product,
            constraint.type,
          )
        ) {
          addConstraintFinding(constraint, finding);
        }
      }
      if (
        constraint.type === "maximum_doses_per_day" &&
        !hasIssue(product.productId, "dosesPerDay") &&
        item.dosesPerDay > constraint.value
      ) {
        const constraintPolicies = maximumPolicies.filter((policy) =>
          policyMatchesConstraint(policy, constraint.type),
        );
        const finding = {
            findingId: `maximum-doses-per-day:${product.productId}:${constraint.constraintId}`,
            severity: "high",
            titleKo: "확인된 하루 복용 횟수를 초과합니다",
            detailKo: `${product.productName}의 입력값 하루 ${item.dosesPerDay}회가 허가 용법의 상한 ${constraint.value}회보다 큽니다.`,
            nextActionKo: "추가 복용하지 말고 제품 포장과 허가사항을 확인한 뒤 약사 또는 의사와 상담하세요.",
            productIds: [product.productId],
            ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
            calculatedAmount: item.dosesPerDay,
            referenceAmount: constraint.value,
            unit: "회/일",
            evidence: [constraint.evidence],
          } satisfies Omit<SafetyFinding, "ruleId" | "ruleType" | "decisionBasis">;
        if (constraintPolicies.length) {
          for (const policy of constraintPolicies) addFinding(policy, finding);
        } else if (
          allowsSeparateAdministrationConstraintDecision(
            "OTC-RULE-003",
            product,
            constraint.type,
          )
        ) {
          addConstraintFinding(constraint, finding);
        }
      }
    }

    if (
      item.hoursSincePreviousDose !== undefined &&
      !hasIssue(product.productId, "hoursSincePreviousDose")
    ) {
      const intervalPolicies = policiesForProduct("minimum_interval", product).filter(
        (policy) => policyMatchesConstraint(policy, "minimum_interval_hours"),
      );
      const intervalConstraints = constraints.filter(
        (constraint) => constraint.type === "minimum_interval_hours",
      );
      const legacyIntervals = product.ingredients
        .filter((ingredient) => ingredient.minimumIntervalHours !== undefined)
        .map((ingredient) => ({
          value: ingredient.minimumIntervalHours as number,
          evidence: ingredient.evidence,
          ingredientId: ingredient.ingredientId,
        }));
      const intervals = intervalConstraints.length
        ? intervalConstraints.map((constraint) => ({
            value: constraint.value,
            evidence: constraint.evidence,
            ingredientId: constraint.ingredientId,
            constraint,
          }))
        : legacyIntervals.map((interval) => ({
            ...interval,
            constraint: undefined,
          }));
      if (intervals.length) {
        const minimumInterval = Math.max(...intervals.map((row) => row.value));
        if (item.hoursSincePreviousDose < minimumInterval) {
          const strictestRows = intervals.filter(
            (row) => row.value === minimumInterval,
          );
          if (intervalConstraints.length && strictestRows.length !== 1) {
            addProductCoverageGap(
              product,
              "minimum_interval",
              "최소 복용 간격의 단일 허가 근거",
              "minimum_interval:ambiguous-source",
            );
          } else {
            const strictest = strictestRows[0];
            const strictestPolicies = intervalPolicies.filter(
              (policy) =>
                !strictest.ingredientId ||
                !policy.applicability.ingredientIds?.length ||
                policy.applicability.ingredientIds.includes(
                  strictest.ingredientId,
                ),
            );
            const finding = {
              findingId: `minimum-interval:${product.productId}:${strictest.constraint?.constraintId ?? strictest.ingredientId}`,
              severity: "high",
              titleKo: "복용 간격이 짧습니다",
              detailKo: `입력 간격 ${item.hoursSincePreviousDose}시간이 확인된 최소 간격 ${minimumInterval}시간보다 짧습니다.`,
              nextActionKo: "다음 복용 시점을 약사 또는 의사에게 확인하세요.",
              productIds: [product.productId],
              ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
              calculatedAmount: item.hoursSincePreviousDose,
              referenceAmount: minimumInterval,
              unit: "시간",
              evidence: [strictest.evidence],
              } satisfies Omit<SafetyFinding, "ruleId" | "ruleType" | "decisionBasis">;
            if (strictestPolicies.length) {
              for (const policy of strictestPolicies) addFinding(policy, finding);
            } else if (
              strictest.constraint &&
              allowsSeparateAdministrationConstraintDecision(
                "OTC-RULE-004",
                product,
                strictest.constraint.type,
              )
            ) {
              addConstraintFinding(strictest.constraint, finding);
            } else {
              addProductCoverageGap(
                product,
                "minimum_interval",
                "최소 복용 간격의 안정적인 ruleId 또는 허가 제약 ID",
                "minimum_interval:unmapped-source",
              );
            }
          }
        }
      }
    }

    if (
      profile.ageYears !== undefined &&
      !inputIssues.some((issue) => issue.field === "ageYears") &&
      product.minimumAgeYears !== undefined &&
      profile.ageYears < product.minimumAgeYears
    ) {
      for (const policy of policiesForProduct("age_restriction", product)) {
        addFinding(policy, {
          findingId: `age:${product.productId}`,
          severity: "high",
          titleKo: "연령 제한을 확인하세요",
          detailKo: `${product.productName}의 확인된 최소 연령 ${product.minimumAgeYears}세보다 입력한 나이가 어립니다.`,
          nextActionKo: "소아용 제품과 용량을 의사 또는 약사에게 확인하세요.",
          productIds: [product.productId],
          ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
          evidence: [product.evidence],
        });
      }
    }

    if (
      item.continuousDays !== undefined &&
      !hasIssue(product.productId, "continuousDays") &&
      product.maximumContinuousDays !== undefined &&
      item.continuousDays > product.maximumContinuousDays
    ) {
      for (const policy of policiesForProduct("maximum_duration", product)) {
        addFinding(policy, {
          findingId: `duration:${product.productId}`,
          severity: "caution",
          titleKo: "연속 복용 기간을 확인하세요",
          detailKo: `입력한 ${item.continuousDays}일이 확인된 기간 ${product.maximumContinuousDays}일을 넘습니다.`,
          nextActionKo: "증상이 지속되면 추가 복용 대신 진료 또는 약사 상담을 받으세요.",
          productIds: [product.productId],
          ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
          evidence: [product.evidence],
        });
      }
    }
  }

  const conditionDefinitions: Array<{
    requested: boolean;
    ruleType: string;
    titleKo: string;
    nextActionKo: string;
    detailKo: (policy: ReleasedRulePolicy) => string;
    policyMatches?: (policy: ReleasedRulePolicy) => boolean;
  }> = [
    {
      requested: Boolean(profile.liverDisease),
      ruleType: "hepatic_disease",
      titleKo: "간질환 관련 주의를 확인하세요",
      nextActionKo: "복용 전 의사 또는 약사와 상담하세요.",
      detailKo: () => "간질환 또는 과거 간질환",
    },
    {
      requested: Boolean(profile.kidneyDisease),
      ruleType: "renal_disease",
      titleKo: "신장질환 관련 주의를 확인하세요",
      nextActionKo: "복용 전 의사 또는 약사와 상담하세요.",
      detailKo: () => "신장질환 또는 과거 신장질환",
    },
    {
      requested: Boolean(profile.giBleedingOrUlcer),
      ruleType: "gi_bleeding_ulcer",
      titleKo: "위장관 출혈·궤양 위험을 확인하세요",
      nextActionKo: "복용 전 의사 또는 약사와 상담하세요.",
      detailKo: () => "위장관 출혈 또는 궤양",
    },
    {
      requested: Boolean(profile.willDrive),
      ruleType: "sedation_driving",
      titleKo: "졸림과 운전 주의를 확인하세요",
      nextActionKo: "운전·기계 조작을 피하고 허가사항을 확인하세요.",
      detailKo: () => "복용 후 운전",
    },
    {
      requested: Boolean(profile.alcohol),
      ruleType: "alcohol",
      titleKo: "정기적인 음주 관련 주의를 확인하세요",
      nextActionKo: "복용 전 약사 또는 의사와 상담하세요.",
      detailKo: () => "매일 3잔 이상 정기적으로 음주",
    },
    {
      requested: Boolean(profile.hypertensionOrCardiovascularDisease),
      ruleType: "decongestant_hypertension",
      titleKo: "비충혈제거제와 혈압 관련 주의를 확인하세요",
      nextActionKo: "복용 전 의사 또는 약사와 상담하세요.",
      detailKo: () => "고혈압 또는 심혈관질환",
    },
    {
      requested: (rulesByType.get("anticoagulant_antiplatelet") ?? []).some(
        (policy) =>
          matchingMedications(profile, policy.applicability.medicationTerms ?? []).length > 0,
      ),
      ruleType: "anticoagulant_antiplatelet",
      titleKo: "항응고제 병용 주의를 확인하세요",
      nextActionKo: "처방한 의료진 또는 약사와 상담하세요.",
      detailKo: (policy) =>
        `복용 중인 약: ${matchingMedications(profile, policy.applicability.medicationTerms ?? []).join(", ")}`,
      policyMatches: (policy) =>
        matchingMedications(
          profile,
          policy.applicability.medicationTerms ?? [],
        ).length > 0,
    },
    {
      requested: (rulesByType.get("sedative_medication") ?? []).some(
        (policy) =>
          matchingMedications(profile, policy.applicability.medicationTerms ?? []).length > 0,
      ),
      ruleType: "sedative_medication",
      titleKo: "진정 작용 약물 병용 주의를 확인하세요",
      nextActionKo: "복용 전 약사 또는 의사와 상담하세요.",
      detailKo: (policy) =>
        `복용 중인 약: ${matchingMedications(profile, policy.applicability.medicationTerms ?? []).join(", ")}`,
      policyMatches: (policy) =>
        matchingMedications(
          profile,
          policy.applicability.medicationTerms ?? [],
        ).length > 0,
    },
  ];

  for (const item of selected) {
    const product = item.product;

    if (profile.pregnant || profile.lactating) {
      const pregnancyPolicies = policiesForProduct("pregnancy_lactation", product);
      let supported = false;
      for (const policy of pregnancyPolicies) {
        const pregnancySupported = Boolean(
          profile.pregnant &&
            profile.pregnancyTrimester !== undefined &&
            policy.applicability.pregnancyTrimesters?.includes(
              profile.pregnancyTrimester,
            ),
        );
        const lactationSupported = Boolean(
          profile.lactating && policy.applicability.lactationSupported,
        );
        if (!pregnancySupported && !lactationSupported) continue;
        supported = true;
        addFinding(policy, {
          findingId: `pregnancy_lactation:${product.productId}`,
          severity: "high",
          titleKo: "임신 중 복용 주의를 확인하세요",
          detailKo: `입력한 조건(임신 ${profile.pregnancyTrimester}기)이 ${product.productName}의 확인된 주의 조건과 일치합니다.`,
          nextActionKo: "복용 전 의사 또는 약사와 상담하세요.",
          productIds: [product.productId],
          ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
          evidence: uniqueEvidence([
            product.evidence,
            ...product.ingredients.map((ingredient) => ingredient.evidence),
          ]),
        });
      }
      const hasUnsupportedPregnancy = Boolean(
        profile.pregnant &&
          (!profile.pregnancyTrimester ||
            !pregnancyPolicies.some((policy) =>
              policy.applicability.pregnancyTrimesters?.includes(
                profile.pregnancyTrimester as 1 | 2 | 3,
              ),
            )),
      );
      const hasUnsupportedLactation = Boolean(
        profile.lactating &&
          !pregnancyPolicies.some((policy) => policy.applicability.lactationSupported),
      );
      if (!supported || hasUnsupportedPregnancy || hasUnsupportedLactation) {
        addProductCoverageGap(
          product,
          "pregnancy_lactation",
          "입력한 임신·수유 상태",
        );
      }
    }

    for (const definition of conditionDefinitions) {
      if (!definition.requested) continue;
      const policies = policiesForProduct(definition.ruleType, product).filter(
        (policy) => definition.policyMatches?.(policy) ?? true,
      );
      if (!policies.length) {
        addProductCoverageGap(product, definition.ruleType, definition.titleKo);
        continue;
      }
      for (const policy of policies) {
        addFinding(policy, {
          findingId: `${definition.ruleType}:${product.productId}`,
          severity: "high",
          titleKo: definition.titleKo,
          detailKo: `입력 조건(${definition.detailKo(policy)})이 ${product.productName}의 확인된 주의 조건과 일치합니다.`,
          nextActionKo: definition.nextActionKo,
          productIds: [product.productId],
          ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
          evidence: uniqueEvidence([
            product.evidence,
            ...product.ingredients.map((ingredient) => ingredient.evidence),
          ]),
        });
      }
    }
  }

  const matchedSymptoms = new Set<string>();
  for (const policy of rulesByType.get("urgent_referral") ?? []) {
    const matchedProducts = selected.filter((item) =>
      policyAppliesToProduct(
        policy,
        item.product,
        applicabilityAgeYears,
      ),
    );
    if (!matchedProducts.length) continue;
    const terms = policy.applicability.urgentTerms ?? [];
    const symptoms = profile.redFlagSymptoms.filter((symptom) =>
      textMatchesTerms(symptom, terms),
    );
    if (!symptoms.length) continue;
    symptoms.forEach((symptom) => matchedSymptoms.add(symptom));
    addFinding(policy, {
      findingId: `urgent:red-flag:${policy.ruleId}`,
      severity: "urgent",
      titleKo: "즉시 상담 또는 진료가 필요할 수 있습니다",
      detailKo: `입력한 증상: ${[...new Set(symptoms)].join(", ")}`,
      nextActionKo: "지체하지 말고 의료기관 또는 응급상담을 이용하세요.",
      productIds: matchedProducts.map((item) => item.product.productId),
      ingredientIds: [
        ...new Set(
          matchedProducts.flatMap((item) =>
            item.product.ingredients.map((ingredient) => ingredient.ingredientId),
          ),
        ),
      ],
      evidence: uniqueEvidence(
        matchedProducts.map((item) => item.product.evidence),
      ),
    });
  }

  const unrecognizedSymptoms = profile.redFlagSymptoms.filter(
    (symptom) => !matchedSymptoms.has(symptom),
  );
  if (unrecognizedSymptoms.length > 0) {
    addCoverageGap({
      gapId: "coverage:profile:unrecognized-symptoms",
      ruleType: "urgent_referral",
      titleKo: "입력한 증상을 분류하지 못했습니다",
      detailKo: `${unrecognizedSymptoms.join(", ")}은(는) 선택한 제품의 검증된 긴급 증상 표현과 일치하지 않습니다. 증상이 심하거나 계속되면 의료기관 또는 약사에게 직접 확인하세요.`,
      productIds: selected.map((item) => item.product.productId),
    });
  }

  const recognizedMedicationTerms = releasedRules.flatMap(
    (policy) => policy.applicability.medicationTerms ?? [],
  );
  const unrecognizedMedications = medicationItems(profile).filter(
    (medication) =>
      !medicationMatchesTerms(medication, recognizedMedicationTerms),
  );
  if (unrecognizedMedications.length > 0) {
    addCoverageGap({
      gapId: "coverage:profile:unrecognized-medications",
      ruleType: "medication_interaction",
      titleKo: "입력한 복용약을 분류하지 못했습니다",
      detailKo: `${unrecognizedMedications.join(", ")}은(는) 현재 복용약 분류에 연결되어 있지 않습니다. 약사 또는 의사에게 직접 확인하세요.`,
      productIds: selected.map((item) => item.product.productId),
    });
  }

  for (const item of selected) {
    const product = item.product;
    const doseConstraints = (product.administrationConstraints ?? []).filter((constraint) =>
      isPositiveFinite(constraint.value),
    );
    const maximumPolicies = policiesForProduct("max_daily_dose", product);
    const hasMaximumUnits = doseConstraints.some(
      (constraint) => constraint.type === "maximum_units_per_dose",
    );
    const hasMaximumFrequency = doseConstraints.some(
      (constraint) => constraint.type === "maximum_doses_per_day",
    );
    const hasMaximumDailyAmount =
      doseConstraints.some(
        (constraint) =>
          constraint.type === "maximum_daily_ingredient_amount" &&
          constraint.ingredientId &&
          product.ingredients.some(
            (ingredient) =>
              ingredient.ingredientId === constraint.ingredientId &&
              ingredient.unit === constraint.valueUnit,
          ),
      ) || product.ingredients.some((ingredient) => ingredient.maxDailyAmount !== undefined);

    const directMaximumSupported = doseConstraints.some(
      (constraint) =>
        constraintRuleType(constraint) === "max_daily_dose" &&
        allowsSeparateAdministrationConstraintDecision(
          "OTC-RULE-003",
          product,
          constraint.type,
        ),
    );
    if (!maximumPolicies.length && !directMaximumSupported) {
      if (!hasIssue(product.productId, "unitsPerDose", "dosesPerDay")) {
        addProductCoverageGap(product, "max_daily_dose", "1회·하루 복용량");
      }
    } else {
      if (!hasIssue(product.productId, "unitsPerDose") && !hasMaximumUnits) {
        addProductCoverageGap(
          product,
          "max_daily_dose",
          "1회 복용량",
          "max_daily_dose:units",
        );
      }
      if (!hasIssue(product.productId, "dosesPerDay") && !hasMaximumFrequency) {
        addProductCoverageGap(
          product,
          "max_daily_dose",
          "하루 복용 횟수",
          "max_daily_dose:frequency",
        );
      }
      if (
        !hasIssue(product.productId, "unitsPerDose", "dosesPerDay") &&
        !hasMaximumDailyAmount &&
        !(hasMaximumUnits && hasMaximumFrequency)
      ) {
        addProductCoverageGap(
          product,
          "max_daily_dose",
          "하루 총복용량",
          "max_daily_dose:total",
        );
      }
    }

    if (
      item.hoursSincePreviousDose !== undefined &&
      !hasIssue(product.productId, "hoursSincePreviousDose")
    ) {
      const hasInterval =
        doseConstraints.some(
          (constraint) => constraint.type === "minimum_interval_hours",
        ) || product.ingredients.some(
          (ingredient) => ingredient.minimumIntervalHours !== undefined,
        );
      const directIntervalSupported = doseConstraints.some(
        (constraint) =>
          constraint.type === "minimum_interval_hours" &&
          allowsSeparateAdministrationConstraintDecision(
            "OTC-RULE-004",
            product,
            constraint.type,
          ),
      );
      if (
        (!policiesForProduct("minimum_interval", product).length &&
          !directIntervalSupported) ||
        !hasInterval
      ) {
        addProductCoverageGap(product, "minimum_interval", "최소 복용 간격");
      }
    }

    if (
      profile.ageYears !== undefined &&
      !inputIssues.some((issue) => issue.field === "ageYears") &&
      (!policiesForProduct("age_restriction", product).length ||
        product.minimumAgeYears === undefined)
    ) {
      addProductCoverageGap(product, "age_restriction", "연령");
    }

    if (
      item.continuousDays !== undefined &&
      !hasIssue(product.productId, "continuousDays") &&
      (!policiesForProduct("maximum_duration", product).length ||
        product.maximumContinuousDays === undefined)
    ) {
      addProductCoverageGap(product, "maximum_duration", "연속 복용 기간");
    }

    if (
      profile.redFlagSymptoms.length > 0 &&
      !policiesForProduct("urgent_referral", product).length
    ) {
      addProductCoverageGap(product, "urgent_referral", "입력 증상");
    }
  }

  const itemSequenceByProductId = new Map(
    selected.map((item) => [item.product.productId, item.product.itemSequence]),
  );
  const policyById = new Map(releasedRules.map((policy) => [policy.ruleId, policy]));
  for (const finding of findings) {
    if (!finding.ruleId) continue;
    const policy = policyById.get(finding.ruleId);
    if (!policy) continue;
    const findingItemSequences = new Set(
      finding.productIds
        .map((productId) => itemSequenceByProductId.get(productId))
        .filter((value): value is string => Boolean(value)),
    );
    const directEvidence = uniqueEvidence(
      policy.evidence.filter((evidence) =>
        findingItemSequences.has(evidence.itemSequence),
      ),
    );
    if (directEvidence.length) finding.ruleEvidence = directEvidence;
  }

  const order = { urgent: 0, high: 1, caution: 2, information: 3 } as const;
  findings.sort(
    (left, right) =>
      order[left.severity] - order[right.severity] ||
      left.findingId.localeCompare(right.findingId),
  );
  coverageGaps.sort((left, right) => left.gapId.localeCompare(right.gapId));

  return {
    findings,
    inputIssues,
    coverageGaps,
    ingredientDailyTotals,
    evaluatedProductIds: selected.map((item) => item.product.productId),
    decisionMode: "deterministic",
  };
}

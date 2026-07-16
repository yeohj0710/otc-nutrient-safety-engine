import type {
  AdministrationConstraint,
  EvaluationCoverageGap,
  EvidenceLink,
  OtcIngredient,
  OtcProduct,
  RuleEvidenceLink,
  SafetyEvaluation,
  SafetyFinding,
  SafetyInputIssue,
  SelectedProduct,
  UserProfile,
  UrgentReferralBinding,
} from "./schema";

const uniqueEvidence = <T extends EvidenceLink>(links: T[]): T[] =>
  [...new Map(links.map((link) => [`${link.sourceId}|${link.locator}`, link])).values()];

const anticoagulantTerms = ["warfarin", "와파린", "apixaban", "아픽사반", "aspirin", "아스피린"];
const sedativeTerms = ["sedative", "진정", "수면"];

const medicationsContain = (profile: UserProfile, terms: string[]) =>
  profile.medications.some((medication) =>
    terms.some((term) => medication.toLowerCase().includes(term)),
  );

const medicationMatchesTerms = (medication: string, terms: string[]) =>
  terms.some((term) => medication.toLowerCase().includes(term));

const matchingMedications = (profile: UserProfile, terms: string[]) =>
  profile.medications.filter((medication) => medicationMatchesTerms(medication, terms));

const symptomMatchesTerms = (symptom: string, terms: string[]) =>
  terms.some(
    (term) => symptom.includes(term) || (symptom.length >= 2 && term.includes(symptom)),
  );

const constraintRuleType = (constraint: AdministrationConstraint) =>
  constraint.type === "minimum_interval_hours" ? "minimum_interval" : "max_daily_dose";

const isPositiveFinite = (value: number) => Number.isFinite(value) && value > 0;

function supportedRuleTypes(
  product: OtcProduct,
  urgentReferralBindings?: UrgentReferralBinding[],
) {
  const supported = new Set(product.supportedRuleTypes ?? []);
  for (const constraint of product.administrationConstraints ?? []) {
    if (isPositiveFinite(constraint.value)) supported.add(constraintRuleType(constraint));
  }
  for (const ingredient of product.ingredients) {
    if (ingredient.maxDailyAmount !== undefined) supported.add("max_daily_dose");
    if (ingredient.minimumIntervalHours !== undefined) supported.add("minimum_interval");
    for (const flag of ingredient.flags) supported.add(flag);
  }
  if (product.minimumAgeYears !== undefined) supported.add("age_restriction");
  if (product.maximumContinuousDays !== undefined) supported.add("maximum_duration");
  for (const flag of product.flags) supported.add(flag);
  if (
    urgentReferralBindings === undefined ||
    urgentReferralBindings.some((binding) => binding.itemSequence === product.itemSequence)
  ) {
    supported.add("urgent_referral");
  }
  return supported;
}

export function evaluateOtcSafety(
  selected: SelectedProduct[],
  profile: UserProfile,
  enabledRuleTypes?: ReadonlySet<string>,
  urgentReferralBindings?: UrgentReferralBinding[],
  ruleEvidenceByType?: Record<string, RuleEvidenceLink[]>,
): SafetyEvaluation {
  const findings: SafetyFinding[] = [];
  const inputIssues: SafetyInputIssue[] = [];
  const issueFields = new Map<string, Set<SafetyInputIssue["field"]>>();

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
      addInputIssue(item.product.productId, "unitsPerDose", `${productName}의 1회 복용량은 0보다 큰 숫자로 입력하세요.`);
    }
    if (!isPositiveFinite(item.dosesPerDay) || !Number.isInteger(item.dosesPerDay)) {
      addInputIssue(item.product.productId, "dosesPerDay", `${productName}의 하루 복용 횟수는 1 이상의 정수로 입력하세요.`);
    }
    if (
      item.hoursSincePreviousDose !== undefined &&
      (!Number.isFinite(item.hoursSincePreviousDose) || item.hoursSincePreviousDose < 0)
    ) {
      addInputIssue(item.product.productId, "hoursSincePreviousDose", `${productName}의 지난 복용 후 시간은 0 이상의 숫자로 입력하세요.`);
    }
    if (
      item.continuousDays !== undefined &&
      (!isPositiveFinite(item.continuousDays) || !Number.isInteger(item.continuousDays))
    ) {
      addInputIssue(item.product.productId, "continuousDays", `${productName}의 연속 복용일은 1 이상의 정수로 입력하세요.`);
    }
  }
  if (
    profile.ageYears !== undefined &&
    (!Number.isFinite(profile.ageYears) || profile.ageYears < 0 || profile.ageYears > 120)
  ) {
    addInputIssue(undefined, "ageYears", "나이는 0세부터 120세 사이의 숫자로 입력하세요.");
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

  const dailyConstraints = selectedForDose.flatMap((item) =>
    (item.product.administrationConstraints ?? [])
      .filter(
        (constraint) =>
          constraint.type === "maximum_daily_ingredient_amount" &&
          constraint.ingredientId &&
          isPositiveFinite(constraint.value),
      )
      .map((constraint) => ({ constraint, product: item.product })),
  );
  const ingredientDailyTotals: Record<string, { amount: number; unit: string }> = {};
  for (const [ingredientId, uses] of ingredientUses) {
    const unit = uses[0].ingredient.unit;
    if (uses.some((use) => use.ingredient.unit !== unit)) continue;
    const amount = uses.reduce((sum, use) => sum + use.daily, 0);
    ingredientDailyTotals[ingredientId] = { amount, unit };
    if (uses.length > 1) {
      findings.push({
        findingId: `duplicate-ingredient:${ingredientId}`,
        ruleType: "duplicate_ingredient",
        severity: "high",
        titleKo: "같은 성분이 여러 제품에 들어 있습니다",
        detailKo: `${uses.map((use) => use.selected.product.productName).join(", ")}에 ${uses[0].ingredient.nameKo}이(가) 겹칩니다. 계산된 하루 총량은 ${amount} ${unit}입니다.`,
        nextActionKo: "추가 복용 전 제품 포장과 허가사항을 확인하고 약사 또는 의사와 상담하세요.",
        productIds: uses.map((use) => use.selected.product.productId),
        ingredientIds: [ingredientId],
        calculatedAmount: amount,
        unit,
        evidence: uniqueEvidence(
          uses.flatMap((use) => [use.ingredient.evidence, use.selected.product.evidence]),
        ),
      });
    }

    const constraints = dailyConstraints.filter(
      ({ constraint }) =>
        constraint.ingredientId === ingredientId && constraint.valueUnit === unit,
    );
    const legacyLimits = uses
      .filter((use) => use.ingredient.maxDailyAmount !== undefined)
      .map((use) => ({
        value: use.ingredient.maxDailyAmount as number,
        evidence: use.ingredient.evidence,
      }));
    const limits = constraints.length
      ? constraints.map(({ constraint }) => ({
          value: constraint.value,
          evidence: constraint.evidence,
        }))
      : legacyLimits;
    if (limits.length) {
      const limit = Math.min(...limits.map((row) => row.value));
      if (amount > limit) {
        findings.push({
          findingId: `max-daily:${ingredientId}`,
          ruleType: "max_daily_dose",
          severity: "high",
          titleKo: "확인된 최대 1일 용량을 초과합니다",
          detailKo: `${uses[0].ingredient.nameKo}의 계산된 하루 총량 ${amount} ${unit}이 기준 ${limit} ${unit}보다 큽니다.`,
          nextActionKo: "추가 복용하지 말고 약사 또는 의사와 상담하세요.",
          productIds: uses.map((use) => use.selected.product.productId),
          ingredientIds: [ingredientId],
          calculatedAmount: amount,
          referenceAmount: limit,
          unit,
          evidence: uniqueEvidence(limits.map((row) => row.evidence)),
        });
      }
    }
  }

  const classUses = new Map<string, Array<{ selected: SelectedProduct; ingredient: OtcIngredient }>>();
  for (const item of selected) {
    for (const ingredient of item.product.ingredients) {
      for (const group of ingredient.pharmacologicClasses) {
        const uses = classUses.get(group) ?? [];
        uses.push({ selected: item, ingredient });
        classUses.set(group, uses);
      }
    }
  }
  for (const duplicateClass of ["NSAID", "antihistamine"]) {
    const classDuplicates = classUses.get(duplicateClass) ?? [];
    if (new Set(classDuplicates.map((use) => use.ingredient.ingredientId)).size <= 1) continue;
    findings.push({
      findingId: `duplicate-class:${duplicateClass}`,
      ruleType: "duplicate_pharmacologic_class",
      severity: "high",
      titleKo: duplicateClass === "NSAID" ? "NSAID 계열 성분이 겹칩니다" : "항히스타민 성분이 겹칩니다",
      detailKo: `${classDuplicates.map((use) => use.ingredient.nameKo).join(", ")}이(가) 함께 선택되었습니다.`,
      nextActionKo: "함께 복용하지 말고 약사 또는 의사와 상담하세요.",
      productIds: [...new Set(classDuplicates.map((use) => use.selected.product.productId))],
      ingredientIds: [...new Set(classDuplicates.map((use) => use.ingredient.ingredientId))],
      evidence: uniqueEvidence(
        classDuplicates.flatMap((use) => [use.ingredient.evidence, use.selected.product.evidence]),
      ),
    });
  }

  for (const item of selected) {
    const product = item.product;
    const constraints = (product.administrationConstraints ?? []).filter((constraint) =>
      isPositiveFinite(constraint.value),
    );
    for (const constraint of constraints) {
      if (
        constraint.type === "maximum_units_per_dose" &&
        !hasIssue(product.productId, "unitsPerDose") &&
        item.unitsPerDose > constraint.value
      ) {
          findings.push({
            findingId: `maximum-units-per-dose:${product.productId}:${constraint.constraintId}`,
            ruleType: "max_daily_dose",
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
          });
      }
      if (
        constraint.type === "maximum_doses_per_day" &&
        !hasIssue(product.productId, "dosesPerDay") &&
        item.dosesPerDay > constraint.value
      ) {
          findings.push({
            findingId: `maximum-doses-per-day:${product.productId}:${constraint.constraintId}`,
            ruleType: "max_daily_dose",
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
          });
      }
    }

    if (
      item.hoursSincePreviousDose !== undefined &&
      !hasIssue(product.productId, "hoursSincePreviousDose")
    ) {
      const intervalConstraints = constraints.filter(
        (constraint) => constraint.type === "minimum_interval_hours",
      );
      if (intervalConstraints.length) {
        const minimumInterval = Math.max(...intervalConstraints.map((constraint) => constraint.value));
        if (item.hoursSincePreviousDose < minimumInterval) {
          findings.push({
            findingId: `minimum-interval:${product.productId}:${intervalConstraints[0].constraintId}`,
            ruleType: "minimum_interval",
            severity: "high",
            titleKo: "복용 간격이 짧습니다",
            detailKo: `입력 간격 ${item.hoursSincePreviousDose}시간이 확인된 최소 간격 ${minimumInterval}시간보다 짧습니다.`,
            nextActionKo: "다음 복용 시점을 약사 또는 의사에게 확인하세요.",
            productIds: [product.productId],
            ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
            calculatedAmount: item.hoursSincePreviousDose,
            referenceAmount: minimumInterval,
            unit: "시간",
            evidence: uniqueEvidence(intervalConstraints.map((constraint) => constraint.evidence)),
          });
        }
      } else {
        for (const ingredient of product.ingredients) {
          if (
            ingredient.minimumIntervalHours !== undefined &&
            item.hoursSincePreviousDose < ingredient.minimumIntervalHours
          ) {
            findings.push({
              findingId: `minimum-interval:${product.productId}:${ingredient.ingredientId}`,
              ruleType: "minimum_interval",
              severity: "high",
              titleKo: "복용 간격이 짧습니다",
              detailKo: `입력 간격 ${item.hoursSincePreviousDose}시간이 확인된 최소 간격 ${ingredient.minimumIntervalHours}시간보다 짧습니다.`,
              nextActionKo: "다음 복용 시점을 약사 또는 의사에게 확인하세요.",
              productIds: [product.productId],
              ingredientIds: [ingredient.ingredientId],
              evidence: [ingredient.evidence],
            });
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
      findings.push({
        findingId: `age:${product.productId}`,
        ruleType: "age_restriction",
        severity: "high",
        titleKo: "연령 제한을 확인하세요",
        detailKo: `${product.productName}은(는) 확인된 최소 연령 ${product.minimumAgeYears}세보다 어린 사용자에게 해당하지 않습니다.`,
        nextActionKo: "소아용 제품과 용량을 의사 또는 약사에게 확인하세요.",
        productIds: [product.productId],
        ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
        evidence: [product.evidence],
      });
    }
    if (
      item.continuousDays !== undefined &&
      !hasIssue(product.productId, "continuousDays") &&
      product.maximumContinuousDays !== undefined &&
      item.continuousDays > product.maximumContinuousDays
    ) {
      findings.push({
        findingId: `duration:${product.productId}`,
        ruleType: "maximum_duration",
        severity: "caution",
        titleKo: "연속 복용 기간을 확인하세요",
        detailKo: `입력한 ${item.continuousDays}일이 확인된 기간 ${product.maximumContinuousDays}일을 넘습니다.`,
        nextActionKo: "증상이 지속되면 추가 복용 대신 진료 또는 약사 상담을 받으세요.",
        productIds: [product.productId],
        ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
        evidence: [product.evidence],
      });
    }

    const flags = new Set([
      ...product.flags,
      ...product.ingredients.flatMap((ingredient) => ingredient.flags),
    ]);
    const pregnancyCondition = profile.pregnant && profile.lactating
      ? "임신 중·수유 중"
      : profile.pregnant
        ? "임신 중"
        : "수유 중";
    const conditional: Array<[boolean, string, string, string, string]> = [
      [Boolean((profile.pregnant || profile.lactating) && flags.has("pregnancy_lactation")), "pregnancy_lactation", "임신·수유 중 주의를 확인하세요", "복용 전 의사 또는 약사와 상담하세요.", pregnancyCondition],
      [Boolean(profile.liverDisease && flags.has("hepatic_disease")), "hepatic_disease", "간질환 관련 주의를 확인하세요", "복용 전 의사 또는 약사와 상담하세요.", "간질환 또는 과거 간질환"],
      [Boolean(profile.kidneyDisease && flags.has("renal_disease")), "renal_disease", "신장질환 관련 주의를 확인하세요", "복용 전 의사 또는 약사와 상담하세요.", "신장질환 또는 과거 신장질환"],
      [Boolean(profile.giBleedingOrUlcer && flags.has("gi_bleeding_ulcer")), "gi_bleeding_ulcer", "위장관 출혈·궤양 위험을 확인하세요", "복용 전 의사 또는 약사와 상담하세요.", "위장관 출혈·궤양"],
      [Boolean(profile.willDrive && flags.has("sedation_driving")), "sedation_driving", "졸림과 운전 주의를 확인하세요", "운전·기계 조작을 피하고 허가사항을 확인하세요.", "복용 후 운전"],
      [Boolean(profile.alcohol && flags.has("alcohol")), "alcohol", "정기적인 음주 관련 주의를 확인하세요", "복용 전 약사 또는 의사와 상담하세요.", "매일 3잔 이상 정기적으로 음주"],
      [Boolean(profile.hypertensionOrCardiovascularDisease && flags.has("decongestant_hypertension")), "decongestant_hypertension", "비충혈제거제와 혈압 관련 주의를 확인하세요", "복용 전 의사 또는 약사와 상담하세요.", "고혈압·심혈관질환"],
      [Boolean(medicationsContain(profile, anticoagulantTerms) && flags.has("anticoagulant_antiplatelet")), "anticoagulant_antiplatelet", "항응고제·항혈소판제 병용 주의를 확인하세요", "처방한 의료진 또는 약사와 상담하세요.", `복용 중인 약: ${matchingMedications(profile, anticoagulantTerms).join(", ")}`],
      [Boolean(medicationsContain(profile, sedativeTerms) && flags.has("sedative_medication")), "sedative_medication", "진정성 약물 병용 주의를 확인하세요", "복용 전 약사 또는 의사와 상담하세요.", `복용 중인 약: ${matchingMedications(profile, sedativeTerms).join(", ")}`],
    ];
    for (const [matches, ruleType, title, action, conditionDetail] of conditional) {
      if (!matches) continue;
      findings.push({
        findingId: `${ruleType}:${product.productId}`,
        ruleType,
        severity: "high",
        titleKo: title,
        detailKo: `입력 조건(${conditionDetail})이 ${product.productName}의 허가상 주의 조건과 일치합니다.`,
        nextActionKo: action,
        productIds: [product.productId],
        ingredientIds: product.ingredients.map((ingredient) => ingredient.ingredientId),
        evidence: uniqueEvidence([
          product.evidence,
          ...product.ingredients.map((ingredient) => ingredient.evidence),
        ]),
      });
    }
  }

  const applicableUrgentBindings = urgentReferralBindings?.filter((binding) =>
    selected.some((item) => item.product.itemSequence === binding.itemSequence),
  );
  const applicableUrgentTerms = applicableUrgentBindings?.flatMap((binding) => binding.terms) ?? [];
  const urgentMatches = urgentReferralBindings
    ? profile.redFlagSymptoms.filter((symptom) =>
        symptomMatchesTerms(symptom, applicableUrgentTerms),
      )
    : profile.redFlagSymptoms;
  if (urgentMatches.length) {
    findings.push({
      findingId: "urgent:red-flag",
      ruleType: "urgent_referral",
      severity: "urgent",
      titleKo: "즉시 상담 또는 진료가 필요할 수 있습니다",
      detailKo: `입력한 증상: ${[...new Set(urgentMatches)].join(", ")}`,
      nextActionKo: "지체하지 말고 의료기관 또는 응급상담을 이용하세요.",
      productIds: selected.map((item) => item.product.productId),
      ingredientIds: [...ingredientUses.keys()],
      evidence: uniqueEvidence(selected.map((item) => item.product.evidence)),
    });
  }

  const coverageGaps: EvaluationCoverageGap[] = [];
  const addCoverageGap = (
    product: OtcProduct,
    ruleType: string,
    checkLabel: string,
    dimension = ruleType,
  ) => {
    const gapId = `coverage:${product.productId}:${dimension}`;
    if (coverageGaps.some((gap) => gap.gapId === gapId)) return;
    coverageGaps.push({
      gapId,
      ruleType,
      titleKo: `${checkLabel} 기준을 확인하지 못했습니다`,
      detailKo: `${product.productName}에 적용할 검증된 ${checkLabel} 기준이 현재 런타임에 연결되지 않았습니다. 제품 포장과 허가사항을 직접 확인하세요.`,
      productIds: [product.productId],
    });
  };
  const conditionalChecks: Array<[boolean | undefined, string, string]> = [
    [profile.pregnant || profile.lactating, "pregnancy_lactation", "임신·수유"],
    [profile.liverDisease, "hepatic_disease", "간질환"],
    [profile.kidneyDisease, "renal_disease", "신장질환"],
    [profile.giBleedingOrUlcer, "gi_bleeding_ulcer", "위장관 출혈·궤양"],
    [profile.willDrive, "sedation_driving", "졸림·운전"],
    [profile.alcohol, "alcohol", "음주 병용"],
    [profile.hypertensionOrCardiovascularDisease, "decongestant_hypertension", "고혈압·심혈관질환"],
    [medicationsContain(profile, anticoagulantTerms), "anticoagulant_antiplatelet", "항응고제·항혈소판제 병용"],
    [medicationsContain(profile, sedativeTerms), "sedative_medication", "진정성 약물 병용"],
  ];
  for (const item of selected) {
    const product = item.product;
    const supported = supportedRuleTypes(product, urgentReferralBindings);
    const isSupported = (ruleType: string) =>
      supported.has(ruleType) && (!enabledRuleTypes || enabledRuleTypes.has(ruleType));
    const doseConstraints = (product.administrationConstraints ?? []).filter((constraint) =>
      isPositiveFinite(constraint.value),
    );
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
    if (!isSupported("max_daily_dose")) {
      if (!hasIssue(product.productId, "unitsPerDose", "dosesPerDay")) {
        addCoverageGap(product, "max_daily_dose", "1회·하루 복용량");
      }
    } else {
      if (!hasIssue(product.productId, "unitsPerDose") && !hasMaximumUnits) {
        addCoverageGap(product, "max_daily_dose", "1회 복용량", "max_daily_dose:units");
      }
      if (!hasIssue(product.productId, "dosesPerDay") && !hasMaximumFrequency) {
        addCoverageGap(product, "max_daily_dose", "하루 복용 횟수", "max_daily_dose:frequency");
      }
      if (
        !hasIssue(product.productId, "unitsPerDose", "dosesPerDay") &&
        !hasMaximumDailyAmount &&
        !(hasMaximumUnits && hasMaximumFrequency)
      ) {
        addCoverageGap(product, "max_daily_dose", "하루 총복용량", "max_daily_dose:total");
      }
    }
    if (
      item.hoursSincePreviousDose !== undefined &&
      !hasIssue(product.productId, "hoursSincePreviousDose") &&
      !isSupported("minimum_interval")
    ) {
      addCoverageGap(product, "minimum_interval", "최소 복용 간격");
    }
    if (
      profile.ageYears !== undefined &&
      !inputIssues.some((issue) => issue.field === "ageYears") &&
      !isSupported("age_restriction")
    ) {
      addCoverageGap(product, "age_restriction", "연령");
    }
    if (
      item.continuousDays !== undefined &&
      !hasIssue(product.productId, "continuousDays") &&
      !isSupported("maximum_duration")
    ) {
      addCoverageGap(product, "maximum_duration", "연속 복용 기간");
    }
    for (const [requested, ruleType, label] of conditionalChecks) {
      if (requested && !isSupported(ruleType)) addCoverageGap(product, ruleType, label);
    }
    if (profile.redFlagSymptoms.length > 0 && !isSupported("urgent_referral")) {
      addCoverageGap(product, "urgent_referral", "입력 증상");
    }
  }
  const unrecognizedMedications = profile.medications.filter(
    (medication) =>
      medication.trim() &&
      !medicationMatchesTerms(medication, anticoagulantTerms) &&
      !medicationMatchesTerms(medication, sedativeTerms),
  );
  if (unrecognizedMedications.length > 0) {
    coverageGaps.push({
      gapId: "coverage:profile:unrecognized-medications",
      ruleType: "medication_interaction",
      titleKo: "입력한 병용약을 분류하지 못했습니다",
      detailKo: `${unrecognizedMedications.join(", ")}은(는) 현재 병용약 분류에 연결되지 않았습니다. 약사 또는 의사에게 직접 확인하세요.`,
      productIds: selected.map((item) => item.product.productId),
    });
  }
  const unrecognizedSymptoms =
    applicableUrgentTerms.length > 0
      ? profile.redFlagSymptoms.filter(
          (symptom) => !symptomMatchesTerms(symptom, applicableUrgentTerms),
        )
      : [];
  if (unrecognizedSymptoms.length > 0) {
    coverageGaps.push({
      gapId: "coverage:profile:unrecognized-symptoms",
      ruleType: "urgent_referral",
      titleKo: "입력한 증상을 분류하지 못했습니다",
      detailKo: `${unrecognizedSymptoms.join(", ")}은(는) 선택한 제품의 검증된 긴급 증상 표현과 일치하지 않습니다. 증상이 심하거나 계속되면 의료기관 또는 약사에게 직접 확인하세요.`,
      productIds: selected.map((item) => item.product.productId),
    });
  }

  const order = { urgent: 0, high: 1, caution: 2, information: 3 } as const;
  const enabledFindings = enabledRuleTypes
    ? findings.filter((finding) => enabledRuleTypes.has(finding.ruleType))
    : findings;
  for (const finding of enabledFindings) {
    const ruleEvidence = uniqueEvidence(ruleEvidenceByType?.[finding.ruleType] ?? []);
    if (ruleEvidence.length > 0) finding.ruleEvidence = ruleEvidence;
  }
  enabledFindings.sort(
    (left, right) =>
      order[left.severity] - order[right.severity] ||
      left.findingId.localeCompare(right.findingId),
  );
  return {
    findings: enabledFindings,
    inputIssues,
    coverageGaps,
    ingredientDailyTotals,
    evaluatedProductIds: selected.map((item) => item.product.productId),
    decisionMode: "deterministic",
  };
}

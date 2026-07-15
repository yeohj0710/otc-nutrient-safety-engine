import type {
  EvidenceLink,
  OtcIngredient,
  SafetyEvaluation,
  SafetyFinding,
  SelectedProduct,
  UserProfile,
  UrgentReferralBinding,
} from "./schema";

const uniqueEvidence = (links: EvidenceLink[]) =>
  [...new Map(links.map((link) => [`${link.sourceId}|${link.locator}`, link])).values()];

const medicationsContain = (profile: UserProfile, terms: string[]) =>
  profile.medications.some((medication) => terms.some((term) => medication.toLowerCase().includes(term)));

export function evaluateOtcSafety(selected: SelectedProduct[], profile: UserProfile, enabledRuleTypes?: ReadonlySet<string>, urgentReferralBindings?: UrgentReferralBinding[]): SafetyEvaluation {
  const findings: SafetyFinding[] = [];
  const ingredientUses = new Map<string, Array<{ selected: SelectedProduct; ingredient: OtcIngredient; daily: number }>>();

  for (const item of selected) {
    for (const ingredient of item.product.ingredients) {
      const daily = ingredient.amountPerUnit * item.unitsPerDose * item.dosesPerDay;
      const uses = ingredientUses.get(ingredient.ingredientId) ?? [];
      uses.push({ selected: item, ingredient, daily });
      ingredientUses.set(ingredient.ingredientId, uses);
    }
  }

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
        evidence: uniqueEvidence(uses.flatMap((use) => [use.ingredient.evidence, use.selected.product.evidence])),
      });
    }
    const limits = uses.map((use) => use.ingredient.maxDailyAmount).filter((value): value is number => value !== undefined);
    if (limits.length) {
      const limit = Math.min(...limits);
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
          evidence: uniqueEvidence(uses.map((use) => use.ingredient.evidence)),
        });
      }
    }
  }

  const classUses = new Map<string, Array<{ selected: SelectedProduct; ingredient: OtcIngredient }>>();
  for (const item of selected) for (const ingredient of item.product.ingredients) for (const group of ingredient.pharmacologicClasses) {
    const uses = classUses.get(group) ?? [];
    uses.push({ selected: item, ingredient });
    classUses.set(group, uses);
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
      evidence: uniqueEvidence(classDuplicates.flatMap((use) => [use.ingredient.evidence, use.selected.product.evidence])),
    });
  }

  for (const item of selected) {
    const product = item.product;
    for (const ingredient of product.ingredients) {
      if (item.hoursSincePreviousDose !== undefined && ingredient.minimumIntervalHours !== undefined && item.hoursSincePreviousDose < ingredient.minimumIntervalHours) {
        findings.push({
          findingId: `minimum-interval:${product.productId}:${ingredient.ingredientId}`,
          ruleType: "minimum_interval",
          severity: "high",
          titleKo: "복용 간격이 짧습니다",
          detailKo: `입력 간격 ${item.hoursSincePreviousDose}시간이 확인된 최소 간격 ${ingredient.minimumIntervalHours}시간보다 짧습니다.`,
          nextActionKo: "다음 복용 시점을 약사 또는 의사에게 확인하세요.",
          productIds: [product.productId], ingredientIds: [ingredient.ingredientId], evidence: [ingredient.evidence],
        });
      }
    }
    if (profile.ageYears !== undefined && product.minimumAgeYears !== undefined && profile.ageYears < product.minimumAgeYears) {
      findings.push({ findingId: `age:${product.productId}`, ruleType: "age_restriction", severity: "high", titleKo: "연령 제한을 확인하세요", detailKo: `${product.productName}은(는) 확인된 최소 연령 ${product.minimumAgeYears}세보다 어린 사용자에게 해당하지 않습니다.`, nextActionKo: "소아용 제품과 용량을 의사 또는 약사에게 확인하세요.", productIds: [product.productId], ingredientIds: product.ingredients.map((x) => x.ingredientId), evidence: [product.evidence] });
    }
    if (item.continuousDays !== undefined && product.maximumContinuousDays !== undefined && item.continuousDays > product.maximumContinuousDays) {
      findings.push({ findingId: `duration:${product.productId}`, ruleType: "maximum_duration", severity: "caution", titleKo: "연속 복용 기간을 확인하세요", detailKo: `입력한 ${item.continuousDays}일이 확인된 기간 ${product.maximumContinuousDays}일을 넘습니다.`, nextActionKo: "증상이 지속되면 추가 복용 대신 진료 또는 약사 상담을 받으세요.", productIds: [product.productId], ingredientIds: product.ingredients.map((x) => x.ingredientId), evidence: [product.evidence] });
    }
    const flags = new Set([...product.flags, ...product.ingredients.flatMap((ingredient) => ingredient.flags)]);
    const conditional: Array<[boolean, string, string, string]> = [
      [Boolean((profile.pregnant || profile.lactating) && flags.has("pregnancy_lactation")), "pregnancy_lactation", "임신·수유 중 주의를 확인하세요", "복용 전 의사 또는 약사와 상담하세요."],
      [Boolean(profile.liverDisease && flags.has("hepatic_disease")), "hepatic_disease", "간질환 관련 주의를 확인하세요", "복용 전 의사 또는 약사와 상담하세요."],
      [Boolean(profile.kidneyDisease && flags.has("renal_disease")), "renal_disease", "신장질환 관련 주의를 확인하세요", "복용 전 의사 또는 약사와 상담하세요."],
      [Boolean(profile.giBleedingOrUlcer && flags.has("gi_bleeding_ulcer")), "gi_bleeding_ulcer", "위장관 출혈·궤양 위험을 확인하세요", "복용 전 의사 또는 약사와 상담하세요."],
      [Boolean(profile.willDrive && flags.has("sedation_driving")), "sedation_driving", "졸림과 운전 주의를 확인하세요", "운전·기계 조작을 피하고 허가사항을 확인하세요."],
      [Boolean(profile.alcohol && flags.has("alcohol")), "alcohol", "음주 병용 주의를 확인하세요", "음주 중 복용 전 약사 또는 의사와 상담하세요."],
      [Boolean(profile.hypertensionOrCardiovascularDisease && flags.has("decongestant_hypertension")), "decongestant_hypertension", "비충혈제거제와 혈압 관련 주의를 확인하세요", "복용 전 의사 또는 약사와 상담하세요."],
      [Boolean(medicationsContain(profile, ["warfarin", "와파린", "apixaban", "아픽사반", "aspirin", "아스피린"]) && flags.has("anticoagulant_antiplatelet")), "anticoagulant_antiplatelet", "항응고제·항혈소판제 병용 주의를 확인하세요", "처방한 의료진 또는 약사와 상담하세요."],
      [Boolean(medicationsContain(profile, ["sedative", "진정", "수면"]) && flags.has("sedative_medication")), "sedative_medication", "진정성 약물 병용 주의를 확인하세요", "복용 전 약사 또는 의사와 상담하세요."],
    ];
    for (const [matches, ruleType, title, action] of conditional) if (matches) {
      findings.push({ findingId: `${ruleType}:${product.productId}`, ruleType, severity: "high", titleKo: title, detailKo: `${product.productName}의 허가상 주의 조건과 입력 정보가 겹칩니다.`, nextActionKo: action, productIds: [product.productId], ingredientIds: product.ingredients.map((x) => x.ingredientId), evidence: uniqueEvidence([product.evidence, ...product.ingredients.map((x) => x.evidence)]) });
    }
  }
  const urgentMatches = urgentReferralBindings
    ? urgentReferralBindings.flatMap((binding) => selected.some((item) => item.product.itemSequence === binding.itemSequence)
      ? profile.redFlagSymptoms.filter((symptom) => binding.terms.some((term) => symptom.includes(term) || (symptom.length >= 2 && term.includes(symptom))))
      : [])
    : profile.redFlagSymptoms;
  if (urgentMatches.length) findings.push({ findingId: "urgent:red-flag", ruleType: "urgent_referral", severity: "urgent", titleKo: "즉시 상담 또는 진료가 필요할 수 있습니다", detailKo: `입력한 증상: ${[...new Set(urgentMatches)].join(", ")}`, nextActionKo: "지체하지 말고 의료기관 또는 응급상담을 이용하세요.", productIds: selected.map((x) => x.product.productId), ingredientIds: [...ingredientUses.keys()], evidence: uniqueEvidence(selected.map((x) => x.product.evidence)) });

  const order = { urgent: 0, high: 1, caution: 2, information: 3 } as const;
  const enabledFindings = enabledRuleTypes ? findings.filter((finding) => enabledRuleTypes.has(finding.ruleType)) : findings;
  enabledFindings.sort((a, b) => order[a.severity] - order[b.severity] || a.findingId.localeCompare(b.findingId));
  return { findings: enabledFindings, ingredientDailyTotals, evaluatedProductIds: selected.map((x) => x.product.productId), decisionMode: "deterministic" };
}

import { describe, expect, it } from "vitest";

import runtimeJson from "@/src/generated/otc-runtime.json";
import { evaluateOtcSafety } from "@/src/lib/otc/engine";
import type {
  AdministrationConstraint,
  EvidenceLink,
  OtcIngredient,
  OtcProduct,
  ReleasedRulePolicy,
  SelectedProduct,
  UserProfile,
} from "@/src/lib/otc/schema";

type RuntimeFixture = {
  products: OtcProduct[];
  releasedRules: ReleasedRulePolicy[];
};

const runtime = runtimeJson as unknown as RuntimeFixture;
const options = { releasedRules: runtime.releasedRules };

const profile = (overrides: Partial<UserProfile> = {}): UserProfile => ({
  medications: [],
  redFlagSymptoms: [],
  ...overrides,
});

const selected = (
  itemSequence: string,
  overrides: Partial<Omit<SelectedProduct, "product">> = {},
): SelectedProduct => {
  const product = runtime.products.find((candidate) => candidate.itemSequence === itemSequence);
  if (!product) throw new Error(`missing test product: ${itemSequence}`);
  return { product, unitsPerDose: 1, dosesPerDay: 1, ...overrides };
};

const findingTypes = (result: ReturnType<typeof evaluateOtcSafety>) =>
  result.findings.map((finding) => finding.ruleType);

const gapTypes = (result: ReturnType<typeof evaluateOtcSafety>) =>
  result.coverageGaps.map((gap) => gap.ruleType);

const ruleIds = (result: ReturnType<typeof evaluateOtcSafety>) =>
  result.findings.map((finding) => finding.ruleId);

const releasedRule = (ruleId: string) => {
  const policy = runtime.releasedRules.find((candidate) => candidate.ruleId === ruleId);
  if (!policy) throw new Error(`missing released policy: ${ruleId}`);
  return policy;
};

type RuleInput = {
  selections: Array<{
    itemSequence: string;
    overrides?: Partial<Omit<SelectedProduct, "product">>;
  }>;
  profile?: Partial<UserProfile>;
};

type ReleasedRuleExecutionCase = {
  ruleId: string;
  positive: RuleInput;
  negatives: Array<RuleInput & { label: string }>;
};

const releasedRuleExecutionCases: ReleasedRuleExecutionCase[] = [
  {
    ruleId: "OTC-RULE-001",
    positive: {
      selections: [
        { itemSequence: "202106092" },
        { itemSequence: "202200525" },
      ],
    },
    negatives: [
      {
        label: "one acetaminophen product",
        selections: [{ itemSequence: "202106092" }],
      },
      {
        label: "duplicate ingredient outside the released ingredient scope",
        selections: [
          { itemSequence: "198700405" },
          { itemSequence: "200300406" },
        ],
      },
    ],
  },
  {
    ruleId: "OTC-RULE-002",
    positive: {
      selections: [
        { itemSequence: "198601920" },
        { itemSequence: "197500016" },
      ],
    },
    negatives: [
      {
        label: "one NSAID product",
        selections: [{ itemSequence: "198601920" }],
      },
      {
        label: "NSAID combination without the ibuprofen anchor",
        selections: [
          { itemSequence: "201110646" },
          { itemSequence: "197500016" },
        ],
      },
    ],
  },
  {
    ruleId: "OTC-RULE-003",
    positive: {
      selections: [
        {
          itemSequence: "202106092",
          overrides: { unitsPerDose: 2, dosesPerDay: 5 },
        },
      ],
      profile: { ageYears: 12 },
    },
    negatives: [
      {
        label: "exact 4,000 mg daily boundary",
        selections: [
          {
            itemSequence: "202106092",
            overrides: { unitsPerDose: 2, dosesPerDay: 4 },
          },
        ],
        profile: { ageYears: 12 },
      },
      {
        label: "below the released age boundary",
        selections: [
          {
            itemSequence: "202106092",
            overrides: { unitsPerDose: 2, dosesPerDay: 5 },
          },
        ],
        profile: { ageYears: 11 },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-004",
    positive: {
      selections: [
        {
          itemSequence: "202106092",
          overrides: { hoursSincePreviousDose: 3.5 },
        },
      ],
      profile: { ageYears: 12 },
    },
    negatives: [
      {
        label: "exact four-hour interval boundary",
        selections: [
          {
            itemSequence: "202106092",
            overrides: { hoursSincePreviousDose: 4 },
          },
        ],
        profile: { ageYears: 12 },
      },
      {
        label: "below the released age boundary",
        selections: [
          {
            itemSequence: "202106092",
            overrides: { hoursSincePreviousDose: 3.5 },
          },
        ],
        profile: { ageYears: 11 },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-005",
    positive: {
      selections: [{ itemSequence: "202106092" }],
      profile: { ageYears: 11 },
    },
    negatives: [
      {
        label: "exact minimum-age boundary",
        selections: [{ itemSequence: "202106092" }],
        profile: { ageYears: 12 },
      },
      {
        label: "younger user with a different acetaminophen product",
        selections: [{ itemSequence: "202200525" }],
        profile: { ageYears: 11 },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-006",
    positive: {
      selections: [{ itemSequence: "198601920" }],
      profile: { pregnant: true, pregnancyTrimester: 3 },
    },
    negatives: [
      {
        label: "second-trimester boundary",
        selections: [{ itemSequence: "198601920" }],
        profile: { pregnant: true, pregnancyTrimester: 2 },
      },
      {
        label: "third trimester with a different NSAID",
        selections: [{ itemSequence: "197500016" }],
        profile: { pregnant: true, pregnancyTrimester: 3 },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-007",
    positive: {
      selections: [{ itemSequence: "202106092" }],
      profile: { liverDisease: true },
    },
    negatives: [
      {
        label: "condition not selected",
        selections: [{ itemSequence: "202106092" }],
      },
      {
        label: "liver disease with a different acetaminophen product",
        selections: [{ itemSequence: "202200525" }],
        profile: { liverDisease: true },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-008",
    positive: {
      selections: [{ itemSequence: "198601920" }],
      profile: { kidneyDisease: true },
    },
    negatives: [
      {
        label: "condition not selected",
        selections: [{ itemSequence: "198601920" }],
      },
      {
        label: "kidney disease with a different NSAID",
        selections: [{ itemSequence: "197500016" }],
        profile: { kidneyDisease: true },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-009",
    positive: {
      selections: [{ itemSequence: "198601920" }],
      profile: { giBleedingOrUlcer: true },
    },
    negatives: [
      {
        label: "condition not selected",
        selections: [{ itemSequence: "198601920" }],
      },
      {
        label: "GI history with a different NSAID",
        selections: [{ itemSequence: "197500016" }],
        profile: { giBleedingOrUlcer: true },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-010",
    positive: {
      selections: [{ itemSequence: "196800036" }],
      profile: { willDrive: true },
    },
    negatives: [
      {
        label: "driving not selected",
        selections: [{ itemSequence: "196800036" }],
      },
      {
        label: "driving with a different cold medicine",
        selections: [{ itemSequence: "199400202" }],
        profile: { willDrive: true },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-011",
    positive: {
      selections: [{ itemSequence: "202106092" }],
      profile: { alcohol: true },
    },
    negatives: [
      {
        label: "alcohol condition not selected",
        selections: [{ itemSequence: "202106092" }],
      },
      {
        label: "alcohol use with a different acetaminophen product",
        selections: [{ itemSequence: "196800036" }],
        profile: { alcohol: true },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-012",
    positive: {
      selections: [{ itemSequence: "198601920" }],
      profile: { medications: ["와파린"] },
    },
    negatives: [
      {
        label: "unreleased medication term",
        selections: [{ itemSequence: "198601920" }],
        profile: { medications: ["아스피린"] },
      },
      {
        label: "warfarin with a different NSAID",
        selections: [{ itemSequence: "197500016" }],
        profile: { medications: ["와파린"] },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-013",
    positive: {
      selections: [{ itemSequence: "196800036" }],
      profile: { medications: ["수면제"] },
    },
    negatives: [
      {
        label: "non-sedating medication wording",
        selections: [{ itemSequence: "196800036" }],
        profile: { medications: ["비진정성 항히스타민제"] },
      },
      {
        label: "sedative with a different cold medicine",
        selections: [{ itemSequence: "199400202" }],
        profile: { medications: ["수면제"] },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-014",
    positive: {
      selections: [{ itemSequence: "196800036" }],
      profile: { hypertensionOrCardiovascularDisease: true },
    },
    negatives: [
      {
        label: "condition not selected",
        selections: [{ itemSequence: "196800036" }],
      },
      {
        label: "hypertension with a different cold medicine",
        selections: [{ itemSequence: "199400202" }],
        profile: { hypertensionOrCardiovascularDisease: true },
      },
    ],
  },
  {
    ruleId: "OTC-RULE-016",
    positive: {
      selections: [{ itemSequence: "202106092" }],
      profile: { redFlagSymptoms: ["호흡곤란"] },
    },
    negatives: [
      {
        label: "partial urgent-term fragment",
        selections: [{ itemSequence: "202106092" }],
        profile: { redFlagSymptoms: ["호흡"] },
      },
      {
        label: "urgent term with a different product",
        selections: [{ itemSequence: "196800036" }],
        profile: { redFlagSymptoms: ["호흡곤란"] },
      },
    ],
  },
];

const evaluateRuleInput = (input: RuleInput) =>
  evaluateOtcSafety(
    input.selections.map(({ itemSequence, overrides }) =>
      selected(itemSequence, overrides),
    ),
    profile(input.profile),
    options,
  );

type AdministrationConstraintCase = {
  constraintId: string;
  product: OtcProduct;
  constraint: AdministrationConstraint;
};

const administrationConstraintCases: AdministrationConstraintCase[] =
  runtime.products.flatMap((product) =>
    (product.administrationConstraints ?? []).map((constraint) => ({
      constraintId: constraint.constraintId,
      product,
      constraint,
    })),
  );

const selectedForConstraint = (
  product: OtcProduct,
  constraint: AdministrationConstraint,
  violates: boolean,
): SelectedProduct => {
  const item: SelectedProduct = {
    product,
    unitsPerDose: 1,
    dosesPerDay: 1,
  };
  switch (constraint.type) {
    case "maximum_units_per_dose":
      item.unitsPerDose = constraint.value + (violates ? 1 : 0);
      break;
    case "maximum_doses_per_day":
      item.dosesPerDay = constraint.value + (violates ? 1 : 0);
      break;
    case "maximum_daily_ingredient_amount": {
      const ingredient = product.ingredients.find(
        (candidate) => candidate.ingredientId === constraint.ingredientId,
      );
      if (!ingredient) {
        throw new Error(`${constraint.constraintId} has no matching ingredient`);
      }
      item.unitsPerDose =
        (constraint.value + (violates ? 1 : 0)) / ingredient.amountPerUnit;
      break;
    }
    case "minimum_interval_hours":
      item.hoursSincePreviousDose = constraint.value - (violates ? 0.5 : 0);
      break;
  }
  return item;
};

const findingForConstraint = (
  result: ReturnType<typeof evaluateOtcSafety>,
  product: OtcProduct,
  constraint: AdministrationConstraint,
) => {
  if (constraint.type === "maximum_daily_ingredient_amount") {
    return result.findings.find(
      (finding) =>
        finding.findingId ===
        `max-daily:${product.productId}:${constraint.constraintId}`,
    );
  }
  const prefix =
    constraint.type === "minimum_interval_hours"
      ? "minimum-interval"
      : constraint.type === "maximum_units_per_dose"
        ? "maximum-units-per-dose"
        : "maximum-doses-per-day";
  return result.findings.find(
    (finding) =>
      finding.findingId ===
      `${prefix}:${product.productId}:${constraint.constraintId}`,
  );
};

const expectedDecisionForConstraint = (
  product: OtcProduct,
  constraint: AdministrationConstraint,
) => {
  if (
    product.itemSequence === "202106092" &&
    constraint.type === "maximum_daily_ingredient_amount"
  ) {
    return { ruleId: "OTC-RULE-003", decisionBasis: "released_rule" as const };
  }
  if (
    product.itemSequence === "202106092" &&
    constraint.type === "minimum_interval_hours"
  ) {
    return { ruleId: "OTC-RULE-004", decisionBasis: "released_rule" as const };
  }
  return {
    ruleId: constraint.constraintId,
    decisionBasis: "administration_constraint" as const,
  };
};

describe("v5.1 released-rule execution matrix", () => {
  it("covers each of the 15 released rule IDs exactly once", () => {
    expect(releasedRuleExecutionCases.map(({ ruleId }) => ruleId).sort()).toEqual(
      runtime.releasedRules.map(({ ruleId }) => ruleId).sort(),
    );
  });

  it.each(releasedRuleExecutionCases)(
    "$ruleId emits its exact released identity and pinned evidence",
    ({ ruleId, positive }) => {
      const result = evaluateRuleInput(positive);
      const finding = result.findings.find(
        (candidate) => candidate.ruleId === ruleId,
      );
      const policy = releasedRule(ruleId);

      expect(finding).toEqual(
        expect.objectContaining({
          ruleId,
          ruleType: policy.ruleType,
          decisionBasis: "released_rule",
        }),
      );
      expect(finding?.ruleEvidence).toEqual(policy.evidence);
      expect(
        finding?.ruleEvidence?.every(({ sourceVersion }) =>
          sourceVersion?.startsWith("sha256:"),
        ),
      ).toBe(true);
    },
  );

  it.each(releasedRuleExecutionCases)(
    "$ruleId stays absent at every pinned negative or boundary case",
    ({ ruleId, negatives }) => {
      for (const negative of negatives) {
        const result = evaluateRuleInput(negative);
        expect(
          result.findings.filter((finding) => finding.ruleId === ruleId),
          negative.label,
        ).toEqual([]);
      }
    },
  );
});

describe("v5.1 rule applicability gate", () => {
  it("maps all 15 released policies by ruleId without claiming a new expert review", () => {
    expect(runtime.releasedRules).toHaveLength(15);
    expect(new Set(runtime.releasedRules.map((rule) => rule.ruleId)).size).toBe(15);
    expect(runtime.releasedRules.every((rule) => rule.lineageStatus === "mapped_from_v50_released_rule")).toBe(true);
    expect(JSON.stringify(runtime.releasedRules)).not.toContain("human_expert_verified");
  });

  it("fails closed when an otherwise executable policy has empty applicability", () => {
    const malformed: ReleasedRulePolicy = {
      ...releasedRule("OTC-RULE-007"),
      applicability: {},
    };
    const result = evaluateOtcSafety(
      [selected("197500016")],
      profile({ liverDisease: true }),
      { releasedRules: [malformed] },
    );
    expect(ruleIds(result)).not.toContain("OTC-RULE-007");
    expect(gapTypes(result)).toContain("hepatic_disease");
  });

  it("fails closed when duplicate ruleIds carry conflicting applicability", () => {
    const original = releasedRule("OTC-RULE-007");
    const conflicting: ReleasedRulePolicy = {
      ...original,
      scope: "conflicting_naproxen_scope",
      applicability: { productItemSequences: ["197500016"] },
    };
    const result = evaluateOtcSafety(
      [selected("197500016")],
      profile({ liverDisease: true }),
      { releasedRules: [original, conflicting] },
    );
    expect(ruleIds(result)).not.toContain("OTC-RULE-007");
    expect(gapTypes(result)).toContain("hepatic_disease");
  });

  it("rejects every duplicate ruleId occurrence when one copy has empty applicability", () => {
    const original = releasedRule("OTC-RULE-007");
    const empty: ReleasedRulePolicy = {
      ...original,
      applicability: {},
    };
    const result = evaluateOtcSafety(
      [selected("197500016")],
      profile({ liverDisease: true }),
      { releasedRules: [original, empty] },
    );
    expect(ruleIds(result)).not.toContain("OTC-RULE-007");
    expect(gapTypes(result)).toContain("hepatic_disease");
  });

  it("rejects every duplicate ruleId occurrence when one copy has malformed evidence", () => {
    const original = releasedRule("OTC-RULE-007");
    const malformed: ReleasedRulePolicy = {
      ...original,
      evidence: original.evidence.map((evidence) => ({
        ...evidence,
        ruleId: "OTC-RULE-999",
      })),
    };
    const result = evaluateOtcSafety(
      [selected("197500016")],
      profile({ liverDisease: true }),
      { releasedRules: [original, malformed] },
    );
    expect(ruleIds(result)).not.toContain("OTC-RULE-007");
    expect(gapTypes(result)).toContain("hepatic_disease");
  });

  it("applies Rule001 only to duplicate acetaminophen and reports unsupported overlaps as gaps", () => {
    const supported = evaluateOtcSafety(
      [selected("202106092"), selected("202200525")],
      profile(),
      options,
    );
    expect(supported.findings).toContainEqual(
      expect.objectContaining({
        ruleId: "OTC-RULE-001",
        ruleType: "duplicate_ingredient",
        ingredientIds: ["ING-acetaminophen"],
      }),
    );

    const digestive = evaluateOtcSafety(
      [selected("198700405"), selected("200300406")],
      profile(),
      options,
    );
    expect(findingTypes(digestive)).not.toContain("duplicate_ingredient");
    expect(gapTypes(digestive)).toContain("duplicate_ingredient");

    const singleProduct = evaluateOtcSafety(
      [selected("202106092")],
      profile(),
      options,
    );
    expect(ruleIds(singleProduct)).not.toContain("OTC-RULE-001");
  });

  it("requires an ibuprofen anchor for Rule002 and rejects antihistamine scope leakage", () => {
    const supported = evaluateOtcSafety(
      [selected("198601920"), selected("197500016")],
      profile(),
      options,
    );
    expect(supported.findings).toContainEqual(
      expect.objectContaining({
        ruleId: "OTC-RULE-002",
        ruleType: "duplicate_pharmacologic_class",
      }),
    );

    const noAnchor = evaluateOtcSafety(
      [selected("201110646"), selected("197500016")],
      profile(),
      options,
    );
    expect(findingTypes(noAnchor)).not.toContain("duplicate_pharmacologic_class");
    expect(gapTypes(noAnchor)).toContain("duplicate_pharmacologic_class");

    const antihistamines = evaluateOtcSafety(
      [selected("196800036"), selected("200610765")],
      profile(),
      options,
    );
    expect(findingTypes(antihistamines)).not.toContain("duplicate_pharmacologic_class");
    expect(gapTypes(antihistamines)).toContain("duplicate_pharmacologic_class");

    const singleNsaid = evaluateOtcSafety(
      [selected("198601920")],
      profile(),
      options,
    );
    expect(ruleIds(singleNsaid)).not.toContain("OTC-RULE-002");
  });

  it("limits Rule012 to warfarin and coumarin terms", () => {
    for (const medication of [
      "warfarin",
      "와파린",
      "coumarin",
      "쿠마린",
      "쿠마린계 항응고제",
    ]) {
      const supported = evaluateOtcSafety(
        [selected("198601920")],
        profile({ medications: [medication] }),
        options,
      );
      expect(supported.findings).toContainEqual(
        expect.objectContaining({
          ruleId: "OTC-RULE-012",
          ruleType: "anticoagulant_antiplatelet",
        }),
      );
    }

    for (const medication of ["아스피린", "아픽사반"]) {
      const unsupported = evaluateOtcSafety(
        [selected("198601920")],
        profile({ medications: [medication] }),
        options,
      );
      expect(findingTypes(unsupported)).not.toContain("anticoagulant_antiplatelet");
      expect(unsupported.coverageGaps).toContainEqual(
        expect.objectContaining({ gapId: "coverage:profile:unrecognized-medications" }),
      );
    }

    const nonTarget = evaluateOtcSafety(
      [selected("202106092")],
      profile({ medications: ["와파린"] }),
      options,
    );
    expect(ruleIds(nonTarget)).not.toContain("OTC-RULE-012");
  });

  it("limits Rule013 to explicit sedative medication categories", () => {
    for (const medication of ["sedative", "진정제", "수면제"]) {
      const supported = evaluateOtcSafety(
        [selected("196800036")],
        profile({ medications: [medication] }),
        options,
      );
      expect(supported.findings).toContainEqual(
        expect.objectContaining({
          ruleId: "OTC-RULE-013",
          ruleType: "sedative_medication",
        }),
      );
    }

    for (const medication of [
      "non-sedative",
      "비진정제",
      "비진정성 항히스타민제",
      "수면 상태 개선",
    ]) {
      const unsupported = evaluateOtcSafety(
        [selected("196800036")],
        profile({ medications: [medication] }),
        options,
      );
      expect(findingTypes(unsupported)).not.toContain("sedative_medication");
      expect(unsupported.coverageGaps).toContainEqual(
        expect.objectContaining({
          gapId: "coverage:profile:unrecognized-medications",
        }),
      );
    }

    const nonTarget = evaluateOtcSafety(
      [selected("199400202")],
      profile({ medications: ["진정제"] }),
      options,
    );
    expect(ruleIds(nonTarget)).not.toContain("OTC-RULE-013");
  });

  it("uses exact comma-item medication matching and preserves mixed coverage gaps", () => {
    const combined = evaluateOtcSafety(
      [selected("196800036")],
      profile({ medications: ["진정제, 비진정제"] }),
      options,
    );
    expect(ruleIds(combined)).toContain("OTC-RULE-013");
    expect(combined.findings.find((finding) => finding.ruleId === "OTC-RULE-013")?.detailKo)
      .toContain("진정제");
    expect(combined.coverageGaps).toContainEqual(
      expect.objectContaining({
        gapId: "coverage:profile:unrecognized-medications",
        detailKo: expect.stringContaining("비진정제"),
      }),
    );

    const mixed = evaluateOtcSafety(
      [selected("198601920")],
      profile({ medications: ["warfarin", "아픽사반"] }),
      options,
    );
    expect(ruleIds(mixed)).toContain("OTC-RULE-012");
    expect(mixed.coverageGaps).toContainEqual(
      expect.objectContaining({
        gapId: "coverage:profile:unrecognized-medications",
        detailKo: expect.stringContaining("아픽사반"),
      }),
    );
  });

  it("limits Rule006 to pregnancy trimester 3 and reports every unsupported state", () => {
    const trimester3 = evaluateOtcSafety(
      [selected("198601920")],
      profile({ pregnant: true, pregnancyTrimester: 3 }),
      options,
    );
    expect(trimester3.findings).toContainEqual(
      expect.objectContaining({
        ruleId: "OTC-RULE-006",
        ruleType: "pregnancy_lactation",
      }),
    );

    for (const values of [
      { pregnant: true },
      { pregnant: true, pregnancyTrimester: 1 as const },
      { pregnant: true, pregnancyTrimester: 2 as const },
      { lactating: true },
    ]) {
      const unsupported = evaluateOtcSafety(
        [selected("198601920")],
        profile(values),
        options,
      );
      expect(findingTypes(unsupported)).not.toContain("pregnancy_lactation");
      expect(gapTypes(unsupported)).toContain("pregnancy_lactation");
    }

    const nonTarget = evaluateOtcSafety(
      [selected("202106092")],
      profile({ pregnant: true, pregnancyTrimester: 3 }),
      options,
    );
    expect(ruleIds(nonTarget)).not.toContain("OTC-RULE-006");

    const pregnancyAndLactation = evaluateOtcSafety(
      [selected("198601920")],
      profile({ pregnant: true, pregnancyTrimester: 3, lactating: true }),
      options,
    );
    expect(ruleIds(pregnancyAndLactation)).toContain("OTC-RULE-006");
    expect(gapTypes(pregnancyAndLactation)).toContain("pregnancy_lactation");
  });

  it("normalizes spaces and hyphens for urgent terms without reverse-substring false positives", () => {
    const matched = evaluateOtcSafety(
      [selected("202106092"), selected("198700405")],
      profile({ redFlagSymptoms: ["얼굴 부기"] }),
      options,
    );
    expect(matched.findings).toContainEqual(
      expect.objectContaining({
        ruleId: "OTC-RULE-016",
        ruleType: "urgent_referral",
        productIds: ["MFDS-202106092"],
      }),
    );

    for (const symptom of ["천식", "발작"]) {
      const falsePositive = evaluateOtcSafety(
        [selected("202106092")],
        profile({ redFlagSymptoms: [symptom] }),
        options,
      );
      expect(findingTypes(falsePositive)).not.toContain("urgent_referral");
      expect(falsePositive.coverageGaps).toContainEqual(
        expect.objectContaining({ gapId: "coverage:profile:unrecognized-symptoms" }),
      );
    }
  });

  it("preserves a recognized urgent finding and an unrecognized symptom in one evaluation", () => {
    const result = evaluateOtcSafety(
      [selected("202106092")],
      profile({ redFlagSymptoms: ["얼굴 부기", "심한 어지럼"] }),
      options,
    );
    expect(ruleIds(result)).toContain("OTC-RULE-016");
    expect(result.coverageGaps).toContainEqual(
      expect.objectContaining({
        gapId: "coverage:profile:unrecognized-symptoms",
        detailKo: expect.stringContaining("심한 어지럼"),
      }),
    );
  });

  it.each(releasedRule("OTC-RULE-016").applicability.urgentTerms ?? [])(
    "maps urgent term %s to Rule016 only when Tylenol 500 is selected",
    (urgentTerm) => {
      const target = evaluateOtcSafety(
        [selected("202106092")],
        profile({ redFlagSymptoms: [urgentTerm] }),
        options,
      );
      expect(ruleIds(target)).toContain("OTC-RULE-016");

      const nonTarget = evaluateOtcSafety(
        [selected("198700405")],
        profile({ redFlagSymptoms: [urgentTerm] }),
        options,
      );
      expect(ruleIds(nonTarget)).not.toContain("OTC-RULE-016");
      expect(nonTarget.coverageGaps).toContainEqual(
        expect.objectContaining({
          gapId: "coverage:profile:unrecognized-symptoms",
        }),
      );
    },
  );

  it("fires Rule003 only above the Tylenol daily boundary for age 12 or older", () => {
    const boundary = evaluateOtcSafety(
      [selected("202106092", { unitsPerDose: 2, dosesPerDay: 4 })],
      profile({ ageYears: 12 }),
      options,
    );
    expect(ruleIds(boundary)).not.toContain("OTC-RULE-003");

    const violation = evaluateOtcSafety(
      [selected("202106092", { unitsPerDose: 2, dosesPerDay: 5 })],
      profile({ ageYears: 12 }),
      options,
    );
    expect(violation.findings).toContainEqual(
      expect.objectContaining({
        ruleId: "OTC-RULE-003",
        ruleType: "max_daily_dose",
        decisionBasis: "released_rule",
      }),
    );

    const underAge = evaluateOtcSafety(
      [selected("202106092", { unitsPerDose: 2, dosesPerDay: 5 })],
      profile({ ageYears: 11 }),
      options,
    );
    expect(ruleIds(underAge)).not.toContain("OTC-RULE-003");
    expect(ruleIds(underAge)).not.toContain("ADMIN-202106092-MAX-DAILY-ING-acetaminophen");
  });

  it("keeps Rule003 scoped to Tylenol intake when another selected product contains acetaminophen", () => {
    const withinEachProduct = evaluateOtcSafety(
      [
        selected("202106092", { unitsPerDose: 1.75, dosesPerDay: 4 }),
        selected("196800036", { unitsPerDose: 1, dosesPerDay: 2 }),
      ],
      profile({ ageYears: 12 }),
      options,
    );
    expect(ruleIds(withinEachProduct)).toContain("OTC-RULE-001");
    expect(ruleIds(withinEachProduct)).not.toContain("OTC-RULE-003");
    expect(ruleIds(withinEachProduct)).not.toContain(
      "ADMIN-202106092-MAX-DAILY-ING-acetaminophen",
    );
    expect(withinEachProduct.ingredientDailyTotals["ING-acetaminophen"]).toEqual({
      amount: 4100,
      unit: "mg",
    });

    const tylenolOnlyViolation = evaluateOtcSafety(
      [selected("202106092", { unitsPerDose: 2, dosesPerDay: 5 })],
      profile({ ageYears: 12 }),
      options,
    );
    expect(tylenolOnlyViolation.findings).toContainEqual(
      expect.objectContaining({
        findingId:
          "max-daily:MFDS-202106092:ADMIN-202106092-MAX-DAILY-ING-acetaminophen",
        ruleId: "OTC-RULE-003",
        productIds: ["MFDS-202106092"],
        ingredientIds: ["ING-acetaminophen"],
        calculatedAmount: 5000,
        referenceAmount: 4000,
      }),
    );
  });

  it("fires Rule004 only below the Tylenol interval boundary for age 12 or older", () => {
    const boundary = evaluateOtcSafety(
      [selected("202106092", { hoursSincePreviousDose: 4 })],
      profile({ ageYears: 12 }),
      options,
    );
    expect(ruleIds(boundary)).not.toContain("OTC-RULE-004");

    const violation = evaluateOtcSafety(
      [selected("202106092", { hoursSincePreviousDose: 3.5 })],
      profile({ ageYears: 12 }),
      options,
    );
    expect(violation.findings).toContainEqual(
      expect.objectContaining({
        ruleId: "OTC-RULE-004",
        ruleType: "minimum_interval",
        decisionBasis: "released_rule",
      }),
    );

    const nonTarget = evaluateOtcSafety(
      [selected("202200525", { hoursSincePreviousDose: 3.5 })],
      profile({ ageYears: 12 }),
      options,
    );
    expect(ruleIds(nonTarget)).not.toContain("OTC-RULE-004");
    expect(ruleIds(nonTarget)).toContain("ADMIN-202200525-MIN-INTERVAL");
  });

  it("fires Rule005 below age 12 only for Tylenol 500", () => {
    const below = evaluateOtcSafety(
      [selected("202106092")],
      profile({ ageYears: 11 }),
      options,
    );
    expect(ruleIds(below)).toContain("OTC-RULE-005");

    const boundary = evaluateOtcSafety(
      [selected("202106092")],
      profile({ ageYears: 12 }),
      options,
    );
    expect(ruleIds(boundary)).not.toContain("OTC-RULE-005");

    const nonTarget = evaluateOtcSafety(
      [selected("202200525")],
      profile({ ageYears: 11 }),
      options,
    );
    expect(ruleIds(nonTarget)).not.toContain("OTC-RULE-005");
  });

  it.each([
    {
      ruleId: "OTC-RULE-007",
      ruleType: "hepatic_disease",
      targetItem: "202106092",
      nonTargetItem: "202200525",
      profilePatch: { liverDisease: true },
    },
    {
      ruleId: "OTC-RULE-008",
      ruleType: "renal_disease",
      targetItem: "198601920",
      nonTargetItem: "197500016",
      profilePatch: { kidneyDisease: true },
    },
    {
      ruleId: "OTC-RULE-009",
      ruleType: "gi_bleeding_ulcer",
      targetItem: "198601920",
      nonTargetItem: "197500016",
      profilePatch: { giBleedingOrUlcer: true },
    },
    {
      ruleId: "OTC-RULE-010",
      ruleType: "sedation_driving",
      targetItem: "196800036",
      nonTargetItem: "199400202",
      profilePatch: { willDrive: true },
    },
    {
      ruleId: "OTC-RULE-011",
      ruleType: "alcohol",
      targetItem: "202106092",
      nonTargetItem: "196800036",
      profilePatch: { alcohol: true },
    },
    {
      ruleId: "OTC-RULE-014",
      ruleType: "decongestant_hypertension",
      targetItem: "196800036",
      nonTargetItem: "199400202",
      profilePatch: { hypertensionOrCardiovascularDisease: true },
    },
  ])(
    "$ruleId fires only for its target product and affirmative condition",
    ({ ruleId, ruleType, targetItem, nonTargetItem, profilePatch }) => {
      const positive = evaluateOtcSafety(
        [selected(targetItem)],
        profile(profilePatch),
        options,
      );
      expect(positive.findings).toContainEqual(
        expect.objectContaining({
          ruleId,
          ruleType,
          decisionBasis: "released_rule",
        }),
      );

      const normal = evaluateOtcSafety(
        [selected(targetItem)],
        profile(),
        options,
      );
      expect(ruleIds(normal)).not.toContain(ruleId);

      const nonTarget = evaluateOtcSafety(
        [selected(nonTargetItem)],
        profile(profilePatch),
        options,
      );
      expect(ruleIds(nonTarget)).not.toContain(ruleId);
    },
  );

  it("separates released Rule003/004 decisions from other products' direct constraints", () => {
    const naproxenProduct = selected("197500016").product;
    const naproxenConstraint = naproxenProduct.administrationConstraints?.find(
      (constraint) => constraint.constraintId === "ADMIN-197500016-MAX-DOSES",
    );
    expect(naproxenConstraint).toBeDefined();
    const naproxen = evaluateOtcSafety(
      [selected("197500016", { dosesPerDay: 5 })],
      profile(),
      options,
    );
    const naproxenFinding = naproxen.findings.find(
      (finding) => finding.findingId === "maximum-doses-per-day:MFDS-197500016:ADMIN-197500016-MAX-DOSES",
    );
    expect(naproxenFinding).toEqual(
      expect.objectContaining({
        ruleId: "ADMIN-197500016-MAX-DOSES",
        decisionBasis: "administration_constraint",
        evidence: [naproxenConstraint!.evidence],
      }),
    );
    expect(naproxenFinding?.ruleEvidence).toBeUndefined();

    const childInterval = evaluateOtcSafety(
      [selected("202200525", { hoursSincePreviousDose: 3 })],
      profile(),
      options,
    ).findings.find((finding) => finding.ruleType === "minimum_interval");
    expect(childInterval).toEqual(
      expect.objectContaining({
        ruleId: "ADMIN-202200525-MIN-INTERVAL",
        decisionBasis: "administration_constraint",
      }),
    );
    expect(childInterval?.ruleEvidence).toBeUndefined();

    const adult = evaluateOtcSafety(
      [
        selected("202106092", {
          unitsPerDose: 2,
          dosesPerDay: 5,
          hoursSincePreviousDose: 3,
        }),
      ],
      profile({ ageYears: 35 }),
      options,
    );
    expect(adult.findings).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          ruleId: "OTC-RULE-003",
          decisionBasis: "released_rule",
          ruleEvidence: [expect.objectContaining({ ruleId: "OTC-RULE-003" })],
        }),
        expect.objectContaining({
          ruleId: "OTC-RULE-004",
          decisionBasis: "released_rule",
          ruleEvidence: [expect.objectContaining({ ruleId: "OTC-RULE-004" })],
        }),
      ]),
    );
    const administrationFinding = adult.findings.find(
      (finding) => finding.ruleId === "ADMIN-202106092-MAX-DOSES",
    );
    expect(administrationFinding).toEqual(
      expect.objectContaining({
        ruleId: "ADMIN-202106092-MAX-DOSES",
        decisionBasis: "administration_constraint",
      }),
    );
    expect(administrationFinding).not.toHaveProperty("ruleEvidence");

    const adultPerDose = evaluateOtcSafety(
      [selected("202106092", { unitsPerDose: 3 })],
      profile({ ageYears: 35 }),
      options,
    ).findings.find(
      (finding) => finding.findingId.includes("maximum-units-per-dose"),
    );
    expect(adultPerDose).toEqual(
      expect.objectContaining({
        ruleId: "ADMIN-202106092-MAX-UNITS",
        decisionBasis: "administration_constraint",
      }),
    );
    expect(adultPerDose?.ruleEvidence).toBeUndefined();

    const adultAgeUnknown = evaluateOtcSafety(
      [
        selected("202106092", {
          unitsPerDose: 2,
          dosesPerDay: 5,
          hoursSincePreviousDose: 3,
        }),
      ],
      profile(),
      options,
    );
    expect(adultAgeUnknown.findings.map((finding) => finding.ruleId)).not.toContain(
      "OTC-RULE-003",
    );
    expect(adultAgeUnknown.findings.map((finding) => finding.ruleId)).not.toContain(
      "OTC-RULE-004",
    );
    expect(adultAgeUnknown.findings.map((finding) => finding.ruleId)).not.toContain(
      "ADMIN-202106092-MAX-DOSES",
    );
    expect(adultAgeUnknown.coverageGaps.map((gap) => gap.ruleType)).toEqual(
      expect.arrayContaining(["max_daily_dose", "minimum_interval"]),
    );
  });

  it("fails closed when policy input is omitted", () => {
    const result = evaluateOtcSafety(
      [selected("202106092"), selected("202200525")],
      profile({ redFlagSymptoms: ["얼굴 부기"] }),
    );
    expect(result.findings).toEqual([]);
    expect(gapTypes(result)).toEqual(
      expect.arrayContaining(["duplicate_ingredient", "urgent_referral"]),
    );
  });

  it("keeps evidence links with distinct URLs and reports ingredient unit conflicts", () => {
    const link = (url: string): EvidenceLink => ({
      sourceId: "MFDS-NEDRUG-DETAIL",
      locator: "같은 locator",
      url,
    });
    const ingredient = (unit: OtcIngredient["unit"], url: string): OtcIngredient => ({
      ingredientId: "ING-acetaminophen",
      nameKo: "아세트아미노펜",
      amountPerUnit: 100,
      unit,
      pharmacologicClasses: ["analgesic_antipyretic"],
      flags: [],
      evidence: link(url),
    });
    const product = (id: string, unit: OtcIngredient["unit"], url: string): OtcProduct => ({
      productId: id,
      itemSequence: id,
      productName: id,
      classification: "일반의약품",
      authorizationStatus: "active",
      doseUnitLabel: "정",
      ingredients: [ingredient(unit, url)],
      flags: [],
      evidence: link(url),
    });

    const distinctUrls = evaluateOtcSafety(
      [
        { product: product("P1", "mg", "https://example.test/one"), unitsPerDose: 1, dosesPerDay: 1 },
        { product: product("P2", "mg", "https://example.test/two"), unitsPerDose: 1, dosesPerDay: 1 },
      ],
      profile(),
      options,
    );
    const duplicate = distinctUrls.findings.find(
      (finding) => finding.ruleType === "duplicate_ingredient",
    );
    expect(new Set(duplicate?.evidence.map((row) => row.url))).toEqual(
      new Set(["https://example.test/one", "https://example.test/two"]),
    );

    const mismatchedUnits = evaluateOtcSafety(
      [
        { product: product("P1", "mg", "https://example.test/one"), unitsPerDose: 1, dosesPerDay: 1 },
        { product: product("P2", "g", "https://example.test/two"), unitsPerDose: 1, dosesPerDay: 1 },
      ],
      profile(),
      options,
    );
    expect(findingTypes(mismatchedUnits)).not.toContain("duplicate_ingredient");
    expect(mismatchedUnits.coverageGaps).toContainEqual(
      expect.objectContaining({
        gapId: "coverage:combination:ING-acetaminophen:unit-mismatch",
        ruleType: "duplicate_ingredient",
      }),
    );
  });

  it("does not attach Rule001 evidence from a product outside the finding", () => {
    const result = evaluateOtcSafety(
      [selected("202200525"), selected("196800036")],
      profile(),
      options,
    );
    const duplicate = result.findings.find(
      (finding) => finding.ruleId === "OTC-RULE-001",
    );
    expect(duplicate).toBeDefined();
    expect(duplicate?.ruleEvidence).toBeUndefined();
  });
});

describe("v5.1 administration constraint execution matrix", () => {
  it("covers all 32 constraints and all four executable subtypes", () => {
    expect(administrationConstraintCases).toHaveLength(32);
    expect(
      Object.fromEntries(
        [
          "maximum_units_per_dose",
          "maximum_doses_per_day",
          "maximum_daily_ingredient_amount",
          "minimum_interval_hours",
        ].map((type) => [
          type,
          administrationConstraintCases.filter(
            ({ constraint }) => constraint.type === type,
          ).length,
        ]),
      ),
    ).toEqual({
      maximum_units_per_dose: 12,
      maximum_doses_per_day: 13,
      maximum_daily_ingredient_amount: 5,
      minimum_interval_hours: 2,
    });
  });

  it.each(administrationConstraintCases)(
    "$constraintId keeps the exact boundary normal and emits the pinned violation decision",
    ({ product, constraint }) => {
      const boundary = evaluateOtcSafety(
        [selectedForConstraint(product, constraint, false)],
        profile({ ageYears: 12 }),
        options,
      );
      expect(findingForConstraint(boundary, product, constraint)).toBeUndefined();

      const violation = evaluateOtcSafety(
        [selectedForConstraint(product, constraint, true)],
        profile({ ageYears: 12 }),
        options,
      );
      const finding = findingForConstraint(violation, product, constraint);
      const expected = expectedDecisionForConstraint(product, constraint);
      expect(finding).toEqual(
        expect.objectContaining({
          ruleId: expected.ruleId,
          decisionBasis: expected.decisionBasis,
          evidence: [constraint.evidence],
        }),
      );
      expect(finding?.evidence[0].sourceVersion).toBe(
        constraint.evidence.sourceVersion,
      );
      if (expected.decisionBasis === "administration_constraint") {
        expect(finding).not.toHaveProperty("ruleEvidence");
      } else {
        expect(finding?.ruleEvidence).toEqual(releasedRule(expected.ruleId).evidence);
      }
    },
  );

  it.each(
    administrationConstraintCases.filter(
      ({ constraint }) => constraint.type === "maximum_daily_ingredient_amount",
    ),
  )(
    "$constraintId ignores the same ingredient amount from another product",
    ({ product, constraint }) => {
      if (!constraint.ingredientId) throw new Error("missing ingredientId");
      const ingredient = product.ingredients.find(
        (candidate) => candidate.ingredientId === constraint.ingredientId,
      );
      if (!ingredient) throw new Error("missing constrained ingredient");
      const otherProduct: OtcProduct = {
        ...product,
        productId: `TEST-OTHER-${product.productId}`,
        itemSequence: `TEST-OTHER-${product.itemSequence}`,
        productName: `다른 ${product.productName}`,
        administrationConstraints: [],
        ingredients: [{ ...ingredient, amountPerUnit: 1, maxDailyAmount: undefined }],
      };
      const result = evaluateOtcSafety(
        [
          selectedForConstraint(product, constraint, false),
          {
            product: otherProduct,
            unitsPerDose: 1,
            dosesPerDay: 1,
          },
        ],
        profile({ ageYears: 12 }),
        options,
      );
      expect(findingForConstraint(result, product, constraint)).toBeUndefined();
      expect(result.ingredientDailyTotals[constraint.ingredientId]).toEqual({
        amount: constraint.value + 1,
        unit: constraint.valueUnit,
      });
    },
  );

  it.each([undefined, 11])(
    "does not fall back to Tylenol ADMIN decisions when age is %s",
    (ageYears) => {
      const tylenol = selected("202106092").product;
      for (const constraint of tylenol.administrationConstraints ?? []) {
        const result = evaluateOtcSafety(
          [selectedForConstraint(tylenol, constraint, true)],
          profile({ ageYears }),
          options,
        );
        expect(findingForConstraint(result, tylenol, constraint)).toBeUndefined();
        expect(ruleIds(result)).not.toContain("OTC-RULE-003");
        expect(ruleIds(result)).not.toContain("OTC-RULE-004");
        expect(ruleIds(result)).not.toContain(constraint.constraintId);
      }
    },
  );

  it("executes every non-Tylenol daily ingredient maximum with its ADMIN identity", () => {
    const cases = administrationConstraintCases.filter(
      ({ product, constraint }) =>
        product.itemSequence !== "202106092" &&
        constraint.type === "maximum_daily_ingredient_amount",
    );
    expect(cases.map(({ constraintId }) => constraintId)).toEqual([
      "ADMIN-201110646-MAX-DAILY-ING-dexibuprofen",
      "ADMIN-197500016-MAX-DAILY-ING-naproxen",
      "ADMIN-200610765-MAX-DAILY-ING-cetirizine_hydrochloride",
      "ADMIN-198601920-MAX-DAILY-ING-ibuprofen",
    ]);
    for (const { product, constraint } of cases) {
      const result = evaluateOtcSafety(
        [selectedForConstraint(product, constraint, true)],
        profile({ ageYears: 12 }),
        options,
      );
      expect(findingForConstraint(result, product, constraint)).toEqual(
        expect.objectContaining({
          ruleId: constraint.constraintId,
          decisionBasis: "administration_constraint",
          evidence: [constraint.evidence],
        }),
      );
    }
  });
});

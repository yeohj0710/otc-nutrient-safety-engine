import { describe, expect, it } from "vitest";

import { evaluateOtcSafety } from "@/src/lib/otc/engine";
import type {
  EvidenceLink,
  OtcIngredient,
  OtcProduct,
  ReleasedRulePolicy,
  RuleApplicability,
  UserProfile,
} from "@/src/lib/otc/schema";

const evidence: EvidenceLink = {
  sourceId: "TEST-SOURCE",
  locator: "검증용 원문 위치",
  url: "https://example.test/source",
};

const ingredient = (
  ingredientId: string,
  nameKo: string,
  classes: string[] = [],
): OtcIngredient => ({
  ingredientId,
  nameKo,
  amountPerUnit: 100,
  unit: "mg",
  pharmacologicClasses: classes,
  flags: [],
  evidence,
});

const product = (
  productId: string,
  ingredients: OtcIngredient[],
): OtcProduct => ({
  productId,
  itemSequence: productId,
  productName: `검증제품-${productId}`,
  classification: "일반의약품",
  authorizationStatus: "active",
  doseUnitLabel: "정",
  ingredients,
  flags: [],
  evidence,
});

const profile = (values: Partial<UserProfile> = {}): UserProfile => ({
  medications: [],
  redFlagSymptoms: [],
  ...values,
});

const policy = (
  ruleId: string,
  ruleType: string,
  applicability: RuleApplicability,
  itemSequence = "P1",
): ReleasedRulePolicy => ({
  ruleId,
  ruleType,
  scope: `test:${ruleId}`,
  lineageStatus: "mapped_from_v50_released_rule",
  applicability,
  evidence: [
    {
      ...evidence,
      sourceVersion: "sha256:test-rule-source",
      ruleId,
      productName: `검증제품-${itemSequence}`,
      itemSequence,
      excerptKo: "검증된 규칙 원문입니다.",
    },
  ],
});

describe("deterministic OTC safety engine", () => {
  it("calculates normal daily totals without inventing a finding", () => {
    const p = product("P1", [ingredient("ING-test", "검증성분")]);
    const result = evaluateOtcSafety(
      [{ product: p, unitsPerDose: 1, dosesPerDay: 2 }],
      profile(),
      { releasedRules: [policy("OTC-RULE-003", "max_daily_dose", {})] },
    );

    expect(result.ingredientDailyTotals["ING-test"]).toEqual({ amount: 200, unit: "mg" });
    expect(result.findings).toEqual([]);
    expect(result.decisionMode).toBe("deterministic");
  });

  it("uses direct authorization constraints for maximum dose and interval findings", () => {
    const p = {
      ...product("P1", [ingredient("ING-test", "검증성분")]),
      administrationConstraints: [
        {
          constraintId: "P1-max-units",
          type: "maximum_units_per_dose",
          value: 2,
          valueUnit: "정/회",
          evidence,
        },
        {
          constraintId: "P1-max-doses",
          type: "maximum_doses_per_day",
          value: 3,
          valueUnit: "회/일",
          evidence,
        },
        {
          constraintId: "P1-interval",
          type: "minimum_interval_hours",
          value: 6,
          valueUnit: "시간",
          evidence,
        },
      ],
    } as OtcProduct;
    const result = evaluateOtcSafety(
      [
        {
          product: p,
          unitsPerDose: 3,
          dosesPerDay: 4,
          hoursSincePreviousDose: 5,
        },
      ],
      profile(),
      {
        releasedRules: [
          policy("OTC-RULE-003", "max_daily_dose", {
            productItemSequences: ["P1"],
            administrationConstraintTypes: [
              "maximum_units_per_dose",
              "maximum_doses_per_day",
            ],
          }),
          policy("OTC-RULE-004", "minimum_interval", {
            productItemSequences: ["P1"],
            administrationConstraintTypes: ["minimum_interval_hours"],
          }),
        ],
      },
    );

    expect(result.findings).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          findingId: "maximum-units-per-dose:P1:P1-max-units",
          ruleId: "OTC-RULE-003",
        }),
        expect.objectContaining({
          findingId: "maximum-doses-per-day:P1:P1-max-doses",
          ruleId: "OTC-RULE-003",
        }),
        expect.objectContaining({
          findingId: "minimum-interval:P1:P1-interval",
          ruleId: "OTC-RULE-004",
          referenceAmount: 6,
        }),
      ]),
    );
  });

  it("rejects invalid numeric input before dose calculation", () => {
    const p = product("P1", [ingredient("ING-test", "검증성분")]);
    for (const [unitsPerDose, dosesPerDay] of [
      [0, 1],
      [-1, 1],
      [Number.POSITIVE_INFINITY, 1],
      [1, 0],
      [1, 1.5],
      [1, Number.NaN],
    ]) {
      const result = evaluateOtcSafety(
        [{ product: p, unitsPerDose, dosesPerDay }],
        profile(),
        { releasedRules: [policy("OTC-RULE-003", "max_daily_dose", {})] },
      );
      expect(result.inputIssues.length).toBeGreaterThan(0);
      expect(result.ingredientDailyTotals).toEqual({});
    }
  });

  it("supports multiple released rules with the same type and keeps their IDs separate", () => {
    const ingredientA = ingredient("ING-a", "성분A");
    const ingredientB = ingredient("ING-b", "성분B");
    const result = evaluateOtcSafety(
      [
        { product: product("P1", [ingredientA]), unitsPerDose: 1, dosesPerDay: 1 },
        { product: product("P2", [ingredientA]), unitsPerDose: 1, dosesPerDay: 1 },
        { product: product("P3", [ingredientB]), unitsPerDose: 1, dosesPerDay: 1 },
        { product: product("P4", [ingredientB]), unitsPerDose: 1, dosesPerDay: 1 },
      ],
      profile(),
      {
        releasedRules: [
          policy("RULE-A", "duplicate_ingredient", { ingredientIds: ["ING-a"] }),
          policy("RULE-B", "duplicate_ingredient", { ingredientIds: ["ING-b"] }),
        ],
      },
    );

    expect(new Set(result.findings.map((finding) => finding.ruleId))).toEqual(
      new Set(["RULE-A", "RULE-B"]),
    );
  });

  it("emits only the same-type medication policy whose terms matched", () => {
    const p = product("P1", [ingredient("ING-test", "검증성분")]);
    const warfarin = policy(
      "RULE-WARFARIN",
      "anticoagulant_antiplatelet",
      { productItemSequences: ["P1"], medicationTerms: ["warfarin", "와파린"] },
    );
    const heparin = policy(
      "RULE-HEPARIN",
      "anticoagulant_antiplatelet",
      { productItemSequences: ["P1"], medicationTerms: ["heparin", "헤파린"] },
    );
    const result = evaluateOtcSafety(
      [{ product: p, unitsPerDose: 1, dosesPerDay: 1 }],
      profile({ medications: ["와파린"] }),
      { releasedRules: [warfarin, heparin] },
    );

    expect(result.findings.map((finding) => finding.ruleId)).toEqual([
      "RULE-WARFARIN",
    ]);
    expect(result.findings[0].detailKo).toContain("와파린");

    const unsupportedStrengthText = evaluateOtcSafety(
      [{ product: p, unitsPerDose: 1, dosesPerDay: 1 }],
      profile({ medications: ["와파린 2mg"] }),
      { releasedRules: [warfarin, heparin] },
    );
    expect(unsupportedStrengthText.findings).toEqual([]);
    expect(unsupportedStrengthText.coverageGaps).toContainEqual(
      expect.objectContaining({
        gapId: "coverage:profile:unrecognized-medications",
      }),
    );
  });

  it("isolates same-type maximum policies by administration constraint subtype", () => {
    const p = {
      ...product("P1", [ingredient("ING-test", "검증성분")]),
      administrationConstraints: [
        {
          constraintId: "U",
          type: "maximum_units_per_dose",
          value: 1,
          valueUnit: "정/회",
          evidence,
        },
        {
          constraintId: "D",
          type: "maximum_doses_per_day",
          value: 3,
          valueUnit: "회/일",
          evidence,
        },
      ],
    } as OtcProduct;
    const result = evaluateOtcSafety(
      [{ product: p, unitsPerDose: 2, dosesPerDay: 1 }],
      profile(),
      {
        releasedRules: [
          policy("RULE-UNITS", "max_daily_dose", {
            productItemSequences: ["P1"],
            administrationConstraintTypes: ["maximum_units_per_dose"],
          }),
          policy("RULE-DOSES", "max_daily_dose", {
            productItemSequences: ["P1"],
            administrationConstraintTypes: ["maximum_doses_per_day"],
          }),
        ],
      },
    );

    expect(result.findings.map((finding) => finding.ruleId)).toEqual([
      "RULE-UNITS",
    ]);
  });

  it("fails closed instead of throwing when policy evidence is malformed", () => {
    const p = product("P1", [ingredient("ING-test", "검증성분")]);
    const malformed = {
      ...policy("OTC-RULE-003", "max_daily_dose", {}),
      evidence: { ruleId: "OTC-RULE-003" },
    };

    expect(() =>
      evaluateOtcSafety(
        [{ product: p, unitsPerDose: 1, dosesPerDay: 1 }],
        profile(),
        { releasedRules: [malformed] } as never,
      ),
    ).not.toThrow();
    const result = evaluateOtcSafety(
      [{ product: p, unitsPerDose: 1, dosesPerDay: 1 }],
      profile(),
      { releasedRules: [malformed] } as never,
    );
    expect(result.findings).toEqual([]);
    expect(result.coverageGaps).toContainEqual(
      expect.objectContaining({ ruleType: "max_daily_dose" }),
    );
  });

  it("fails closed instead of throwing when applicability fields are malformed", () => {
    const p = product("P1", [ingredient("ING-test", "검증성분")]);
    const malformed = {
      ...policy("OTC-RULE-016", "urgent_referral", {
        productItemSequences: ["P1"],
        urgentTerms: ["호흡곤란"],
      }),
      applicability: {
        productItemSequences: ["P1"],
        urgentTerms: [42],
      },
    };

    expect(() =>
      evaluateOtcSafety(
        [{ product: p, unitsPerDose: 1, dosesPerDay: 1 }],
        profile({ redFlagSymptoms: ["호흡곤란"] }),
        { releasedRules: [malformed] } as never,
      ),
    ).not.toThrow();
    const result = evaluateOtcSafety(
      [{ product: p, unitsPerDose: 1, dosesPerDay: 1 }],
      profile({ redFlagSymptoms: ["호흡곤란"] }),
      { releasedRules: [malformed] } as never,
    );
    expect(result.findings).toEqual([]);
    expect(result.coverageGaps).toContainEqual(
      expect.objectContaining({ ruleType: "urgent_referral" }),
    );
  });

  it("does not compare a combined amount against separate product constraints", () => {
    const same = ingredient("ING-test", "검증성분");
    const constrainedProduct = (productId: string): OtcProduct => ({
      ...product(productId, [same]),
      administrationConstraints: [
        {
          constraintId: `ADMIN-${productId}-MAX-DAILY`,
          type: "maximum_daily_ingredient_amount",
          value: 300,
          valueUnit: "mg",
          ingredientId: "ING-test",
          evidence: { ...evidence, url: `https://example.test/${productId}` },
        },
      ],
    });
    const result = evaluateOtcSafety(
      [
        { product: constrainedProduct("P1"), unitsPerDose: 1, dosesPerDay: 2 },
        { product: constrainedProduct("P2"), unitsPerDose: 1, dosesPerDay: 2 },
      ],
      profile(),
      {
        releasedRules: [
          policy("OTC-RULE-003", "max_daily_dose", {
            productItemSequences: ["P1"],
            administrationConstraintTypes: ["maximum_daily_ingredient_amount"],
          }),
        ],
      },
    );

    expect(result.findings.map((finding) => finding.ruleType)).not.toContain(
      "max_daily_dose",
    );
    expect(result.coverageGaps.map((gap) => gap.gapId)).not.toContain(
      "coverage:combination:ING-test:ambiguous-maximum-source",
    );
  });

  it("emits every applicable released maximum rule with its own ruleId", () => {
    const p = {
      ...product("P1", [ingredient("ING-test", "검증성분")]),
      administrationConstraints: [
        {
          constraintId: "ADMIN-P1-MAX-DAILY",
          type: "maximum_daily_ingredient_amount",
          value: 300,
          valueUnit: "mg",
          ingredientId: "ING-test",
          evidence,
        },
      ],
    } as OtcProduct;
    const applicability: RuleApplicability = {
      productItemSequences: ["P1"],
      ingredientIds: ["ING-test"],
      administrationConstraintTypes: ["maximum_daily_ingredient_amount"],
    };
    const result = evaluateOtcSafety(
      [{ product: p, unitsPerDose: 2, dosesPerDay: 2 }],
      profile(),
      {
        releasedRules: [
          policy("RULE-MAX-A", "max_daily_dose", applicability),
          policy("RULE-MAX-B", "max_daily_dose", applicability),
        ],
      },
    );

    expect(result.findings.map((finding) => finding.ruleId)).toEqual([
      "RULE-MAX-A",
      "RULE-MAX-B",
    ]);
    expect(result.coverageGaps.map((gap) => gap.gapId)).not.toContain(
      "coverage:combination:ING-test:ambiguous-maximum-rule",
    );
  });

  it("does not apply an ingredient-scoped maximum rule to another compound ingredient", () => {
    const p = {
      ...product("P1", [
        ingredient("ING-a", "성분A"),
        ingredient("ING-b", "성분B"),
      ]),
      administrationConstraints: [
        {
          constraintId: "ADMIN-P1-B-MAX-DAILY",
          type: "maximum_daily_ingredient_amount",
          value: 100,
          valueUnit: "mg",
          ingredientId: "ING-b",
          evidence,
        },
      ],
    } as OtcProduct;
    const result = evaluateOtcSafety(
      [{ product: p, unitsPerDose: 2, dosesPerDay: 1 }],
      profile(),
      {
        releasedRules: [
          policy("RULE-ING-A", "max_daily_dose", {
            productItemSequences: ["P1"],
            ingredientIds: ["ING-a"],
            administrationConstraintTypes: ["maximum_daily_ingredient_amount"],
          }),
        ],
      },
    );

    expect(result.findings.map((finding) => finding.ruleId)).not.toContain(
      "RULE-ING-A",
    );
    expect(result.coverageGaps).toContainEqual(
      expect.objectContaining({
        gapId: "coverage:P1:ING-b:unmapped-maximum-source",
        productIds: ["P1"],
      }),
    );
  });

  it("compares each legacy maximum only with the product that owns it", () => {
    const ingredientFor = (
      amountPerUnit: number,
      maxDailyAmount: number,
    ): OtcIngredient => ({
      ...ingredient("ING-test", "검증성분"),
      amountPerUnit,
      maxDailyAmount,
    });
    const result = evaluateOtcSafety(
      [
        {
          product: product("P1", [ingredientFor(10, 300)]),
          unitsPerDose: 1,
          dosesPerDay: 1,
        },
        {
          product: product("P2", [ingredientFor(100, 100)]),
          unitsPerDose: 1,
          dosesPerDay: 1,
        },
      ],
      profile(),
      {
        releasedRules: [
          policy("RULE-P1-MAX", "max_daily_dose", {
            productItemSequences: ["P1"],
            ingredientIds: ["ING-test"],
            administrationConstraintTypes: ["maximum_daily_ingredient_amount"],
          }),
        ],
      },
    );

    expect(result.findings.map((finding) => finding.ruleId)).not.toContain(
      "RULE-P1-MAX",
    );
    expect(result.coverageGaps.map((gap) => gap.gapId)).not.toContain(
      "coverage:P2:ING-test:unmapped-maximum-source",
    );
  });

  it("does not apply an ingredient-scoped interval rule to another compound ingredient", () => {
    const p = {
      ...product("P1", [
        ingredient("ING-a", "성분A"),
        ingredient("ING-b", "성분B"),
      ]),
      administrationConstraints: [
        {
          constraintId: "ADMIN-P1-B-INTERVAL",
          type: "minimum_interval_hours",
          value: 6,
          valueUnit: "시간",
          ingredientId: "ING-b",
          evidence,
        },
      ],
    } as OtcProduct;
    const result = evaluateOtcSafety(
      [
        {
          product: p,
          unitsPerDose: 1,
          dosesPerDay: 1,
          hoursSincePreviousDose: 2,
        },
      ],
      profile(),
      {
        releasedRules: [
          policy("RULE-ING-A-INTERVAL", "minimum_interval", {
            productItemSequences: ["P1"],
            ingredientIds: ["ING-a"],
            administrationConstraintTypes: ["minimum_interval_hours"],
          }),
        ],
      },
    );

    expect(result.findings.map((finding) => finding.ruleId)).not.toContain(
      "RULE-ING-A-INTERVAL",
    );
    expect(result.coverageGaps).toContainEqual(
      expect.objectContaining({
        gapId: "coverage:P1:minimum_interval:unmapped-source",
      }),
    );
  });

  it("attaches rule evidence only when its product is part of the finding", () => {
    const same = ingredient("ING-test", "검증성분");
    const result = evaluateOtcSafety(
      [
        { product: product("P1", [same]), unitsPerDose: 1, dosesPerDay: 1 },
        { product: product("P2", [same]), unitsPerDose: 1, dosesPerDay: 1 },
      ],
      profile(),
      {
        releasedRules: [
          policy("OTC-RULE-001", "duplicate_ingredient", {
            ingredientIds: ["ING-test"],
          }),
        ],
      },
    );

    expect(result.findings[0]).toEqual(
      expect.objectContaining({
        ruleId: "OTC-RULE-001",
        ruleEvidence: [expect.objectContaining({ itemSequence: "P1" })],
      }),
    );
    expect(result.findings[0].evidence).not.toEqual(result.findings[0].ruleEvidence);
  });

  it("does not let a legacy type set synthesize broad applicability", () => {
    const same = ingredient("ING-test", "검증성분");
    const result = evaluateOtcSafety(
      [
        { product: product("P1", [same]), unitsPerDose: 1, dosesPerDay: 1 },
        { product: product("P2", [same]), unitsPerDose: 1, dosesPerDay: 1 },
      ],
      profile({ redFlagSymptoms: ["호흡곤란"] }),
      new Set(["duplicate_ingredient", "urgent_referral"]),
      [{ itemSequence: "P1", terms: ["호흡곤란"] }],
    );

    expect(result.findings).toEqual([]);
    expect(result.coverageGaps.map((gap) => gap.ruleType)).toEqual(
      expect.arrayContaining(["duplicate_ingredient", "urgent_referral"]),
    );
  });

  it("accepts a legacy type set only when evidence carries the full approved policy", () => {
    const same = ingredient("ING-test", "검증성분");
    const approved = policy("OTC-RULE-001", "duplicate_ingredient", {
      ingredientIds: ["ING-test"],
    });
    const legacyEvidence = {
      ...approved.evidence[0],
      ruleType: approved.ruleType,
      scope: approved.scope,
      lineageStatus: approved.lineageStatus,
      applicability: approved.applicability,
    };
    const result = evaluateOtcSafety(
      [
        { product: product("P1", [same]), unitsPerDose: 1, dosesPerDay: 1 },
        { product: product("P2", [same]), unitsPerDose: 1, dosesPerDay: 1 },
      ],
      profile(),
      new Set(["duplicate_ingredient"]),
      undefined,
      { duplicate_ingredient: [legacyEvidence] },
    );

    expect(result.findings).toContainEqual(
      expect.objectContaining({ ruleId: "OTC-RULE-001" }),
    );
  });

  it("fails closed for malformed legacy rule IDs and applicability", () => {
    const same = ingredient("ING-test", "검증성분");
    const approved = policy("OTC-RULE-001", "duplicate_ingredient", {
      ingredientIds: ["ING-test"],
    });
    const baseLegacyEvidence = {
      ...approved.evidence[0],
      ruleType: approved.ruleType,
      scope: approved.scope,
      lineageStatus: approved.lineageStatus,
      applicability: approved.applicability,
    };

    for (const malformed of [
      { ...baseLegacyEvidence, ruleId: "" },
      { ...baseLegacyEvidence, applicability: [] as never },
    ]) {
      const result = evaluateOtcSafety(
        [
          { product: product("P1", [same]), unitsPerDose: 1, dosesPerDay: 1 },
          { product: product("P2", [same]), unitsPerDose: 1, dosesPerDay: 1 },
        ],
        profile(),
        new Set(["duplicate_ingredient"]),
        undefined,
        { duplicate_ingredient: [malformed] } as never,
      );

      expect(result.findings).toEqual([]);
      expect(result.coverageGaps).toContainEqual(
        expect.objectContaining({ ruleType: "duplicate_ingredient" }),
      );
    }
  });
});

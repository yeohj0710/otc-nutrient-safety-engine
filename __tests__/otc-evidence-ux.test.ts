import { describe, expect, it } from "vitest";

import literatureData from "@/src/generated/otc-supporting-literature.json";
import runtimeData from "@/src/generated/otc-runtime.json";
import {
  backgroundLiteratureForFinding,
  buildFindingContext,
  buildProductSupportSummary,
  directLiteratureForFinding,
  formatEvidenceSource,
  groupCoverageGaps,
  groupFindingsForDisplay,
  literatureStatusSummary,
  literatureRelationLabel,
  productLiteratureCoverage,
  ruleEvidenceForFinding,
  splitSupportingLiteratureForFinding,
  supportingLiteratureForFinding,
  type SupportingLiterature,
} from "@/src/lib/otc/presentation";
import type {
  EvaluationCoverageGap,
  OtcProduct,
  ReleasedRulePolicy,
  SafetyFinding,
  SelectedProduct,
} from "@/src/lib/otc/schema";

const gap = (
  gapId: string,
  ruleType: string,
  titleKo: string,
  productId: string,
): EvaluationCoverageGap => ({
  gapId,
  ruleType,
  titleKo,
  detailKo: `${productId} 상세 안내`,
  productIds: [productId],
});

const runtimeProducts = runtimeData.products as OtcProduct[];

const selectRuntimeProducts = (...itemSequences: string[]): SelectedProduct[] =>
  itemSequences.map((itemSequence) => {
    const product = runtimeProducts.find(
      (candidate) => candidate.itemSequence === itemSequence,
    );
    if (!product) throw new Error(`Missing runtime product ${itemSequence}`);
    return { product, unitsPerDose: 1, dosesPerDay: 1 };
  });

const literatureFinding = (
  ruleId: string,
  ruleType: string,
  selected: SelectedProduct[],
  ingredientIds: string[],
): SafetyFinding => ({
  findingId: `test:${ruleId}`,
  ruleId,
  decisionBasis: "released_rule",
  ruleType,
  severity: "high",
  titleKo: "검증 판정",
  detailKo: "문헌 범위 검증",
  nextActionKo: "허가사항을 확인하세요.",
  productIds: selected.map(({ product }) => product.productId),
  ingredientIds,
  evidence: [],
});

describe("OTC evidence presentation", () => {
  it("groups repeated ingredient warnings for the same product pair", () => {
    const duplicateFinding = (
      ingredientId: string,
      findingId: string,
    ): SafetyFinding => ({
      findingId,
      ruleId: "OTC-RULE-001",
      decisionBasis: "released_rule",
      ruleType: "duplicate_ingredient",
      severity: "high",
      titleKo: "같은 성분이 여러 제품에 들어 있습니다",
      detailKo: `${ingredientId} 성분이 겹칩니다.`,
      nextActionKo: "포장과 허가사항을 확인하세요.",
      productIds: ["P2", "P1"],
      ingredientIds: [ingredientId],
      evidence: [
        { sourceId: "MFDS", locator: "제품 허가사항", url: "https://example.com/source" },
      ],
    });
    const findings = [
      duplicateFinding("ING-A", "duplicate:A"),
      duplicateFinding("ING-B", "duplicate:B"),
      duplicateFinding("ING-C", "duplicate:C"),
    ];
    const ingredientNames = new Map([
      ["ING-A", "성분A"],
      ["ING-B", "성분B"],
      ["ING-C", "성분C"],
    ]);

    const grouped = groupFindingsForDisplay(findings, ingredientNames);

    expect(grouped).toHaveLength(1);
    expect(grouped[0].productIds).toEqual(["P1", "P2"]);
    expect(grouped[0].ingredientIds).toEqual(["ING-A", "ING-B", "ING-C"]);
    expect(grouped[0].titleKo).toBe("같은 성분 3개가 여러 제품에 들어 있습니다");
    expect(grouped[0].detailKo).toContain("성분A, 성분B, 성분C");
    expect(grouped[0].evidence).toHaveLength(1);
    expect(grouped[0].members).toEqual(findings);
  });

  it("preserves each grouped ingredient calculation instead of erasing it", () => {
    const findings: SafetyFinding[] = [
      {
        findingId: "duplicate:A",
        ruleId: "OTC-RULE-001",
        decisionBasis: "released_rule",
        ruleType: "duplicate_ingredient",
        severity: "high",
        titleKo: "중복",
        detailKo: "A",
        nextActionKo: "확인",
        productIds: ["P1", "P2"],
        ingredientIds: ["ING-A"],
        calculatedAmount: 600,
        unit: "mg",
        evidence: [],
      },
      {
        findingId: "duplicate:B",
        ruleId: "OTC-RULE-001",
        decisionBasis: "released_rule",
        ruleType: "duplicate_ingredient",
        severity: "high",
        titleKo: "중복",
        detailKo: "B",
        nextActionKo: "확인",
        productIds: ["P1", "P2"],
        ingredientIds: ["ING-B"],
        calculatedAmount: 24,
        unit: "mg",
        evidence: [],
      },
    ];

    const [grouped] = groupFindingsForDisplay(
      findings,
      new Map([
        ["ING-A", "성분A"],
        ["ING-B", "성분B"],
      ]),
    );

    expect(grouped.members).toEqual(findings);
    expect(grouped.members.map((member) => member.calculatedAmount)).toEqual([600, 24]);
    expect(grouped.members.map((member) => member.unit)).toEqual(["mg", "mg"]);
  });

  it("does not merge different product pairs or other rule types", () => {
    const findings: SafetyFinding[] = [
      {
        findingId: "duplicate:A",
        ruleId: "OTC-RULE-001",
        decisionBasis: "released_rule",
        ruleType: "duplicate_ingredient",
        severity: "high",
        titleKo: "중복",
        detailKo: "A",
        nextActionKo: "확인",
        productIds: ["P1", "P2"],
        ingredientIds: ["ING-A"],
        evidence: [],
      },
      {
        findingId: "duplicate:B",
        ruleId: "OTC-RULE-001",
        decisionBasis: "released_rule",
        ruleType: "duplicate_ingredient",
        severity: "high",
        titleKo: "중복",
        detailKo: "B",
        nextActionKo: "확인",
        productIds: ["P1", "P3"],
        ingredientIds: ["ING-B"],
        evidence: [],
      },
      {
        findingId: "maximum:C",
        ruleId: "OTC-RULE-003",
        decisionBasis: "released_rule",
        ruleType: "max_daily_dose",
        severity: "high",
        titleKo: "최대량",
        detailKo: "C",
        nextActionKo: "확인",
        productIds: ["P1", "P2"],
        ingredientIds: ["ING-C"],
        evidence: [],
      },
    ];

    expect(groupFindingsForDisplay(findings, new Map())).toHaveLength(3);
  });

  it("does not merge findings from different rule IDs", () => {
    const shared: SafetyFinding = {
      findingId: "duplicate:R1",
      ruleId: "OTC-RULE-001",
      decisionBasis: "released_rule",
      ruleType: "duplicate_ingredient",
      severity: "high",
      titleKo: "중복",
      detailKo: "A",
      nextActionKo: "확인",
      productIds: ["P1", "P2"],
      ingredientIds: ["ING-A"],
      evidence: [],
    };

    expect(
      groupFindingsForDisplay(
        [
          shared,
          {
            ...shared,
            findingId: "duplicate:R2",
            ruleId: "OTC-RULE-999",
            ingredientIds: ["ING-B"],
          },
        ],
        new Map(),
      ),
    ).toHaveLength(2);
  });

  it("groups repeated product-level coverage gaps by the requested condition", () => {
    const grouped = groupCoverageGaps(
      [
        gap("g1", "pregnancy_lactation", "임신·수유 기준을 확인하지 못했습니다", "P1"),
        gap("g2", "pregnancy_lactation", "임신·수유 기준을 확인하지 못했습니다", "P2"),
        gap("g3", "hepatic_disease", "간질환 기준을 확인하지 못했습니다", "P1"),
      ],
      new Map([
        ["P1", "검증제품1"],
        ["P2", "검증제품2"],
      ]),
    );

    expect(grouped).toEqual([
      expect.objectContaining({
        ruleType: "pregnancy_lactation",
        productNames: ["검증제품1", "검증제품2"],
        profileDetailMessages: [],
        count: 2,
      }),
      expect.objectContaining({
        ruleType: "hepatic_disease",
        productNames: ["검증제품1"],
        count: 1,
      }),
    ]);
  });

  it("preserves the exact unrecognized medication text in grouped profile gaps", () => {
    const grouped = groupCoverageGaps(
      [
        {
          gapId: "coverage:profile:unrecognized-medications",
          ruleType: "medication_interaction",
          titleKo: "입력한 병용약을 분류하지 못했습니다",
          detailKo: "미분류약은 현재 병용약 분류에 연결되지 않았습니다.",
          productIds: ["P1"],
        },
      ],
      new Map([["P1", "검증제품1"]]),
    );
    expect(grouped[0].profileDetailMessages).toEqual([
      "미분류약은 현재 병용약 분류에 연결되지 않았습니다.",
    ]);
  });

  it("uses a reader-facing name for MFDS authorization evidence", () => {
    expect(formatEvidenceSource("MFDS-NEDRUG-DETAIL")).toBe("식약처 의약품안전나라 허가사항");
    expect(formatEvidenceSource("TEST-SOURCE")).toBe("TEST-SOURCE");
  });

  it("builds visible product and ingredient facts for a finding", () => {
    const product: OtcProduct = {
      productId: "P1",
      itemSequence: "1",
      productName: "검증감기약",
      classification: "일반의약품",
      authorizationStatus: "active",
      doseUnitLabel: "병",
      ingredients: [
        {
          ingredientId: "I1",
          nameKo: "페닐레프린염산염",
          amountPerUnit: 10,
          unit: "mg",
          pharmacologicClasses: [],
          flags: [],
          evidence: { sourceId: "S", locator: "L", url: "https://example.test" },
        },
      ],
      flags: ["decongestant_hypertension"],
      evidence: { sourceId: "S", locator: "L", url: "https://example.test" },
    };
    const selected: SelectedProduct[] = [
      { product, unitsPerDose: 1, dosesPerDay: 3 },
    ];
    const finding: SafetyFinding = {
      findingId: "decongestant:P1",
      ruleId: "OTC-RULE-014",
      decisionBasis: "released_rule",
      ruleType: "decongestant_hypertension",
      severity: "high",
      titleKo: "혈압 관련 주의",
      detailKo: "입력 조건: 고혈압·심혈관질환",
      nextActionKo: "상담하세요.",
      productIds: ["P1"],
      ingredientIds: ["I1"],
      evidence: [],
    };

    expect(buildFindingContext(finding, selected)).toEqual({
      productNames: ["검증감기약"],
      ingredientFacts: ["페닐레프린염산염 10 mg/병"],
    });
  });

  it("separates supported check types from released-rule bindings", () => {
    const evidence = {
      sourceId: "TEST-SOURCE",
      locator: "검증용 허가사항",
      url: "https://example.test/source",
    };
    const product: OtcProduct = {
      productId: "P1",
      itemSequence: "1",
      productName: "검증제품",
      classification: "일반의약품",
      authorizationStatus: "active",
      doseUnitLabel: "정",
      ingredients: [],
      administrationConstraints: [
        {
          constraintId: "P1:maximum-doses",
          type: "maximum_doses_per_day",
          value: 3,
          valueUnit: "회/일",
          evidence,
        },
      ],
      supportedRuleTypes: ["max_daily_dose", "minimum_interval", "hepatic_disease"],
      supportedReleasedRuleIds: ["OTC-RULE-003"],
      flags: [],
      evidence,
    };

    const doseOnly = buildProductSupportSummary(
      product,
      new Set(["max_daily_dose", "minimum_interval"]),
    );
    expect(doseOnly).toEqual({
      activeCheckTypes: ["max_daily_dose", "minimum_interval"],
      administrationConstraintCount: 1,
      conditionLabels: [],
      detailLabels: ["1회·하루 사용량", "사용·복용 간격"],
      releasedRuleBindingCount: 1,
      summaryKo: "용량·간격만 확인 가능",
      supportedCheckTypeCount: 2,
    });

    const maximumOnly = buildProductSupportSummary(
      product,
      new Set(["max_daily_dose"]),
    );
    expect(maximumOnly.summaryKo).toBe("용량만 확인 가능");

    const broader = buildProductSupportSummary(
      product,
      new Set(["max_daily_dose", "hepatic_disease"]),
    );
    expect(broader.summaryKo).toBe("용량 외 조건도 확인 가능");
    expect(broader.conditionLabels).toEqual(["간질환"]);
    expect(broader.supportedCheckTypeCount).toBe(2);
    expect(broader.releasedRuleBindingCount).toBe(1);
  });

  it("labels whether a paper supports caution or explains uncertainty", () => {
    expect(literatureRelationLabel("supports_caution")).toBe("주의를 뒷받침하는 연구");
    expect(literatureRelationLabel("contextualizes_uncertainty")).toBe("불확실성을 설명하는 연구");
  });

  it("distinguishes a selected product's rule quote from a representative quote", () => {
    const product: OtcProduct = {
      productId: "P1",
      itemSequence: "1",
      productName: "검증제품",
      classification: "일반의약품",
      authorizationStatus: "active",
      doseUnitLabel: "정",
      ingredients: [],
      flags: [],
      evidence: { sourceId: "S", locator: "L", url: "https://example.test" },
    };
    const selected: SelectedProduct[] = [{ product, unitsPerDose: 1, dosesPerDay: 1 }];
    const finding: SafetyFinding = {
      findingId: "dose:P1",
      ruleId: "R1",
      decisionBasis: "released_rule",
      ruleType: "max_daily_dose",
      severity: "high",
      titleKo: "하루 용량 주의",
      detailKo: "검증 상세",
      nextActionKo: "상담하세요.",
      productIds: ["P1"],
      ingredientIds: [],
      evidence: [],
    };
    const direct = {
      ruleId: "R1",
      productName: "검증제품",
      itemSequence: "1",
      sourceId: "S",
      locator: "L1",
      url: "https://example.test/1",
      excerptKo: "직접 원문",
    };
    const representative = {
      ...direct,
      productName: "대표제품",
      itemSequence: "2",
      locator: "L2",
      url: "https://example.test/2",
      excerptKo: "대표 원문",
    };

    expect(
      ruleEvidenceForFinding(finding, selected, [
        representative,
        direct,
        { ...direct },
      ]),
    ).toEqual(
      expect.objectContaining({
        evidence: direct,
        direct: [direct],
        representative: [representative],
        productMatch: "all",
        matchedProductCount: 1,
        findingProductCount: 1,
      }),
    );
    expect(ruleEvidenceForFinding(finding, selected, [representative])).toEqual(
      expect.objectContaining({
        evidence: undefined,
        direct: [],
        representative: [representative],
        productMatch: "none",
        matchedProductCount: 0,
        findingProductCount: 1,
      }),
    );
    expect(
      ruleEvidenceForFinding(finding, selected, [
        { ...direct, ruleId: "R2" },
      ]),
    ).toEqual({
      evidence: undefined,
      direct: [],
      representative: [],
      productMatch: "none",
      matchedProductCount: 0,
      findingProductCount: 1,
    });
    const secondProduct = { ...product, productId: "P2", itemSequence: "2" };
    expect(
      ruleEvidenceForFinding(
        { ...finding, productIds: ["P1", "P2"] },
        [...selected, { product: secondProduct, unitsPerDose: 1, dosesPerDay: 1 }],
        [direct],
      ),
    ).toEqual(
      expect.objectContaining({
        evidence: direct,
        direct: [direct],
        representative: [],
        productMatch: "partial",
        matchedProductCount: 1,
        findingProductCount: 2,
      }),
    );
    const firstSnapshot = { ...direct, sourceVersion: "2025-01-01" };
    const secondSnapshot = { ...direct, sourceVersion: "2026-01-01" };
    expect(
      ruleEvidenceForFinding(finding, selected, [
        firstSnapshot,
        { ...firstSnapshot },
        secondSnapshot,
      ]).direct,
    ).toEqual([firstSnapshot, secondSnapshot]);
  });

  it("keeps the 10/5/4 literature states separate with user-facing labels", () => {
    const papers = literatureData as SupportingLiterature[];

    expect(
      papers.reduce(
        (summary, paper) => {
          if (paper.v50Validation.screened) summary.v50Linked += 1;
          else if (paper.v50Validation.reason === "not_in_v5_corpus") {
            summary.notInV5Corpus += 1;
          } else if (
            paper.v50Validation.reason ===
            "no_retain_decision_for_rule_question"
          ) {
            summary.noRetainForRuleQuestion += 1;
          } else summary.unknown += 1;
          return summary;
        },
        {
          v50Linked: 0,
          notInV5Corpus: 0,
          noRetainForRuleQuestion: 0,
          unknown: 0,
        },
      ),
    ).toEqual({
      v50Linked: 10,
      notInV5Corpus: 5,
      noRetainForRuleQuestion: 4,
      unknown: 0,
    });
    expect(literatureStatusSummary(papers)).toEqual({
      v5Linked: 10,
      directCapable: 5,
      backgroundOnly: 5,
      excluded: 10,
    });
  });

  it("keeps a rejected v5.0 candidate out of the accepted literature split", () => {
    const finding: SafetyFinding = {
      findingId: "sedative-medication:P1",
      ruleId: "OTC-RULE-013",
      decisionBasis: "released_rule",
      ruleType: "sedative_medication",
      severity: "high",
      titleKo: "진정 작용이 겹칩니다",
      detailKo: "검증 상세",
      nextActionKo: "상담하세요.",
      productIds: ["P1"],
      ingredientIds: ["ING-chlorpheniramine_maleate"],
      evidence: [],
    };
    const matched = supportingLiteratureForFinding(
      finding,
      literatureData as SupportingLiterature[],
      [],
      { medications: ["졸피뎀"], redFlagSymptoms: [] },
    );
    expect(matched).toEqual([]);
    expect(
      (literatureData as SupportingLiterature[]).find(
        (paper) => paper.pmid === "23747192",
      )?.v50Validation.reason,
    ).toBe("not_in_v5_corpus");
    expect(finding.evidence).toEqual([]);
  });

  it("never attaches released-rule literature to an administration constraint", () => {
    const selected = selectRuntimeProducts("202106092");
    const sourcePaper = (literatureData as SupportingLiterature[]).find(
      (paper) => paper.pmid === "30306812",
    );
    if (!sourcePaper) throw new Error("Missing accepted direct literature fixture");
    const rule003Papers: SupportingLiterature[] = [
      {
        ...sourcePaper,
        ruleTypes: ["max_daily_dose"],
        ruleLinks: sourcePaper.ruleLinks
          .filter((link) => link.ruleId === "OTC-RULE-001")
          .map((link) => ({
            ...link,
            linkId: "TEST-LINK-RULE-003",
            ruleId: "OTC-RULE-003",
            ruleType: "max_daily_dose",
          })),
      },
    ];
    const releasedFinding = literatureFinding(
      "OTC-RULE-003",
      "max_daily_dose",
      selected,
      ["ING-acetaminophen"],
    );
    const profile = {
      ageYears: 30,
      medications: [],
      redFlagSymptoms: [],
    };

    expect(
      directLiteratureForFinding(
        releasedFinding,
        rule003Papers,
        selected,
        profile,
      ),
    ).not.toEqual([]);
    expect(
      splitSupportingLiteratureForFinding(
        {
          ...releasedFinding,
          findingId: "admin:maximum-units-per-dose",
          decisionBasis: "administration_constraint",
        },
        rule003Papers,
        selected,
        profile,
      ),
    ).toEqual({ direct: [], background: [] });
  });

  it("does not present a pregnancy-only paper as lactation evidence", () => {
    const selected = selectRuntimeProducts("198601920");
    const finding: SafetyFinding = {
      findingId: "pregnancy:P1",
      ruleId: "OTC-RULE-006",
      decisionBasis: "released_rule",
      ruleType: "pregnancy_lactation",
      severity: "high",
      titleKo: "임신·수유 주의",
      detailKo: "검증 상세",
      nextActionKo: "상담하세요.",
      productIds: selected.map(({ product }) => product.productId),
      ingredientIds: ["ING-ibuprofen"],
      evidence: [],
    };
    const papers = literatureData as SupportingLiterature[];
    const lactationOnly = splitSupportingLiteratureForFinding(
      finding,
      papers,
      selected,
      {
        lactating: true,
        medications: [],
        redFlagSymptoms: [],
      },
    );
    const pregnancyTrimester3 = splitSupportingLiteratureForFinding(
      finding,
      papers,
      selected,
      {
        pregnant: true,
        pregnancyTrimester: 3,
        medications: [],
        redFlagSymptoms: [],
      },
    );

    expect(lactationOnly.direct.map(({ paper }) => paper.pmid)).not.toContain(
      "39714827",
    );
    expect(lactationOnly.background.map(({ paper }) => paper.pmid)).toContain(
      "39714827",
    );
    expect(
      pregnancyTrimester3.direct.map(({ paper }) => paper.pmid),
    ).toContain("39714827");
    for (const pregnancyTrimester of [undefined, 1, 2] as const) {
      const split = splitSupportingLiteratureForFinding(
        finding,
        papers,
        selected,
        {
          pregnant: true,
          pregnancyTrimester,
          medications: [],
          redFlagSymptoms: [],
        },
      );
      expect(split.direct, `trimester ${pregnancyTrimester ?? "unknown"}`).toEqual(
        [],
      );
      expect(split.background.map(({ paper }) => paper.pmid)).toEqual([
        "39714827",
      ]);
    }

    const naproxen = selectRuntimeProducts("197500016");
    expect(
      directLiteratureForFinding(
        literatureFinding(
          "OTC-RULE-006",
          "pregnancy_lactation",
          naproxen,
          ["ING-naproxen"],
        ),
        papers,
        naproxen,
        {
          pregnant: true,
          pregnancyTrimester: 3,
          medications: [],
          redFlagSymptoms: [],
        },
      ),
    ).toEqual([]);
  });

  it("requires the classified ingredient and profile scope for direct evidence", () => {
    const selected = selectRuntimeProducts("196800036", "202106092");
    const finding: SafetyFinding = {
      findingId: "duplicate-ingredient:digestive-enzyme",
      ruleId: "OTC-RULE-001",
      decisionBasis: "released_rule",
      ruleType: "duplicate_ingredient",
      severity: "high",
      titleKo: "같은 성분이 여러 제품에 들어 있습니다",
      detailKo: "소화제 성분이 겹칩니다.",
      nextActionKo: "상담하세요.",
      productIds: selected.map(({ product }) => product.productId),
      ingredientIds: ["ING-acetaminophen"],
      evidence: [],
    };
    const papers = literatureData as SupportingLiterature[];

    expect(
      directLiteratureForFinding(finding, papers, selected).map(
        ({ paper }) => paper.pmid,
      ),
    ).toEqual([]);
    expect(
      backgroundLiteratureForFinding(finding, papers, selected).map(
        ({ paper }) => paper.pmid,
      ),
    ).toEqual([]);
    expect(
      splitSupportingLiteratureForFinding(finding, papers, selected, {
        ageYears: 11,
        medications: [],
        redFlagSymptoms: [],
      }),
    ).toEqual({ direct: [], background: [] });
    expect(
      directLiteratureForFinding(finding, papers, selected, {
        ageYears: 30,
        medications: [],
        redFlagSymptoms: [],
      }).map(({ paper }) => paper.pmid),
    ).toEqual(["30306812"]);
  });

  it("keeps Rule008 direct only for an ibuprofen-taking child with kidney disease", () => {
    const selected = selectRuntimeProducts("198601920");
    const finding = literatureFinding(
      "OTC-RULE-008",
      "renal_disease",
      selected,
      ["ING-ibuprofen"],
    );
    const papers = literatureData as SupportingLiterature[];
    expect(
      directLiteratureForFinding(finding, papers, selected, {
        ageYears: 18,
        kidneyDisease: true,
        medications: [],
        redFlagSymptoms: [],
      }).map(({ paper }) => paper.pmid),
    ).toEqual(["33662136"]);
    for (const ageYears of [undefined, 19]) {
      const split = splitSupportingLiteratureForFinding(
        finding,
        papers,
        selected,
        {
          ageYears,
          kidneyDisease: true,
          medications: [],
          redFlagSymptoms: [],
        },
      );
      expect(split.direct).toEqual([]);
      expect(split.background.map(({ paper }) => paper.pmid)).toEqual([
        "33662136",
      ]);
    }
  });

  it("labels Rule012 direct for warfarin and background for coumarin", () => {
    const selected = selectRuntimeProducts("198601920");
    const finding = literatureFinding(
      "OTC-RULE-012",
      "anticoagulant_antiplatelet",
      selected,
      ["ING-ibuprofen"],
    );
    const papers = literatureData as SupportingLiterature[];
    expect(
      directLiteratureForFinding(finding, papers, selected, {
        medications: ["와파린"],
        redFlagSymptoms: [],
      }).map(({ paper }) => paper.pmid),
    ).toEqual(["39551938"]);
    expect(
      backgroundLiteratureForFinding(finding, papers, selected, {
        medications: ["쿠마린"],
        redFlagSymptoms: [],
      }).map(({ paper }) => paper.pmid),
    ).toEqual(["39551938"]);
  });

  it("requires the exact Pancol product, both ingredients, and condition for Rule014", () => {
    const selected = selectRuntimeProducts("196800036");
    const ingredientIds = selected[0].product.ingredients.map(
      (ingredient) => ingredient.ingredientId,
    );
    const finding = literatureFinding(
      "OTC-RULE-014",
      "decongestant_hypertension",
      selected,
      ingredientIds,
    );
    const papers = literatureData as SupportingLiterature[];
    const profile = {
      hypertensionOrCardiovascularDisease: true,
      medications: [],
      redFlagSymptoms: [],
    };
    expect(
      directLiteratureForFinding(finding, papers, selected, profile).map(
        ({ paper }) => paper.pmid,
      ),
    ).toEqual(["26022219"]);
    expect(
      directLiteratureForFinding(
        { ...finding, ingredientIds: ["ING-acetaminophen"] },
        papers,
        selected,
        profile,
      ),
    ).toEqual([]);
    expect(
      backgroundLiteratureForFinding(
        { ...finding, ingredientIds: ["ING-acetaminophen"] },
        papers,
        selected,
        profile,
      ).map(({ paper }) => paper.pmid),
    ).toEqual(["26022219"]);
  });

  it("keeps background-only links visible for same and other ingredients", () => {
    const selected = selectRuntimeProducts("202106092");
    const sameIngredient = literatureFinding(
      "OTC-RULE-007",
      "hepatic_disease",
      selected,
      ["ING-acetaminophen"],
    );
    const profile = {
      liverDisease: true,
      medications: [],
      redFlagSymptoms: [],
    };
    for (const finding of [
      sameIngredient,
      { ...sameIngredient, ingredientIds: ["ING-ibuprofen"] },
    ]) {
      expect(
        backgroundLiteratureForFinding(
          finding,
          literatureData as SupportingLiterature[],
          selected,
          profile,
        ).map(({ paper }) => paper.pmid),
      ).toEqual(["26460177"]);
    }
  });

  it("keeps candidates outside v5.0 out of the accepted direct/background split", () => {
    const selected = selectRuntimeProducts("196800036", "202106092");
    const finding: SafetyFinding = {
      findingId: "duplicate-ingredient:P1",
      ruleId: "OTC-RULE-001",
      decisionBasis: "released_rule",
      ruleType: "duplicate_ingredient",
      severity: "high",
      titleKo: "같은 성분 중복",
      detailKo: "검증 상세",
      nextActionKo: "상담하세요.",
      productIds: selected.map(({ product }) => product.productId),
      ingredientIds: ["ING-acetaminophen"],
      evidence: [],
    };

    const split = splitSupportingLiteratureForFinding(
      finding,
      literatureData as SupportingLiterature[],
      selected,
      { ageYears: 30, medications: [], redFlagSymptoms: [] },
    );
    expect(split.direct.map(({ paper }) => paper.pmid)).toEqual(["30306812"]);
    expect(split.background).toEqual([]);
    expect(
      [...split.direct, ...split.background].map(({ paper }) => paper.pmid),
    ).not.toContain("26149538");
  });

  it("counts only ingredient-and-rule matches as a product's linked literature", () => {
    const product: OtcProduct = {
      productId: "P1",
      itemSequence: "1",
      productName: "검증 소화제",
      classification: "일반의약품",
      authorizationStatus: "active",
      therapeuticClass: "위장관 일반의약품",
      doseUnitLabel: "정",
      supportedRuleTypes: ["duplicate_ingredient"],
      ingredients: [
        {
          ingredientId: "ING-acetaminophen",
          nameKo: "검증 성분",
          amountPerUnit: 1,
          unit: "mg",
          pharmacologicClasses: [],
          flags: [],
          evidence: { sourceId: "S", locator: "L", url: "https://example.test" },
        },
      ],
      flags: [],
      evidence: { sourceId: "S", locator: "L", url: "https://example.test" },
    };

    expect(
      productLiteratureCoverage(
        product,
        literatureData as SupportingLiterature[],
        runtimeData.releasedRules as ReleasedRulePolicy[],
      ),
    ).toEqual({ v5Linked: 1, directCapable: 1 });
  });

  it("keeps every paper traceable and explicitly outside rule release evidence", () => {
    const papers = literatureData as SupportingLiterature[];
    expect(papers.length).toBeGreaterThanOrEqual(5);
    expect(new Set(papers.map((paper) => paper.pmid)).size).toBe(papers.length);
    for (const paper of papers) {
      expect(paper.title).toBeTruthy();
      expect(paper.doi).toBeTruthy();
      expect(paper.url).toBe(`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`);
      expect(paper.keyFindingKo).toBeTruthy();
      expect(paper.limitationKo).toBeTruthy();
      expect(paper.selectionReasonKo).toBeTruthy();
      expect([
        "supports_caution",
        "contextualizes_uncertainty",
        "supports_mechanism",
      ]).toContain(paper.evidenceRelation);
      expect(paper.supportsRuleRelease).toBe(false);
      expect(paper.reviewStatus).toBe("agent_curated_from_v40_retained_corpus");
      // 문헌은 설명용이라는 사실과 면책 문구가 데이터에 함께 붙어 있어야 한다.
      expect(paper.evidenceAuthority).toBe("literature_explanatory_only");
      expect(paper.disclaimerKo).toBe(
        "참고 문헌은 판정 근거가 아니며 허가원문 판정을 바꾸지 않습니다.",
      );
      expect(paper.ruleLinks.length).toBeGreaterThan(0);
      for (const link of paper.ruleLinks) {
        // 모든 연결은 초록의 문장 단위 locator 와 원문 인용을 가진다.
        expect(link.locator).toMatch(/^abstract:sentence:\d+$/);
        expect(link.locatorQuoteEn.length).toBeGreaterThan(20);
        expect(["consistent", "conflict"]).toContain(link.authorizationAlignment);
        if (link.authorizationAlignment === "conflict") {
          expect(link.authorizationNoteKo.length).toBeGreaterThan(10);
        }
      }
    }
  });

  it("covers all 16 rules and preserves authorization conflicts", () => {
    const papers = literatureData as SupportingLiterature[];
    const links = papers.flatMap((paper) => paper.ruleLinks);
    expect(new Set(links.map((link) => link.ruleId)).size).toBe(16);
    // 허가원문과 어긋나는 문헌을 지우지 않고 conflict 로 남긴다.
    expect(
      links.filter((link) => link.authorizationAlignment === "conflict").length,
    ).toBeGreaterThan(0);
    // 문헌이 규칙을 배포시키는 일은 없다.
    expect(papers.every((paper) => paper.supportsRuleRelease === false)).toBe(true);
  });
});

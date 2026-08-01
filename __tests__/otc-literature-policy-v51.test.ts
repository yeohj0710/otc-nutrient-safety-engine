import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import literatureData from "@/src/generated/otc-supporting-literature.json";
import runtimeData from "@/src/generated/otc-runtime.json";
import {
  FindingLiteratureGroup,
  LiteratureCard,
} from "@/src/components/otc-product-safety-client";
import {
  literatureHomepageStatusSummary,
  literatureStatusLabel,
  literatureStatusSummary,
  productLiteratureCoverage,
  splitSupportingLiteratureForFinding,
  type SplitSupportingLiterature,
  type SupportingLiterature,
  type SupportingLiteratureRuleLink,
  type SupportingLiteratureV51Classification,
} from "@/src/lib/otc/presentation";
import type {
  OtcProduct,
  ReleasedRulePolicy,
  SafetyFinding,
  SelectedProduct,
  UserProfile,
} from "@/src/lib/otc/schema";

type ExpectedUiResult = "direct" | "background" | "mixed" | "excluded";

const literaturePolicyMatrix = [
  {
    linkId: "OTC-LIT-LINK-001",
    lineageStatus: "v50_emitted",
    semanticClassification: "direct_match",
    uiPolicy: "direct",
    uiDirectLabelAllowed: true,
    expectedUiResult: "direct",
  },
  {
    linkId: "OTC-LIT-LINK-002",
    lineageStatus: "v50_rejected_not_in_v5_corpus",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-003",
    lineageStatus: "v50_emitted",
    semanticClassification: "background_context",
    uiPolicy: "background_only",
    uiDirectLabelAllowed: false,
    expectedUiResult: "background",
  },
  {
    linkId: "OTC-LIT-LINK-004",
    lineageStatus: "v50_rejected_not_in_v5_corpus",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-005",
    lineageStatus: "v50_rejected_not_in_v5_corpus",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-006",
    lineageStatus: "v50_emitted",
    semanticClassification: "background_context",
    uiPolicy: "background_only",
    uiDirectLabelAllowed: false,
    expectedUiResult: "background",
  },
  {
    linkId: "OTC-LIT-LINK-007",
    lineageStatus: "v50_emitted",
    semanticClassification: "background_context",
    uiPolicy: "background_only",
    uiDirectLabelAllowed: false,
    expectedUiResult: "background",
  },
  {
    linkId: "OTC-LIT-LINK-008",
    lineageStatus: "v50_emitted",
    semanticClassification: "background_context",
    uiPolicy: "background_only",
    uiDirectLabelAllowed: false,
    expectedUiResult: "background",
  },
  {
    linkId: "OTC-LIT-LINK-009",
    lineageStatus: "v50_emitted",
    semanticClassification: "mixed_scope",
    uiPolicy: "direct_when_scope_matches_else_background",
    uiDirectLabelAllowed: true,
    expectedUiResult: "mixed",
  },
  {
    linkId: "OTC-LIT-LINK-010",
    lineageStatus: "v50_emitted",
    semanticClassification: "background_context",
    uiPolicy: "background_only",
    uiDirectLabelAllowed: false,
    expectedUiResult: "background",
  },
  {
    linkId: "OTC-LIT-LINK-011",
    lineageStatus: "v50_emitted",
    semanticClassification: "mixed_scope",
    uiPolicy: "direct_when_scope_matches_else_background",
    uiDirectLabelAllowed: true,
    expectedUiResult: "mixed",
  },
  {
    linkId: "OTC-LIT-LINK-012",
    lineageStatus: "v50_rejected_not_in_v5_corpus",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-013",
    lineageStatus: "v50_rejected_no_retain_decision_for_rule_question",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-014",
    lineageStatus: "v50_rejected_no_retain_decision_for_rule_question",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-015",
    lineageStatus: "v50_emitted",
    semanticClassification: "mixed_scope",
    uiPolicy: "direct_when_scope_matches_else_background",
    uiDirectLabelAllowed: true,
    expectedUiResult: "mixed",
  },
  {
    linkId: "OTC-LIT-LINK-016",
    lineageStatus: "v50_rejected_not_in_v5_corpus",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-017",
    lineageStatus: "v50_emitted",
    semanticClassification: "mixed_scope",
    uiPolicy: "direct_when_scope_matches_else_background",
    uiDirectLabelAllowed: true,
    expectedUiResult: "mixed",
  },
  {
    linkId: "OTC-LIT-LINK-018",
    lineageStatus: "v50_rejected_no_retain_decision_for_rule_question",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-019",
    lineageStatus: "v50_rejected_no_retain_decision_for_rule_question",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
  {
    linkId: "OTC-LIT-LINK-020",
    lineageStatus: "v50_rejected_not_in_v5_corpus",
    semanticClassification: null,
    uiPolicy: "exclude_from_result_ui",
    uiDirectLabelAllowed: false,
    expectedUiResult: "excluded",
  },
] as const satisfies ReadonlyArray<{
  linkId: string;
  lineageStatus: SupportingLiteratureV51Classification["lineageStatus"];
  semanticClassification: SupportingLiteratureV51Classification["semanticClassification"];
  uiPolicy: SupportingLiteratureV51Classification["uiPolicy"];
  uiDirectLabelAllowed: boolean;
  expectedUiResult: ExpectedUiResult;
}>;

const papers = literatureData as SupportingLiterature[];
const releasedRules = runtimeData.releasedRules as ReleasedRulePolicy[];
const runtimeProducts = runtimeData.products as OtcProduct[];

function findLiteratureLink(linkId: string): {
  paper: SupportingLiterature;
  link: SupportingLiteratureRuleLink;
} {
  for (const paper of papers) {
    const link = paper.ruleLinks.find((candidate) => candidate.linkId === linkId);
    if (link) return { paper, link };
  }
  throw new Error(`Missing literature fixture ${linkId}`);
}

function oneLinkPaper(
  paper: SupportingLiterature,
  link: SupportingLiteratureRuleLink,
): SupportingLiterature {
  return { ...paper, ruleTypes: [link.ruleType], ruleLinks: [link] };
}

function applyProfileCondition(profile: UserProfile, condition: string): void {
  if (condition === "medications.class=oral_anticoagulant") return;
  const match = condition.match(/^([A-Za-z][A-Za-z0-9]*)(?:>=|<=|=)(.+)$/);
  if (!match) throw new Error(`Unsupported test profile condition ${condition}`);
  const [, key, rawValue] = match;
  if (key === "ageYears") {
    profile.ageYears = Number(rawValue);
    return;
  }
  if (key === "pregnancyTrimester") {
    profile.pregnancyTrimester = Number(rawValue) as 1 | 2 | 3;
    return;
  }
  const enabled = rawValue === "true";
  switch (key) {
    case "pregnant":
      profile.pregnant = enabled;
      return;
    case "lactating":
      profile.lactating = enabled;
      return;
    case "liverDisease":
      profile.liverDisease = enabled;
      return;
    case "kidneyDisease":
      profile.kidneyDisease = enabled;
      return;
    case "giBleedingOrUlcer":
      profile.giBleedingOrUlcer = enabled;
      return;
    case "hypertensionOrCardiovascularDisease":
      profile.hypertensionOrCardiovascularDisease = enabled;
      return;
    case "willDrive":
      profile.willDrive = enabled;
      return;
    case "alcohol":
      profile.alcohol = enabled;
      return;
    default:
      throw new Error(`Unsupported test profile key ${key}`);
  }
}

function matchingInput(link: SupportingLiteratureRuleLink): {
  finding: SafetyFinding;
  selected: SelectedProduct[];
  profile: UserProfile;
} {
  const scope = link.v51Classification.directScope;
  const itemSequences =
    scope.productItemSequences.length > 0
      ? scope.productItemSequences
      : [`fixture-${link.linkId}`];
  const evidence = {
    sourceId: "TEST-SOURCE",
    locator: "test locator",
    url: "https://example.test/source",
  };
  const selected = itemSequences.map((itemSequence, index) => {
    const product: OtcProduct = {
      productId: `fixture-product-${link.linkId}-${index}`,
      itemSequence,
      productName: `fixture ${link.linkId}`,
      classification: "일반의약품",
      authorizationStatus: "active",
      doseUnitLabel: "정",
      supportedRuleTypes: [link.ruleType],
      ingredients: scope.ingredientIds.map((ingredientId) => ({
        ingredientId,
        nameKo: ingredientId,
        amountPerUnit: 1,
        unit: "mg",
        pharmacologicClasses: [],
        flags: [],
        evidence,
      })),
      flags: [],
      evidence,
    };
    return { product, unitsPerDose: 1, dosesPerDay: 1 };
  });
  const profile: UserProfile = {
    medications:
      scope.medicationTerms.length > 0 ? [scope.medicationTerms[0]] : [],
    redFlagSymptoms: [],
  };
  scope.profileConditions.forEach((condition) =>
    applyProfileCondition(profile, condition),
  );
  return {
    finding: {
      findingId: `fixture-finding-${link.linkId}`,
      ruleId: link.ruleId,
      decisionBasis: "released_rule",
      ruleType: link.ruleType,
      severity: "high",
      titleKo: "문헌 정책 검증",
      detailKo: "문헌 정책 검증",
      nextActionKo: "허가사항을 확인하세요.",
      productIds: selected.map(({ product }) => product.productId),
      ingredientIds: [...scope.ingredientIds],
      evidence: [],
    },
    selected,
    profile,
  };
}

function splitLink(linkId: string): {
  split: SplitSupportingLiterature;
  paper: SupportingLiterature;
  link: SupportingLiteratureRuleLink;
  input: ReturnType<typeof matchingInput>;
} {
  const { paper, link } = findLiteratureLink(linkId);
  const input = matchingInput(link);
  return {
    paper,
    link,
    input,
    split: splitSupportingLiteratureForFinding(
      input.finding,
      [oneLinkPaper(paper, link)],
      input.selected,
      input.profile,
    ),
  };
}

const linkIds = (split: SplitSupportingLiterature, kind: "direct" | "background") =>
  split[kind].map(({ link }) => link.linkId);

describe("v5.1 literature result policy", () => {
  it("keeps a literature-empty finding visible beside findings that have papers", () => {
    const finding: SafetyFinding = {
      findingId: "finding-without-literature",
      ruleId: "OTC-RULE-TEST",
      decisionBasis: "released_rule",
      ruleType: "test_rule",
      severity: "caution",
      titleKo: "문헌 없는 혼합 판정",
      detailKo: "검증용 판정",
      nextActionKo: "검증용 조치",
      productIds: ["P1"],
      ingredientIds: ["ING-1"],
      evidence: [],
    };

    const html = renderToStaticMarkup(
      createElement(FindingLiteratureGroup, {
        finding,
        matches: { direct: [], background: [] },
      }),
    );

    expect(html).toContain("문헌 없는 혼합 판정");
    expect(html).toContain("직접 일치 0편 · 배경 문헌 0편");
    expect(html).toContain("현재 성분과 직접 일치하는 논문은 없습니다.");
  });

  it("pins all 10 emitted and all 10 rejected legacy link classifications", () => {
    const generatedLinkIds = papers
      .flatMap((paper) => paper.ruleLinks.map((link) => link.linkId))
      .sort();
    expect(generatedLinkIds).toEqual(
      literaturePolicyMatrix.map(({ linkId }) => linkId).sort(),
    );
    expect(
      literaturePolicyMatrix.filter(
        ({ lineageStatus }) => lineageStatus === "v50_emitted",
      ),
    ).toHaveLength(10);
    expect(
      literaturePolicyMatrix.filter(
        ({ expectedUiResult }) => expectedUiResult === "excluded",
      ),
    ).toHaveLength(10);
    expect(
      literaturePolicyMatrix.reduce<Record<ExpectedUiResult, number>>(
        (counts, { expectedUiResult }) => ({
          ...counts,
          [expectedUiResult]: counts[expectedUiResult] + 1,
        }),
        { direct: 0, mixed: 0, background: 0, excluded: 0 },
      ),
    ).toEqual({ direct: 1, mixed: 4, background: 5, excluded: 10 });

    for (const expected of literaturePolicyMatrix) {
      const { link } = findLiteratureLink(expected.linkId);
      expect(link.v51Classification, expected.linkId).toMatchObject({
        lineageStatus: expected.lineageStatus,
        semanticClassification: expected.semanticClassification,
        uiPolicy: expected.uiPolicy,
        uiDirectLabelAllowed: expected.uiDirectLabelAllowed,
      });
    }
  });

  it("applies direct, background, mixed-scope, and exclusion behavior to every link", () => {
    for (const expected of literaturePolicyMatrix) {
      const { split, paper, link, input } = splitLink(expected.linkId);
      if (expected.expectedUiResult === "direct") {
        expect(linkIds(split, "direct"), expected.linkId).toEqual([
          expected.linkId,
        ]);
        expect(split.background, expected.linkId).toEqual([]);
        expect(
          splitSupportingLiteratureForFinding(
            { ...input.finding, ingredientIds: [] },
            [oneLinkPaper(paper, link)],
            input.selected,
            input.profile,
          ),
          `${expected.linkId}: scope mismatch`,
        ).toEqual({ direct: [], background: [] });
      } else if (expected.expectedUiResult === "background") {
        expect(split.direct, expected.linkId).toEqual([]);
        expect(linkIds(split, "background"), expected.linkId).toEqual([
          expected.linkId,
        ]);
      } else if (expected.expectedUiResult === "mixed") {
        expect(linkIds(split, "direct"), expected.linkId).toEqual([
          expected.linkId,
        ]);
        expect(split.background, expected.linkId).toEqual([]);
        const scopeMismatch = splitSupportingLiteratureForFinding(
          { ...input.finding, ingredientIds: [] },
          [oneLinkPaper(paper, link)],
          input.selected,
          input.profile,
        );
        expect(scopeMismatch.direct, `${expected.linkId}: scope mismatch`).toEqual(
          [],
        );
        expect(
          linkIds(scopeMismatch, "background"),
          `${expected.linkId}: scope mismatch`,
        ).toEqual([expected.linkId]);
      } else {
        expect(split, expected.linkId).toEqual({ direct: [], background: [] });
      }
    }
  });

  it("labels exact, mixed-scope, background, and excluded literature distinctly", () => {
    const expectedLabels: Record<ExpectedUiResult, string> = {
      direct: "v5.0 직접 일치 문헌",
      mixed: "v5.0 범위 일치 시 직접 문헌",
      background: "v5.0 배경 문헌",
      excluded: "결과 화면 제외 문헌",
    };
    for (const { linkId, expectedUiResult } of literaturePolicyMatrix) {
      expect(literatureStatusLabel(findLiteratureLink(linkId).link), linkId).toBe(
        expectedLabels[expectedUiResult],
      );
    }
  });

  it("keeps both Rule015 candidates excluded when no literature is applicable", () => {
    const rule015 = literaturePolicyMatrix.filter((entry) =>
      ["OTC-LIT-LINK-018", "OTC-LIT-LINK-019"].includes(entry.linkId),
    );
    expect(rule015).toHaveLength(2);
    for (const { linkId } of rule015) {
      const { split, link } = splitLink(linkId);
      expect(link.ruleId).toBe("OTC-RULE-015");
      expect(link.v51Classification.uiPolicy).toBe("exclude_from_result_ui");
      expect(split).toEqual({ direct: [], background: [] });
    }
  });

  it("does not turn an administration label into a released-rule literature link", () => {
    const childTylenol = runtimeProducts.find(
      (product) => product.itemSequence === "202200525",
    );
    const tylenol500 = runtimeProducts.find(
      (product) => product.itemSequence === "202106092",
    );
    if (!childTylenol || !tylenol500) {
      throw new Error("Missing Tylenol runtime fixtures");
    }
    expect(childTylenol.supportedReleasedRuleIds).toEqual([]);
    expect(childTylenol.supportedRuleTypes).toContain("minimum_interval");

    const rule004 = findLiteratureLink("OTC-LIT-LINK-006");
    expect(
      productLiteratureCoverage(
        childTylenol,
        [oneLinkPaper(rule004.paper, rule004.link)],
        releasedRules,
      ),
    ).toEqual({ v5Linked: 0, directCapable: 0 });
    expect(
      productLiteratureCoverage(
        tylenol500,
        [oneLinkPaper(rule004.paper, rule004.link)],
        releasedRules,
      ),
    ).toEqual({ v5Linked: 1, directCapable: 0 });

    const globalRule001 = findLiteratureLink("OTC-LIT-LINK-001");
    expect(
      productLiteratureCoverage(
        childTylenol,
        [oneLinkPaper(globalRule001.paper, globalRule001.link)],
        releasedRules,
      ),
    ).toEqual({ v5Linked: 1, directCapable: 1 });
    expect(
      productLiteratureCoverage(
        childTylenol,
        [oneLinkPaper(globalRule001.paper, globalRule001.link)],
        [],
      ),
    ).toEqual({ v5Linked: 0, directCapable: 0 });
    expect(productLiteratureCoverage(childTylenol, papers, releasedRules)).toEqual({
      v5Linked: 1,
      directCapable: 1,
    });
  });

  it("requires the Rule002 ibuprofen anchor for global NSAID literature coverage", () => {
    const ibuprofen = runtimeProducts.find(
      (product) => product.itemSequence === "198601920",
    );
    const naproxen = runtimeProducts.find(
      (product) => product.itemSequence === "197500016",
    );
    if (!ibuprofen || !naproxen) {
      throw new Error("Missing NSAID runtime fixtures");
    }
    const rule002 = findLiteratureLink("OTC-LIT-LINK-003");
    const rule002Literature = [oneLinkPaper(rule002.paper, rule002.link)];

    expect(
      productLiteratureCoverage(ibuprofen, rule002Literature, releasedRules),
    ).toEqual({ v5Linked: 1, directCapable: 0 });
    expect(
      productLiteratureCoverage(naproxen, rule002Literature, releasedRules),
    ).toEqual({ v5Linked: 0, directCapable: 0 });
  });

  it("fails closed for missing, contradictory, and structurally malformed classifications", () => {
    const { paper, link } = findLiteratureLink("OTC-LIT-LINK-001");
    const input = matchingInput(link);
    const valid = link.v51Classification;
    const malformedClassifications: ReadonlyArray<{
      name: string;
      value: unknown;
    }> = [
      { name: "missing", value: undefined },
      { name: "null", value: null },
      {
        name: "missing direct scope",
        value: { ...valid, directScope: undefined },
      },
      {
        name: "non-array scope member",
        value: {
          ...valid,
          directScope: { ...valid.directScope, ingredientIds: "ING-acetaminophen" },
        },
      },
      {
        name: "contradictory semantic policy",
        value: { ...valid, semanticClassification: "background_context" },
      },
      {
        name: "truthy string direct-label permission",
        value: { ...valid, uiDirectLabelAllowed: "true" },
      },
      {
        name: "truthy string expert-review flag",
        value: { ...valid, humanExpertReviewed: "false" },
      },
      {
        name: "expert-reviewed classification outside the current contract",
        value: { ...valid, humanExpertReviewed: true },
      },
      {
        name: "direct policy with an empty direct scope",
        value: {
          ...valid,
          directScope: {
            ingredientIds: [],
            productItemSequences: [],
            profileConditions: [],
            medicationTerms: [],
          },
        },
      },
      {
        name: "missing classification identity",
        value: { ...valid, classificationId: null },
      },
    ];

    for (const malformed of malformedClassifications) {
      const malformedLink = {
        ...link,
        v51Classification: malformed.value,
      } as unknown as SupportingLiteratureRuleLink;
      const malformedPaper = oneLinkPaper(paper, malformedLink);
      expect(
        splitSupportingLiteratureForFinding(
          input.finding,
          [malformedPaper],
          input.selected,
          input.profile,
        ),
        malformed.name,
      ).toEqual({ direct: [], background: [] });
      expect(literatureStatusSummary([malformedPaper]), malformed.name).toEqual({
        v5Linked: 0,
        directCapable: 0,
        backgroundOnly: 0,
        excluded: 1,
      });
      expect(literatureStatusLabel(malformedLink), malformed.name).toBe(
        "결과 화면 제외 문헌",
      );
      expect(
        productLiteratureCoverage(
          input.selected[0].product,
          [malformedPaper],
          releasedRules,
        ),
        malformed.name,
      ).toEqual({ v5Linked: 0, directCapable: 0 });
    }
  });

  it("requires a nonempty scope for mixed direct-capable links but permits empty background scope", () => {
    const mixed = findLiteratureLink("OTC-LIT-LINK-011");
    const mixedInput = matchingInput(mixed.link);
    const emptyScope = {
      ingredientIds: [],
      productItemSequences: [],
      profileConditions: [],
      medicationTerms: [],
    };
    const malformedMixedLink = {
      ...mixed.link,
      v51Classification: {
        ...mixed.link.v51Classification,
        directScope: emptyScope,
      },
    };
    expect(
      splitSupportingLiteratureForFinding(
        mixedInput.finding,
        [oneLinkPaper(mixed.paper, malformedMixedLink)],
        mixedInput.selected,
        mixedInput.profile,
      ),
    ).toEqual({ direct: [], background: [] });

    const background = findLiteratureLink("OTC-LIT-LINK-003");
    expect(background.link.v51Classification.directScope).toEqual(emptyScope);
    expect(literatureStatusSummary([oneLinkPaper(background.paper, background.link)]))
      .toEqual({
        v5Linked: 1,
        directCapable: 0,
        backgroundOnly: 1,
        excluded: 0,
      });
  });

  it("counts malformed homepage links as excluded without reading their classification", () => {
    expect(literatureHomepageStatusSummary(papers)).toEqual({
      v5Linked: 10,
      v5RuleCount: 9,
      directMatch: 1,
      conditionalDirect: 4,
      backgroundOnly: 5,
      excluded: 10,
    });

    const { paper, link } = findLiteratureLink("OTC-LIT-LINK-001");
    const malformedLinks = [
      { ...link, v51Classification: undefined },
      {
        ...link,
        v51Classification: {
          ...link.v51Classification,
          uiDirectLabelAllowed: "true",
        },
      },
      {
        ...link,
        v51Classification: {
          ...link.v51Classification,
          directScope: {
            ingredientIds: [],
            productItemSequences: [],
            profileConditions: [],
            medicationTerms: [],
          },
        },
      },
    ] as unknown as SupportingLiteratureRuleLink[];

    for (const malformedLink of malformedLinks) {
      expect(
        literatureHomepageStatusSummary([oneLinkPaper(paper, malformedLink)]),
      ).toEqual({
        v5Linked: 0,
        v5RuleCount: 0,
        directMatch: 0,
        conditionalDirect: 0,
        backgroundOnly: 0,
        excluded: 1,
      });
    }

    const pageSource = readFileSync(resolve(process.cwd(), "app/page.tsx"), "utf8");
    expect(pageSource).toContain("literatureHomepageStatusSummary");
    expect(pageSource).not.toContain("const classification = link.v51Classification");
  });

  it("renders adult Rule008 literature as background with the v5.1 boundary", () => {
    const { paper, link } = findLiteratureLink("OTC-LIT-LINK-011");
    const input = matchingInput(link);
    input.profile.ageYears = 30;
    const split = splitSupportingLiteratureForFinding(
      input.finding,
      [oneLinkPaper(paper, link)],
      input.selected,
      input.profile,
    );
    expect(split.direct).toEqual([]);
    expect(split.background).toHaveLength(1);

    const html = renderToStaticMarkup(
      createElement(LiteratureCard, {
        match: split.background[0],
        scopeLabel: "현재 판정의 직접 근거가 아님",
        kind: "background",
      }),
    );
    expect(html).toContain("v5.0 배경 문헌");
    expect(html).not.toContain("v5.0 범위 일치 시 직접 문헌");
    expect(html).toContain(link.v51Classification.classificationReasonKo);
    expect(html).toContain(link.v51Classification.uiBoundaryKo);
    expect(html).not.toContain(link.selectionReasonKo);
  });

  it("exposes only emitted links through the presentation and card-rendering contract", () => {
    const exposedMatches = literaturePolicyMatrix.flatMap(({ linkId }) => {
      const { split } = splitLink(linkId);
      return [...split.direct, ...split.background];
    });
    const exposedLinkIds = exposedMatches.map(({ link }) => link.linkId).sort();
    const emittedLinkIds = literaturePolicyMatrix
      .filter(({ lineageStatus }) => lineageStatus === "v50_emitted")
      .map(({ linkId }) => linkId)
      .sort();
    const rejectedLinkIds = new Set<string>(
      literaturePolicyMatrix
        .filter(({ expectedUiResult }) => expectedUiResult === "excluded")
        .map(({ linkId }) => linkId),
    );
    const rejectedUrls = new Set(
      [...rejectedLinkIds].map((linkId) => findLiteratureLink(linkId).paper.url),
    );

    expect(exposedLinkIds).toEqual(emittedLinkIds);
    expect(
      exposedMatches.some(({ link }) => rejectedLinkIds.has(link.linkId)),
    ).toBe(false);
    expect(exposedMatches.some(({ paper }) => rejectedUrls.has(paper.url))).toBe(
      false,
    );

    const componentSource = readFileSync(
      resolve(process.cwd(), "src/components/otc-product-safety-client.tsx"),
      "utf8",
    );
    expect(componentSource.match(/<LiteratureCard\b/g) ?? []).toHaveLength(2);
    expect(componentSource).toContain(
      "literatureByFinding.get(finding.findingId)?.direct",
    );
    expect(componentSource).toContain(
      "literatureByFinding.get(finding.findingId)?.background",
    );
    expect(componentSource).not.toContain("outsideV50LiteratureForFinding");
    expect(componentSource).not.toContain("v50CorpusStatus");
  });
});

import { describe, expect, it } from "vitest";

import {
  buildQuickCheckSelection,
  buildSelectedProducts,
  inputSupportStatusMessage,
  quickChecks,
  searchRuntime,
  type OtcRuntime,
} from "@/src/components/otc-product-safety-client";
import { evaluateOtcSafety } from "@/src/lib/otc/engine";
import {
  createSelectedProductDraft,
  parseSelectedProductDraft,
  selectedProductToDraft,
} from "@/src/lib/otc/form-state";
import {
  buildProductSupportSummary,
  productsForTherapeuticClass,
  ruleEvidenceForFinding,
} from "@/src/lib/otc/presentation";
import type { OtcProduct } from "@/src/lib/otc/schema";
import runtimeData from "@/src/generated/otc-runtime.json";

const product = (productId: string, productName: string): OtcProduct => ({
  productId,
  itemSequence: productId,
  productName,
  classification: "일반의약품",
  authorizationStatus: "active",
  doseUnitLabel: "정",
  ingredients: [],
  flags: [],
  evidence: {
    sourceId: "TEST-SOURCE",
    locator: "검증용 원문 위치",
    url: "https://example.test/source",
  },
});

const runtime: OtcRuntime = {
  schemaVersion: "1.0.0",
  generatedAt: "2026-07-14",
  researchDirection: "korean_otc_product_safety",
  releaseReady: false,
  rulesReleased: 0,
  releasedRuleTypes: [],
  releasedRules: [],
  products: [product("P1", "검증제품1"), product("P2", "검증제품2")],
  officialCandidates: [
    { candidateId: "C1", productName: "검증대기감기정", className: "종합감기약", status: "authorization_pending" },
  ],
};

describe("product-name search flow", () => {
  it("distinguishes the support matrix from the current input coverage", () => {
    expect(
      inputSupportStatusMessage({
        selectedCount: 2,
        supportedCount: 1,
        hasCurrentInput: false,
        hasCoverageGap: false,
        hasInputIssue: false,
      }),
    ).toBe("적으시면 담은 약 2개 가운데 1개에서 봐요.");
    expect(
      inputSupportStatusMessage({
        selectedCount: 2,
        supportedCount: 2,
        hasCurrentInput: true,
        hasCoverageGap: true,
        hasInputIssue: false,
      }),
    ).toBe(
      "담은 약 2개 가운데 2개에서 보고, 나머지는 확인하지 못한 범위로 남깁니다.",
    );
    expect(
      inputSupportStatusMessage({
        selectedCount: 2,
        supportedCount: 2,
        hasCurrentInput: true,
        hasCoverageGap: false,
        hasInputIssue: false,
      }),
    ).toBe("적으신 내용을 담은 약 2개 가운데 2개에서 봐요.");
    expect(
      inputSupportStatusMessage({
        selectedCount: 1,
        supportedCount: 1,
        hasCurrentInput: true,
        hasCoverageGap: false,
        hasInputIssue: true,
      }),
    ).toBe("적으신 값을 고쳐야 볼 수 있어요.");
  });

  it("shows no results before the user searches", () => {
    expect(searchRuntime(runtime, "")).toEqual({ verified: [], candidates: [] });
  });

  it("returns an official candidate separately from selectable verified products", () => {
    expect(searchRuntime(runtime, "감기")).toEqual({ verified: [], candidates: runtime.officialCandidates });
  });

  it("does not convert an unsupported name into a guessed product", () => {
    expect(searchRuntime(runtime, "없는제품")).toEqual({ verified: [], candidates: [] });
  });

  it("normalizes spaces, brackets, and punctuation in a product name", () => {
    const fullRuntime = runtimeData as OtcRuntime;
    expect(searchRuntime(fullRuntime, "타이레놀정 500 밀리그람").verified[0]?.productId).toBe(
      "MFDS-202106092",
    );
  });

  it("finds products by ingredient and therapeutic-class aliases", () => {
    const fullRuntime = runtimeData as OtcRuntime;
    expect(
      searchRuntime(fullRuntime, "아세트아미노펜").verified.some(
        (item) => item.productId === "MFDS-202106092",
      ),
    ).toBe(true);
    expect(
      searchRuntime(fullRuntime, "감기약").verified.some(
        (item) => item.productId === "MFDS-196800036",
      ),
    ).toBe(true);
    expect(
      searchRuntime(fullRuntime, "소화제").verified.some(
        (item) => item.productId === "MFDS-198700405",
      ),
    ).toBe(true);
  });

  it("builds a quick-check selection in requested order without unknowns or duplicates", () => {
    expect(buildSelectedProducts(runtime, ["P2", "UNKNOWN", "P1", "P2"])).toEqual([
      { product: runtime.products[1], unitsPerDose: 1, dosesPerDay: 1 },
      { product: runtime.products[0], unitsPerDose: 1, dosesPerDay: 1 },
    ]);
  });

  it("keeps a newly selected product's required dose fields empty until confirmed", () => {
    const draft = createSelectedProductDraft(runtime.products[0]);
    expect(draft.unitsPerDose).toBe("");
    expect(draft.dosesPerDay).toBe("");

    const parsed = parseSelectedProductDraft(draft);
    expect(Number.isNaN(parsed.unitsPerDose)).toBe(true);
    expect(Number.isNaN(parsed.dosesPerDay)).toBe(true);
    expect(parsed.hoursSincePreviousDose).toBeUndefined();
    expect(parsed.continuousDays).toBeUndefined();
  });

  it("round-trips a demo selection through string drafts without changing values", () => {
    const selected = {
      product: runtime.products[0],
      unitsPerDose: 1.5,
      dosesPerDay: 3,
      hoursSincePreviousDose: 2,
      continuousDays: 4,
    };
    expect(parseSelectedProductDraft(selectedProductToDraft(selected))).toEqual(selected);
  });

  it("keeps every MFDS-verified runtime product discoverable by therapeutic class", () => {
    const fullRuntime = runtimeData as OtcRuntime;
    expect(productsForTherapeuticClass(fullRuntime.products, "전체")).toHaveLength(13);
    expect(new Set(fullRuntime.products.map((item) => item.therapeuticClass))).toEqual(
      new Set(["해열진통제", "종합감기약", "위장관 일반의약품", "외용 소염진통제", "항히스타민제"]),
    );
  });

  it("exposes the exact support scope for all 13 verified products", () => {
    const fullRuntime = runtimeData as OtcRuntime;
    const releasedRuleTypes = new Set(fullRuntime.releasedRuleTypes);
    const summaries = fullRuntime.products.map((item) => ({
      productName: item.productName,
      ...buildProductSupportSummary(item, releasedRuleTypes),
    }));
    const doseOnly = summaries.filter(
      (summary) => summary.summaryKo === "용량만 확인 가능",
    );
    const doseAndIntervalOnly = summaries.filter(
      (summary) => summary.summaryKo === "용량·간격만 확인 가능",
    );
    const doseWithConditions = summaries.filter(
      (summary) => summary.summaryKo === "용량 외 조건도 확인 가능",
    );
    const doseAndIntervalWithConditions = summaries.filter(
      (summary) => summary.summaryKo === "용량·간격 외 조건도 확인 가능",
    );

    expect(doseOnly).toHaveLength(9);
    expect(doseAndIntervalOnly.map((summary) => summary.productName)).toEqual([
      "어린이타이레놀현탁액(아세트아미노펜)",
    ]);
    expect(doseWithConditions.map((summary) => summary.productName)).toEqual([
      "어린이부루펜시럽(이부프로펜)",
      "판콜에이내복액",
    ]);
    expect(
      doseAndIntervalWithConditions.map((summary) => summary.productName),
    ).toEqual([
      "타이레놀정500밀리그람(아세트아미노펜)",
    ]);
    expect(doseAndIntervalWithConditions[0].conditionLabels).toEqual([
      "연령",
      "정기 음주",
      "간질환",
      "긴급 증상",
    ]);
    expect(
      summaries.reduce((sum, item) => sum + item.supportedCheckTypeCount, 0),
    ).toBe(26);
    expect(
      summaries.reduce(
        (sum, item) => sum + item.releasedRuleBindingCount,
        0,
      ),
    ).toBe(13);
    expect(
      summaries.reduce(
        (sum, item) => sum + item.administrationConstraintCount,
        0,
      ),
    ).toBe(32);

    const dexibuprofen = fullRuntime.products.find(
      (item) => item.itemSequence === "201110646",
    );
    expect(dexibuprofen).toBeTruthy();
    expect(
      buildProductSupportSummary(dexibuprofen!, releasedRuleTypes),
    ).toEqual(
      expect.objectContaining({
        supportedCheckTypeCount: 1,
        releasedRuleBindingCount: 0,
        administrationConstraintCount: 3,
      }),
    );
  });

  it("offers varied examples with a real deterministic result and no input issues", () => {
    const fullRuntime = runtimeData as OtcRuntime;
    expect(quickChecks).toHaveLength(7);
    expect(quickChecks.map((item) => item.kind)).toEqual([
      "duplicate_ingredient",
      "duplicate_class",
      "authorization_limit",
      "minimum_interval",
      "condition",
      "medication",
      "unsupported",
    ]);
    for (const quickCheck of quickChecks) {
      const selected = buildQuickCheckSelection(fullRuntime, quickCheck);
      const profile = {
        medications: [],
        redFlagSymptoms: [],
        ...quickCheck.profilePatch,
      };
      const result = evaluateOtcSafety(
        selected,
        profile,
        { releasedRules: fullRuntime.releasedRules ?? [] },
      );
      expect(result.inputIssues, quickCheck.label).toEqual([]);
      if (quickCheck.expectedRuleType === null) {
        expect(result.findings, quickCheck.label).toEqual([]);
        if (quickCheck.expectedCoverageGap) {
          expect(result.coverageGaps.length, quickCheck.label).toBeGreaterThan(0);
        }
      } else {
        expect(result.findings.map((finding) => finding.ruleType), quickCheck.label).toContain(
          quickCheck.expectedRuleType,
        );
        const matchedFinding = result.findings.find(
          (finding) => finding.ruleType === quickCheck.expectedRuleType,
        );
        expect(matchedFinding, quickCheck.label).toBeTruthy();
        if (matchedFinding?.decisionBasis === "released_rule") {
          expect(
            fullRuntime.releasedRules
              ?.find((rule) => rule.ruleId === matchedFinding.ruleId)
              ?.evidence[0]?.excerptKo,
            quickCheck.label,
          ).toBeTruthy();
        } else {
          expect(matchedFinding?.decisionBasis, quickCheck.label).toBe(
            "administration_constraint",
          );
          expect(matchedFinding?.ruleId, quickCheck.label).toMatch(/^ADMIN-/);
          expect(matchedFinding?.ruleEvidence ?? [], quickCheck.label).toEqual([]);
          expect(
            matchedFinding?.evidence[0],
            quickCheck.label,
          ).toEqual(
            expect.objectContaining({ sourceId: "MFDS-NEDRUG-DETAIL" }),
          );
        }
      }
    }
  });

  it("shows the digestive-medicine example as an explicit coverage gap", () => {
    const fullRuntime = runtimeData as OtcRuntime;
    const quickCheck = quickChecks.find((item) => item.kind === "unsupported");
    expect(quickCheck).toBeTruthy();
    const selected = buildSelectedProducts(fullRuntime, quickCheck!.productIds);
    const result = evaluateOtcSafety(
      selected,
      { medications: [], redFlagSymptoms: [] },
      { releasedRules: fullRuntime.releasedRules ?? [] },
    );

    expect(result.findings).toEqual([]);
    expect(result.coverageGaps).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ ruleType: "duplicate_ingredient" }),
      ]),
    );
  });

  it("feeds same-rule runtime evidence into the representative product panel", () => {
    const fullRuntime = runtimeData as OtcRuntime;
    const selected = buildSelectedProducts(fullRuntime, [
      "MFDS-196800036",
      "MFDS-202200525",
    ]);
    const result = evaluateOtcSafety(
      selected,
      { medications: [], redFlagSymptoms: [] },
      { releasedRules: fullRuntime.releasedRules ?? [] },
    );
    const finding = result.findings.find(
      (candidate) => candidate.ruleId === "OTC-RULE-001",
    );
    expect(finding).toBeTruthy();

    const display = ruleEvidenceForFinding(
      finding!,
      selected,
      fullRuntime.releasedRules?.find(
        (rule) => rule.ruleId === finding!.ruleId,
      )?.evidence ?? [],
    );
    expect(display.evidence).toBeUndefined();
    expect(display.direct).toEqual([]);
    expect(display.representative).toEqual([
      expect.objectContaining({
        ruleId: "OTC-RULE-001",
        itemSequence: "202106092",
      }),
    ]);
  });
});

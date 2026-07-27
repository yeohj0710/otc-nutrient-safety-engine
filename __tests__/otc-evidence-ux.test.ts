import { describe, expect, it } from "vitest";

import literatureData from "@/src/generated/otc-supporting-literature.json";
import {
  buildFindingContext,
  formatEvidenceSource,
  groupCoverageGaps,
  literatureRelationLabel,
  ruleEvidenceForFinding,
  supportingLiteratureForFinding,
  type SupportingLiterature,
} from "@/src/lib/otc/presentation";
import type {
  EvaluationCoverageGap,
  OtcProduct,
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

describe("OTC evidence presentation", () => {
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

    expect(ruleEvidenceForFinding(finding, selected, [representative, direct])).toEqual({
      evidence: direct,
      productMatch: "all",
    });
    expect(ruleEvidenceForFinding(finding, selected, [representative])).toEqual({
      evidence: representative,
      productMatch: "none",
    });
    const secondProduct = { ...product, productId: "P2", itemSequence: "2" };
    expect(
      ruleEvidenceForFinding(
        { ...finding, productIds: ["P1", "P2"] },
        [...selected, { product: secondProduct, unitsPerDose: 1, dosesPerDay: 1 }],
        [direct],
      ),
    ).toEqual({ evidence: direct, productMatch: "partial" });
  });

  it("matches supporting papers by rule and ingredient without changing the finding", () => {
    const finding: SafetyFinding = {
      findingId: "sedative-medication:P1",
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
      { medications: ["졸피뎀"], redFlagSymptoms: [] },
    );
    expect(matched.map((item) => item.pmid)).toContain("23747192");
    // 다른 규칙 유형에 붙은 문헌은 이 판정으로 넘어오지 않는다.
    expect(matched.map((item) => item.pmid)).not.toContain("20178131");
    expect(finding.evidence).toEqual([]);
  });

  it("does not present a pregnancy-only paper as lactation evidence", () => {
    const finding: SafetyFinding = {
      findingId: "pregnancy:P1",
      ruleType: "pregnancy_lactation",
      severity: "high",
      titleKo: "임신·수유 주의",
      detailKo: "검증 상세",
      nextActionKo: "상담하세요.",
      productIds: ["P1"],
      ingredientIds: ["ING-ibuprofen"],
      evidence: [],
    };
    const papers = literatureData as SupportingLiterature[];
    const lactationOnly = supportingLiteratureForFinding(finding, papers, {
      lactating: true,
      medications: [],
      redFlagSymptoms: [],
    });
    const pregnancy = supportingLiteratureForFinding(finding, papers, {
      pregnant: true,
      medications: [],
      redFlagSymptoms: [],
    });

    expect(lactationOnly.map((paper) => paper.pmid)).not.toContain("39714827");
    expect(pregnancy.map((paper) => paper.pmid)).toContain("39714827");
  });

  it("shows the most rule-specific paper first", () => {
    const finding: SafetyFinding = {
      findingId: "max-daily-dose:P1",
      ruleType: "max_daily_dose",
      severity: "high",
      titleKo: "하루 최대량 초과",
      detailKo: "검증 상세",
      nextActionKo: "상담하세요.",
      productIds: ["P1"],
      ingredientIds: ["ING-acetaminophen"],
      evidence: [],
    };

    const matched = supportingLiteratureForFinding(
      finding,
      literatureData as SupportingLiterature[],
    );
    // 29516533 은 이 규칙 하나에만, 26149538 은 두 규칙에 연결돼 있다.
    expect(matched[0].pmid).toBe("29516533");
    expect(matched.map((paper) => paper.pmid)).toContain("26149538");
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

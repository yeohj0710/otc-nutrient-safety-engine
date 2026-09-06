import { describe, expect, it } from "vitest";
import data from "@/src/generated/otc-runtime.json";
import { parseOtcExplainInput } from "@/src/lib/ai/otc-explain-input";
import { buildOtcCounselingContext, validateOtcDiscussion } from "@/src/lib/ai/otc-counseling-context";
import type { UserProfile } from "@/src/lib/otc/schema";

// "관련 문헌 없음", "입력 정보 부족", "연구 대상과 차이"를 상담 근거에서 구분하는지 본다.
// 검토 문헌은 숨기지 않고 이유를 붙여 배경으로 내리고, 검토 문헌이 없는 판정에는
// 추가 선별 후보를 그 지위 그대로 붙인다.

const productId = (part: string) => data.products.find((product) => product.productName.includes(part))!.productId;
const tylenol = "MFDS-202106092";
const brufen = "MFDS-198601920";
type Selected = { productId: string; unitsPerDose: number; dosesPerDay: number; hoursSincePreviousDose?: number };
const emptyProfile: UserProfile = { medications: [], redFlagSymptoms: [] };

function context(selected: Selected[], profile: Partial<UserProfile> = {}) {
  const input = parseOtcExplainInput({ selected, profile: { ...emptyProfile, ...profile } })!;
  expect(input).not.toBeNull();
  return buildOtcCounselingContext(input.evaluation, input.selected, input.profile);
}
const row = (ctx: ReturnType<typeof context>, ruleId: string) => {
  const found = ctx.evidence.find((item) => item.ruleId === ruleId);
  expect(found, ruleId).toBeDefined();
  return found!;
};

describe("검토 문헌의 적용 조건 구분", () => {
  const duplicate: Selected[] = [tylenol, productId("판콜에이")].map((id) => ({ productId: id, unitsPerDose: 1, dosesPerDay: 1 }));

  it("keeps the registered duplicate-ingredient paper when age is unknown", () => {
    const paper = row(context(duplicate), "OTC-RULE-001").papers.find((item) => item.pmid === "30306812");
    expect(paper).toBeDefined();
    expect(paper!.relation).toBe("background");
    expect(paper!.status).toBe("missing_information");
    expect(paper!.limitation).toContain("나이 정보가 없어");
    expect(paper!.limitation).toContain("나이 12세 이상");
    expect(row(context(duplicate), "OTC-RULE-001").literature.status).toBe("reviewed_conditional");
  });

  it("distinguishes an unmatched age from missing information", () => {
    const child = row(context(duplicate, { ageYears: 8 }), "OTC-RULE-001").papers.find((item) => item.pmid === "30306812")!;
    expect(child.relation).toBe("background");
    expect(child.status).toBe("population_difference");
    expect(child.limitation).toContain("연구 대상과 다릅니다");
    const adult = row(context(duplicate, { ageYears: 35 }), "OTC-RULE-001").papers.find((item) => item.pmid === "30306812")!;
    expect(adult.relation).toBe("direct");
    expect(row(context(duplicate, { ageYears: 35 }), "OTC-RULE-001").literature.status).toBe("direct");
  });

  it("applies the same split to conditional-direct papers (renal rule, age unknown vs adult vs child)", () => {
    const syrup: Selected[] = [{ productId: brufen, unitsPerDose: 5, dosesPerDay: 3 }];
    const unknownAge = row(context(syrup, { kidneyDisease: true }), "OTC-RULE-008").papers.find((item) => item.pmid === "33662136")!;
    expect(unknownAge.status).toBe("missing_information");
    expect(unknownAge.limitation).toContain("나이 정보가 없어");
    expect(unknownAge.limitation).toContain("나이 18세 이하");
    const adult = row(context(syrup, { kidneyDisease: true, ageYears: 45 }), "OTC-RULE-008").papers.find((item) => item.pmid === "33662136")!;
    expect(adult.status).toBe("population_difference");
    expect(adult.limitation).toContain("입력한 나이 조건이 연구 대상과 다릅니다");
    const child = row(context(syrup, { kidneyDisease: true, ageYears: 9 }), "OTC-RULE-008").papers.find((item) => item.pmid === "33662136")!;
    expect(child.relation).toBe("direct");
  });

  it("treats a medication class word as missing information, not as a population difference", () => {
    const syrup: Selected[] = [{ productId: brufen, unitsPerDose: 5, dosesPerDay: 3 }];
    const generic = row(context(syrup, { ageYears: 40, medications: ["쿠마린계 항응고제"] }), "OTC-RULE-012").papers.find((item) => item.pmid === "39551938")!;
    expect(generic.status).toBe("missing_information");
    expect(generic.limitation).toContain("계열 이름만");
    const warfarin = row(context(syrup, { ageYears: 40, medications: ["와파린"] }), "OTC-RULE-012").papers.find((item) => item.pmid === "39551938")!;
    expect(warfarin.relation).toBe("direct");
  });
});

describe("추가 선별 후보 연결", () => {
  it("attaches agent-screened candidates to rules that have no reviewed literature", () => {
    const alcohol = row(context([{ productId: tylenol, unitsPerDose: 1, dosesPerDay: 3 }], { ageYears: 40, alcohol: true }), "OTC-RULE-011");
    expect(alcohol.literature.status).toBe("candidate_only");
    expect(alcohol.literature.headlineKo).toContain("추가 선별 후보");
    expect(alcohol.papers.length).toBeGreaterThan(0);
    for (const paper of alcohol.papers) {
      expect(paper.relation).toBe("candidate");
      expect(paper.reviewStatus).toBe("agent_screened_candidate");
      expect(paper.statusKo).toContain("추가 선별 후보");
      expect(paper.population).toMatch(/[가-힣]/);
      expect(paper.exposure).toMatch(/[가-힣]/);
      expect(paper.limitation).toContain("사람 전문가 검토");
    }
    expect(alcohol.papers[0].status).toBe("candidate_scope_match");
    expect(alcohol.papers.some((paper) => paper.pmid === "22851428")).toBe(true);
  });

  it("marks candidates as background when the rule topic is only adjacent (sedative co-medication)", () => {
    const sedative = row(context([{ productId: productId("판콜에이"), unitsPerDose: 1, dosesPerDay: 3 }], { ageYears: 40, medications: ["수면제"] }), "OTC-RULE-013");
    expect(sedative.papers.length).toBeGreaterThan(0);
    for (const paper of sedative.papers) expect(paper.status).toBe("candidate_background");
    expect(sedative.papers[0].limitation).toContain("함께 먹은 경우는 연구하지 않았습니다");
  });

  it("connects authorization dosing constraints to same-ingredient candidates and explains empty ones", () => {
    const panpirin = context([{ productId: productId("판피린"), unitsPerDose: 1, dosesPerDay: 5 }], { ageYears: 40 });
    const constraint = panpirin.evidence.find((item) => item.decisionBasis === "administration_constraint" && item.ruleType === "max_daily_dose")!;
    expect(constraint).toBeDefined();
    expect(constraint.papers.some((paper) => paper.pmid === "39825523")).toBe(true);
    expect(constraint.literature.status).toBe("candidate_only");

    const digestive = context([{ productId: "MFDS-198700405", unitsPerDose: 1, dosesPerDay: 5 }]);
    const enzyme = digestive.evidence.find((item) => item.ruleType === "max_daily_dose")!;
    expect(enzyme.papers).toEqual([]);
    expect(enzyme.literature.status).toBe("none");
    expect(enzyme.literature.headlineKo).toContain("연결한 문헌이 없습니다");
    expect(enzyme.literature.detailKo).toContain("허가원문");
  });

  it("reports missing input for candidates with age conditions", () => {
    const noAge = row(context([{ productId: tylenol, unitsPerDose: 1, dosesPerDay: 3 }], { alcohol: true }), "OTC-RULE-011");
    expect(noAge.papers[0].status).toBe("candidate_missing_information");
    expect(noAge.papers[0].limitation).toContain("나이 정보가 없어");
  });
});

describe("상담문 검사", () => {
  it("requires candidate paragraphs to say they are candidates and blocks verified-evidence claims", () => {
    const ctx = context([{ productId: tylenol, unitsPerDose: 1, dosesPerDay: 3 }], { ageYears: 40, alcohol: true });
    const evidence = row(ctx, "OTC-RULE-011");
    const pmid = evidence.papers[0].pmid;
    expect(validateOtcDiscussion([{ ruleId: "OTC-RULE-011", pmids: [pmid], text: "술을 마시는 성인의 임상시험을 모은 연구에서 간효소가 오르지 않았습니다." }], ctx)).toContain("missing_candidate_status");
    expect(validateOtcDiscussion([{ ruleId: "OTC-RULE-011", pmids: [pmid], text: "검토를 마친 문헌에서 간효소가 오르지 않았습니다. 후보입니다." }], ctx)).toContain("candidate_overreach");
    expect(validateOtcDiscussion([{ ruleId: "OTC-RULE-011", pmids: [pmid], text: "추가 선별 후보인 이 연구는 술을 마시는 성인이 며칠 동안 먹었을 때 간효소 변화가 위약과 차이가 없었다고 보고했지만, 오래 먹는 경우와 간질환이 있는 경우는 다뤄지지 않았습니다." }], ctx)).toEqual([]);
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import data from "@/src/generated/otc-runtime.json";
import { parseOtcExplainInput } from "@/src/lib/ai/otc-explain-input";
import {
  buildOtcCounselingContext,
  buildOtcGroundingLines,
  groundingTextForRow,
  validateOtcDiscussion,
} from "@/src/lib/ai/otc-counseling-context";
import { splitOtcNdjson, type OtcExplainEvent } from "@/src/lib/ai/otc-explain-stream";
import type { UserProfile } from "@/src/lib/otc/schema";

vi.mock("server-only", () => ({}));

// 두 가지를 본다.
//  1. 제품 하나가 하루에 넣는 성분량을 자료로 넘기는지. 예전에는 합계만 넘겨서
//     "판콜에이에서 900 mg" 같은 문장이 심판의 unsupported_number 로 걸렸고,
//     프로덕션에서 설명 전체가 버려졌다.
//  2. 요약과 판정별 문단을 따로 만들어 끝나는 것부터 흘려보내는지, 문단 하나가
//     걸려도 나머지가 살아남는지.

const tylenol = "MFDS-202106092";
const pankol = data.products.find((product) => product.productName.includes("판콜에이"))!.productId;
const emptyProfile: UserProfile = { medications: [], redFlagSymptoms: [] };
const request = {
  selected: [
    { productId: tylenol, unitsPerDose: 2, dosesPerDay: 4 },
    { productId: pankol, unitsPerDose: 1, dosesPerDay: 3 },
  ],
  profile: { ...emptyProfile, ageYears: 35, alcohol: true },
};

function context() {
  const input = parseOtcExplainInput(request)!;
  expect(input).not.toBeNull();
  return buildOtcCounselingContext(input.evaluation, input.selected, input.profile);
}

describe("제품별 하루 성분량", () => {
  it("hands the model each product's own daily amount instead of making it multiply", () => {
    const ctx = context();
    const tylenolUse = ctx.productUse.find((item) => item.name.includes("타이레놀"))!;
    const acetaminophen = tylenolUse.dailyContribution.find((row) => row.ingredientId === "ING-acetaminophen")!;
    expect(acetaminophen.dailyAmount).toBe(4000);
    expect(acetaminophen.dailyAmountKo).toContain("500 mg");
    expect(acetaminophen.dailyAmountKo).toContain("= 4000 mg");
    const pankolUse = ctx.productUse.find((item) => item.name.includes("판콜에이"))!;
    expect(pankolUse.dailyContribution.find((row) => row.ingredientId === "ING-acetaminophen")!.dailyAmount).toBe(900);
    // 합계도 그대로 있다. 둘을 함께 줘야 "어느 약에서 얼마, 합쳐 얼마" 를 쓸 수 있다.
    expect(ctx.dailyIngredientTotals["ING-acetaminophen"].amount).toBe(4900);
  });

  it("accepts a paragraph that names one product's daily amount", () => {
    const ctx = context();
    const text =
      "타이레놀정500밀리그람에서 4000 mg, 판콜에이내복액에서 900 mg이 들어가 아세트아미노펜 하루 총량이 4900 mg입니다.";
    expect(validateOtcDiscussion([{ ruleId: "OTC-RULE-001", pmids: [], text }], ctx)).toEqual([]);
    // 자료에 없는 양은 그대로 막는다.
    expect(
      validateOtcDiscussion([{ ruleId: "OTC-RULE-001", pmids: [], text: "판콜에이내복액에서 1200 mg이 들어갑니다." }], ctx),
    ).toContain("unsupported_unit");
  });
});

describe("모델 없이 읽는 판정 설명", () => {
  it("ties the product dose, the authorization number and the paper to the input", () => {
    const ctx = context();
    const row = ctx.evidence.find((item) => item.ruleId === "OTC-RULE-001")!;
    const text = groundingTextForRow(row);
    expect(text).toContain("타이레놀");
    expect(text).toContain("4000 mg");
    expect(text).toContain("900 mg");
    expect(text).toContain("PMID");
    expect(text).toContain(row.literature.headlineKo);
    expect(buildOtcGroundingLines(ctx.evidence).length).toBeGreaterThan(0);
  });

  it("says why a paper is not direct evidence when the input is short", () => {
    const input = parseOtcExplainInput({ ...request, profile: emptyProfile })!;
    const ctx = buildOtcCounselingContext(input.evaluation, input.selected, input.profile);
    const text = groundingTextForRow(ctx.evidence.find((item) => item.ruleId === "OTC-RULE-001")!);
    expect(text).toContain("입력 정보 부족");
    expect(text).toContain("그대로 적용하지 못하는 까닭");
    expect(text).toContain("나이 정보가 없어");
    expect(text).toContain("나이 12세 이상");
  });
});

type ParseCall = { instructions: string };
const calls: ParseCall[] = [];
let reply: (call: ParseCall, index: number) => Promise<unknown> = async () => ({ output_parsed: null });

vi.mock("openai", () => ({
  default: class {
    responses = {
      parse: (options: ParseCall) => {
        const index = calls.length;
        calls.push(options);
        return reply(options, index);
      },
    };
  },
}));

const { streamOtcExplanation } = await import("@/src/lib/ai/explainOtcFindings");

function explainInput(patient: Partial<UserProfile> = {}) {
  const input = parseOtcExplainInput({ ...request, profile: { ...request.profile, ...patient } })!;
  return { ...input, productNames: input.productNames, profileSummary: input.profileSummary };
}

describe("요약과 판정별 문단을 나눠 만들기", () => {
  beforeEach(() => {
    calls.length = 0;
    process.env.OPENAI_API_KEY = "sk-test-key";
  });

  it("asks the summary and each rule separately and streams what finishes first", async () => {
    reply = async (call) =>
      call.instructions.includes("summaryTitle 과 summaryParagraph 만")
        ? { output_parsed: { summaryTitle: "겹친 성분과 하루 총량", summaryParagraph: "아세트아미노펜이 두 제품에서 겹칩니다." } }
        : { output_parsed: { text: "이 판정에 붙은 연구는 성인을 대상으로 했습니다.", pmids: [] } };

    const events: OtcExplainEvent[] = [];
    const response = await streamOtcExplanation(explainInput({ ageYears: 41 }), (event) => events.push(event));
    // 요약 1 + 판정별 최대 3. 한 호출로 몰지 않는다.
    expect(calls.length).toBeGreaterThan(1);
    expect(calls.length).toBeLessThanOrEqual(4);
    expect(events[0].type).toBe("interim");
    expect(events.some((event) => event.type === "summary")).toBe(true);
    expect(events.some((event) => event.type === "discussion")).toBe(true);
    expect(response.ok).toBe(true);
    if (response.ok) {
      expect(response.explanation.summaryTitle).toBe("겹친 성분과 하루 총량");
      expect(response.evidenceDiscussion?.length).toBeGreaterThan(0);
      // 경보 등급은 엔진 값에서 그대로 만든다. 모델이 고르지 않는다.
      for (const alert of response.explanation.topAlerts) expect(alert.ruleId).toMatch(/^OTC-RULE-/);
    }
  });

  it("drops only the paragraph the referee stops", async () => {
    let ruleCall = 0;
    reply = async (call) => {
      if (call.instructions.includes("summaryTitle 과 summaryParagraph 만")) {
        return { output_parsed: { summaryTitle: "겹친 성분", summaryParagraph: "두 제품에 같은 성분이 있습니다." } };
      }
      ruleCall += 1;
      return ruleCall === 1
        ? { output_parsed: { text: "이 조합은 안전합니다.", pmids: [] } }
        : { output_parsed: { text: "이 판정에 붙은 연구는 성인을 대상으로 했습니다.", pmids: [] } };
    };
    const response = await streamOtcExplanation(explainInput({ ageYears: 41 }));
    expect(response.ok).toBe(true);
    if (response.ok) {
      expect(response.evidenceDiscussion?.every((item) => !item.text.includes("안전합니다"))).toBe(true);
      expect(response.evidenceDiscussion?.length).toBeGreaterThan(0);
    }
  });

  it("keeps the whole summary out when the referee stops it", async () => {
    reply = async (call) =>
      call.instructions.includes("summaryTitle 과 summaryParagraph 만")
        ? { output_parsed: { summaryTitle: "괜찮습니다", summaryParagraph: "문제없습니다." } }
        : { output_parsed: { text: "이 판정에 붙은 연구는 성인을 대상으로 했습니다.", pmids: [] } };
    const response = await streamOtcExplanation(explainInput({ ageYears: 42 }));
    expect(response.ok).toBe(false);
    if (!response.ok) expect(response.reason).toBe("refereed_out");
  });

  it("reads a streamed line back with its slot", () => {
    const { events, rest } = splitOtcNdjson(
      '{"type":"summary","summaryTitle":"t","summaryParagraph":"p","elapsedMs":30000}\nbroken\n{"type":"resu',
    );
    expect(events.map((event) => event.type)).toEqual(["summary"]);
    expect(rest).toBe('{"type":"resu');
  });
});

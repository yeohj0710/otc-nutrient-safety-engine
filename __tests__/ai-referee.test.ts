import { describe, expect, it } from "vitest";

import { refereeExplanation } from "@/src/lib/ai/referee";
import type { AiExplanation } from "@/src/lib/ai/schema";

// 엔진이 심각도를 판정하는 사이트라, 심판이 막아야 하는 것은 "모델이 판단했다"가
// 아니라 "엔진이 하지 않은 판단을 모델이 더했다"이다. 등급 부풀리기·규칙 환각·
// 숫자 환각 셋을 고정한다.

const payload = {
  profileSummary: "타이레놀정500과 종합감기약을 함께 복용 중",
  totals: { definitely_matched: 1, possibly_relevant: 1, needs_more_info: 0 },
  definitelyMatched: [
    {
      ruleId: "RULE-DUP-APAP",
      nutrientOrIngredient: "아세트아미노펜",
      severity: "일반 주의",
      shortMessage: "동일 성분이 두 제품에 들어 있습니다.",
      matchedBecause: ["두 제품 모두 아세트아미노펜을 포함합니다."],
      needsMoreInfo: [],
      sourceTitles: ["의약품 허가사항"],
      evidence: ["[원문 확인] 1일 최대 4000 mg 을 넘지 않도록 한다."],
    },
  ],
  possiblyRelevant: [],
  needsMoreInfo: [],
};

const base: AiExplanation = {
  summaryTitle: "아세트아미노펜 성분 중복",
  summaryParagraph: "두 제품 모두 아세트아미노펜을 포함해 성분이 중복됩니다.",
  topAlerts: [
    {
      ruleId: "RULE-DUP-APAP",
      title: "성분 중복",
      severity: "일반 주의",
      reason: "동일 성분이 두 제품에 들어 있습니다.",
    },
  ],
  groupedFindings: [
    { sectionTitle: "확인된 항목", items: ["1일 최대 4000 mg 기준이 있습니다."] },
  ],
  missingInformation: [],
  userFriendlyNextSteps: ["복용 중인 제품의 성분표를 함께 확인해 보세요."],
  ruleCardActions: [
    { ruleId: "RULE-DUP-APAP", recommendation: "성분표에서 중복 여부를 확인합니다." },
  ],
  disclaimer: "이 설명은 참고용이며 진료를 대신하지 않습니다.",
};

describe("ai explanation referee", () => {
  it("passes an explanation that stays inside the engine result", () => {
    expect(refereeExplanation({ explanation: base, payload }).ok).toBe(true);
  });

  it.each(["금지/중단", "강한 주의", "참고"])(
    "rejects any severity that differs from the bound rule: %s",
    (severity) => {
      // 엔진이 이 규칙에 "일반 주의"를 줬다. 올리든 내리든 다른 값은 판정을 바꾼다.
      const verdict = refereeExplanation({
        explanation: {
          ...base,
          topAlerts: [{ ...base.topAlerts[0], severity: severity as never }],
        },
        payload,
      });
      expect(verdict.ok).toBe(false);
      if (!verdict.ok) {
        expect(
          verdict.rejections.some((r) => r.startsWith("severity_mismatch")),
        ).toBe(true);
      }
    },
  );

  it("rejects the same rule warned about twice", () => {
    // 같은 판정을 두 번 적으면 문제가 실제보다 많아 보인다.
    const verdict = refereeExplanation({
      explanation: { ...base, topAlerts: [base.topAlerts[0], base.topAlerts[0]] },
      payload,
    });
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) {
      expect(verdict.rejections).toContain("duplicate_alert_rule");
    }
  });

  it("rejects an alert bound to a rule the engine never sent", () => {
    const verdict = refereeExplanation({
      explanation: {
        ...base,
        topAlerts: [{ ...base.topAlerts[0], ruleId: "RULE-GHOST" }],
      },
      payload,
    });
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) {
      expect(verdict.rejections.some((r) => r.startsWith("unknown_rule"))).toBe(true);
    }
  });

  it("rejects a rule id the engine never sent", () => {
    const verdict = refereeExplanation({
      explanation: {
        ...base,
        ruleCardActions: [{ ruleId: "RULE-MADE-UP", recommendation: "확인합니다." }],
      },
      payload,
    });
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) {
      expect(verdict.rejections.some((r) => r.startsWith("unknown_rule"))).toBe(true);
    }
  });

  it("rejects a dose number that is absent from the engine payload", () => {
    const verdict = refereeExplanation({
      explanation: {
        ...base,
        groupedFindings: [
          { sectionTitle: "확인된 항목", items: ["1일 최대 8000 mg 까지 가능합니다."] },
        ],
      },
      payload,
    });
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) {
      expect(
        verdict.rejections.some((r) => r.startsWith("unsupported_number")),
      ).toBe(true);
    }
  });

  it("keeps numbers that the engine payload actually contains", () => {
    const verdict = refereeExplanation({
      explanation: {
        ...base,
        summaryParagraph: "허가사항은 1일 최대 4000 mg 을 넘지 않도록 합니다.",
      },
      payload,
    });
    expect(verdict.ok).toBe(true);
  });

  it.each([
    "함께 드셔도 안전합니다.",
    "위험하지 않습니다.",
    "반드시 중단하세요.",
  ])("rejects verdicts beyond what the engine said: %s", (line) => {
    const verdict = refereeExplanation({
      explanation: { ...base, summaryParagraph: line },
      payload,
    });
    expect(verdict.ok).toBe(false);
  });

  it("rejects questions in narrative fields where no answer can be given", () => {
    const verdict = refereeExplanation({
      explanation: { ...base, summaryParagraph: "다른 약도 드시나요?" },
      payload,
    });
    expect(verdict.ok).toBe(false);
  });

  it("allows questions only in missingInformation, which the profile form answers", () => {
    const verdict = refereeExplanation({
      explanation: { ...base, missingInformation: ["하루 몇 정을 드시나요?"] },
      payload,
    });
    expect(verdict.ok).toBe(true);
  });
});

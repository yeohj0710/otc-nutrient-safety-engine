import sampleEvaluationInput from "@/data/sample_evaluation_input.json";
import knowledgeIndexJson from "@/src/generated/knowledge-index.json";
import { explainSafetyResults } from "@/src/lib/ai/explainSafetyResults";
import { runSafetyEngine } from "@/src/lib/safety-engine";
import { knowledgeIndexSchema, type EngineQuery } from "@/src/types/knowledge";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const knowledgeIndex = knowledgeIndexSchema.parse(knowledgeIndexJson);

function buildSampleQuery(): EngineQuery {
  return {
    profile: {
      age: sampleEvaluationInput.user_profile.age_years,
      sex: sampleEvaluationInput.user_profile.sex,
      pregnancyStatus: sampleEvaluationInput.user_profile.pregnancy_status,
      lactationStatus: sampleEvaluationInput.user_profile.lactation_status,
      smokerStatus: sampleEvaluationInput.user_profile.smoking_status,
      medications: sampleEvaluationInput.user_profile.medications.map((item) => item.name),
      conditions: sampleEvaluationInput.user_profile.conditions,
      allergies: sampleEvaluationInput.user_profile.allergies,
      jurisdiction: "KR",
    },
    candidateItems: sampleEvaluationInput.candidate_stack.map((item) => ({
      ingredientId: item.ingredient_id,
      name: item.label,
      dailyIntakeValue: item.daily_intake_value,
      dailyIntakeUnit: item.daily_intake_unit,
      sameDay: item.ingredient_id === "calcium" ? true : undefined,
    })),
    sort: "severity_desc",
  };
}

function buildRequest() {
  return {
    engineResponse: runSafetyEngine(buildSampleQuery(), knowledgeIndex),
    profileSummary: "나이 67 / 성별 male / 복용 약물 warfarin, levothyroxine / 선택 성분 vitamin D, calcium",
    selectedFilters: {
      jurisdiction: "KR",
    },
  };
}

const originalApiKey = process.env.OPENAI_API_KEY;

afterEach(() => {
  process.env.OPENAI_API_KEY = originalApiKey;
});

describe("explainSafetyResults", () => {
  it("returns a graceful unavailable response when OPENAI_API_KEY is missing", async () => {
    delete process.env.OPENAI_API_KEY;

    const response = await explainSafetyResults(buildRequest(), {
      cache: new Map(),
      now: () => 0,
    });

    expect(response.ok).toBe(false);
    if (!response.ok) {
      expect(response.reason).toBe("missing_api_key");
    }
  });

  it("falls back when the model returns malformed structured output", async () => {
    process.env.OPENAI_API_KEY = "test-key";

    const response = await explainSafetyResults(buildRequest(), {
      cache: new Map(),
      now: () => 0,
      client: {
        responses: {
          parse: vi.fn().mockResolvedValue({
            output_parsed: null,
            _request_id: "req_bad",
          }),
        },
      },
    });

    expect(response.ok).toBe(false);
    if (!response.ok) {
      expect(response.reason).toBe("invalid_response");
    }
  });

  it("falls back cleanly when the OpenAI call throws", async () => {
    process.env.OPENAI_API_KEY = "test-key";

    const response = await explainSafetyResults(buildRequest(), {
      cache: new Map(),
      now: () => 0,
      client: {
        responses: {
          parse: vi.fn().mockRejectedValue(new Error("network timeout")),
        },
      },
    });

    expect(response.ok).toBe(false);
    if (!response.ok) {
      expect(response.reason).toBe("timeout");
    }
  });

  it("returns a validated structured response on success", async () => {
    process.env.OPENAI_API_KEY = "test-key";

    const response = await explainSafetyResults(buildRequest(), {
      cache: new Map(),
      now: () => 0,
      client: {
        responses: {
          parse: vi.fn().mockResolvedValue({
            _request_id: "req_ok",
            output_parsed: {
              summaryTitle: "AI 정리: 주요 주의사항",
              summaryParagraph: "비타민 D와 vitamin K 관련 경고가 우선적으로 보입니다.",
              topAlerts: [
                {
                  title: "비타민 K와 warfarin 관련 경고",
                  severity: "금지/중단",
                  reason: "deterministic 결과에 warfarin 상호작용 규칙이 포함되어 있습니다. 출처: Vitamin K - Health Professional Fact Sheet",
                },
              ],
              groupedFindings: [
                {
                  sectionTitle: "약물 상호작용",
                  items: ["warfarin과 관련된 규칙이 매칭되었습니다."],
                },
              ],
              missingInformation: ["일부 성분은 제형 정보가 없어서 추가 확인이 필요합니다."],
              userFriendlyNextSteps: ["현재 복용 중인 약물과 성분 제형을 다시 확인해 보세요."],
              ruleCardActions: [
                {
                  ruleId: "RULE-VITK-WARFARIN-CONSISTENCY",
                  recommendation: "warfarin을 복용 중이면 vitamin K 음식과 보충제 섭취량을 갑자기 바꾸지 말고 일정하게 유지해 주세요.",
                },
              ],
              disclaimer: "AI 정리는 결정적 규칙 엔진 결과를 쉽게 읽도록 정리한 보조 설명입니다.",
            },
          }),
        },
      },
    });

    expect(response.ok).toBe(true);
    if (response.ok) {
      expect(response.explanation.summaryTitle).toContain("AI 정리");
      expect(response.explanation.ruleCardActions[0]?.ruleId).toBe("RULE-VITK-WARFARIN-CONSISTENCY");
      expect(response.meta.model).toBe("gpt-5.4-mini");
    }
  });
});

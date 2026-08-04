import "server-only";

import OpenAI from "openai";

import {
  AI_EXPLAIN_MAX_OUTPUT_TOKENS,
  AI_EXPLAIN_MODEL,
  AI_EXPLAIN_REASONING_EFFORT,
  AI_EXPLAIN_TIMEOUT_MS,
  getOpenAIApiKey,
} from "@/src/lib/ai/config";
import { refereeExplanation } from "@/src/lib/ai/referee";
import {
  aiExplainResponseSchema,
  aiExplanationSchema,
  aiExplanationTextFormat,
  type AiExplainResponse,
} from "@/src/lib/ai/schema";
import type { SafetyEvaluation, Severity } from "@/src/lib/otc/schema";

// 메인 화면(OtcProductSafetyClient)이 쓰는 엔진은 otc/engine.ts 이고 출력이
// SafetyEvaluation 이다. 기존 explainSafetyResults 는 구 knowledge-pack 엔진
// (rule-explorer-client) 전용이라 그대로는 못 쓴다. 출력 스키마와 심판은 같은
// 것을 재사용하고 payload 어댑터만 여기서 따로 만든다.
//
// 판정은 전부 엔진이 이미 끝냈다. 모델은 그 결과를 읽기 쉬운 한국어로 다시 쓸 뿐,
// 어떤 규칙이 걸렸는지는 바꾸지 못한다.

/** 심판이 비교할 라벨. 엔진 severity 를 화면 표현으로만 옮긴다. */
function severityToLabel(severity: Severity) {
  // OTC 엔진의 등급은 information | caution | high | urgent 네 단계다.
  // 구 엔진(contraindicated/avoid/warn/monitor)과 값이 달라 그대로 못 쓴다.
  switch (severity) {
    case "urgent":
      return "금지/중단";
    case "high":
      return "강한 주의";
    case "caution":
      return "일반 주의";
    default:
      return "참고";
  }
}

const MAX_FINDINGS = 8;
const MAX_TEXT = 220;

function cut(text: string | undefined, limit = MAX_TEXT) {
  const value = (text ?? "").trim();
  return value.length > limit ? `${value.slice(0, limit)}…` : value;
}

export type OtcExplainInput = {
  evaluation: SafetyEvaluation;
  productNames: string[];
  profileSummary: string;
};

/**
 * 심판이 허용 목록을 뽑을 수 있도록 ruleId·severity 키 이름을 그대로 쓴다.
 * refereeExplanation 이 payload 를 훑어 이 두 키를 모은다.
 */
export function buildOtcPayload(input: OtcExplainInput) {
  return {
    profileSummary: cut(input.profileSummary, 300),
    products: input.productNames.slice(0, 12).map((name) => cut(name, 60)),
    totals: {
      findings: input.evaluation.findings.length,
      inputIssues: input.evaluation.inputIssues.length,
      coverageGaps: input.evaluation.coverageGaps.length,
    },
    findings: input.evaluation.findings.slice(0, MAX_FINDINGS).map((finding) => ({
      ruleId: finding.ruleId,
      ruleType: finding.ruleType,
      severity: severityToLabel(finding.severity),
      decisionBasis: finding.decisionBasis,
      title: cut(finding.titleKo),
      detail: cut(finding.detailKo),
      nextAction: cut(finding.nextActionKo),
      amount:
        finding.calculatedAmount !== undefined && finding.unit
          ? `${finding.calculatedAmount}${finding.unit}`
          : "",
      reference:
        finding.referenceAmount !== undefined && finding.unit
          ? `${finding.referenceAmount}${finding.unit}`
          : "",
    })),
    inputIssues: input.evaluation.inputIssues
      .slice(0, 6)
      .map((issue) => ({ field: issue.field, message: cut(issue.messageKo) })),
    coverageGaps: input.evaluation.coverageGaps.slice(0, 4).map((gap) => ({
      ruleType: gap.ruleType,
      title: cut(gap.titleKo),
      detail: cut(gap.detailKo),
    })),
  };
}

function buildInstructions() {
  return [
    "당신은 일반의약품 함께복용 점검 결과를 쉬운 한국어로 풀어 쓰는 보조 설명자입니다.",
    "이미 계산된 판정 결과만 바탕으로 설명합니다.",
    "규칙 매칭 여부를 새로 판단하지 마십시오. 판정은 엔진이 이미 끝냈습니다.",
    "주어진 자료에 없는 용량·상한·기간 숫자를 쓰지 마십시오.",
    "되묻지 마십시오. 물음표를 쓰지 마십시오. 화면에는 답을 받을 자리가 없습니다.",
    "단, 조건 부족 목록(missingInformation)만 물음 형태를 써도 됩니다. 화면에 입력란이 있습니다.",
    "안전 여부를 단정하지 마십시오. '안전합니다', '문제없습니다', '괜찮습니다', '위험하지 않습니다' 같은 표현을 쓰지 마십시오. 엔진은 심각도 등급만 매기고 안전을 보증하지 않습니다.",
    "판정이 하나도 없더라도 안심시키지 마십시오. '해당 없음'은 '안전함'이 아니라 '이 규칙으로는 판정하지 못함'이라는 뜻입니다.",
    "severity 는 주어진 값을 그대로 쓰십시오. 등급을 올리거나 내리지 마십시오.",
    "ruleCardActions 의 ruleId 는 주어진 findings 의 ruleId 만 쓰십시오.",
    "복용 시작·중단·용량 변경을 지시하지 마십시오. 판단이 필요하면 약사·의사와 상의하라고만 적으십시오.",
  ].join("\n");
}

export async function explainOtcFindings(
  input: OtcExplainInput,
): Promise<AiExplainResponse> {
  const apiKey = getOpenAIApiKey();
  if (!apiKey) {
    return aiExplainResponseSchema.parse({
      ok: false,
      reason: "missing_api_key",
      notice: "요약 기능 설정이 없어 기본 결과만 표시합니다.",
    });
  }

  const payload = buildOtcPayload(input);
  const client = new OpenAI({ apiKey, timeout: AI_EXPLAIN_TIMEOUT_MS });

  try {
    const parsed = await client.responses.parse({
      model: AI_EXPLAIN_MODEL,
      instructions: buildInstructions(),
      input: [
        {
          role: "user",
          content: [{ type: "input_text", text: JSON.stringify(payload) }],
        },
      ],
      text: { format: aiExplanationTextFormat },
      reasoning: { effort: AI_EXPLAIN_REASONING_EFFORT },
      max_output_tokens: AI_EXPLAIN_MAX_OUTPUT_TOKENS,
      store: false,
    });

    const explanation = aiExplanationSchema.safeParse(parsed.output_parsed);
    if (!explanation.success) {
      return aiExplainResponseSchema.parse({
        ok: false,
        reason: "invalid_response",
        notice: "보조 설명 형식이 올바르지 않아 기본 결과만 표시합니다.",
      });
    }

    // 엔진이 하지 않은 판단을 더했는지 결정론으로 본다. 걸리면 전체를 버린다.
    const verdict = refereeExplanation({ explanation: explanation.data, payload });
    if (!verdict.ok) {
      console.warn("[otc-explain] refereed out", {
        rejections: verdict.rejections.slice(0, 6),
      });
      return aiExplainResponseSchema.parse({
        ok: false,
        reason: "refereed_out",
        notice: "보조 설명이 검사 기준을 벗어나 기본 결과만 표시합니다.",
      });
    }

    return aiExplainResponseSchema.parse({
      ok: true,
      explanation: explanation.data,
      meta: { cached: false, model: AI_EXPLAIN_MODEL, requestId: "otc" },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown";
    const timedOut = /time(?:d)?\s*out/i.test(message) || /abort/i.test(message);
    console.warn("[otc-explain] fallback", { reason: timedOut ? "timeout" : "openai_error", message });
    return aiExplainResponseSchema.parse({
      ok: false,
      reason: timedOut ? "timeout" : "openai_error",
      notice: "보조 설명을 만들지 못해 기본 결과만 표시합니다.",
    });
  }
}

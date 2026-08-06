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
    "topAlerts 의 각 항목에는 그 경보가 근거로 삼은 ruleId 를 반드시 넣고, severity 는 그 규칙에 주어진 값을 글자 그대로 복사하십시오. 다른 규칙의 등급을 가져오거나 새로 고르지 마십시오.",
    "ruleCardActions 의 ruleId 는 주어진 findings 의 ruleId 만 쓰십시오.",
    "복용 시작·중단·용량 변경을 지시하지 마십시오.",
    "",
    // 예전 지시문은 마지막 줄에서 약사·의사와 상의하라고만 적으라고 시켰다.
    // 그래서 요약이 엔진의 nextAction 을 그대로 옮겨 "…확인하고 약사 또는 의사와
    // 상담하십시오"라고 시키는 문장이 화면에 나갔다. 할 일은 판정마다 붙는
    // "지금 할 일" 칸이 이미 적고 있으므로 요약이 다시 시킬 자리가 아니다.
    "시키는 말투를 쓰지 마십시오:",
    "이 요약은 무엇이 걸렸고 왜 걸렸는지를 말하는 자리입니다. 할 일은 판정마다 화면 아래 '지금 할 일' 칸이 이미 적고 있습니다.",
    "'~하십시오', '~하세요', '~해 주세요', '~하시기 바랍니다', '~하도록 하십시오', '~할 것', '~해야 합니다' 같은 말끝을 쓰지 마십시오.",
    "엔진이 적어 둔 nextAction 을 요약문에 옮겨 적지 마십시오. 그 문장은 화면이 따로 보여줍니다.",
    "상담을 권하는 문장도 쓰지 마십시오. 누구와 상의할지는 '지금 할 일' 칸이 정합니다.",
    "",
    "이렇게 쓰지 마십시오 → 이렇게 쓰십시오:",
    "'추가 복용 전 제품 포장과 허가사항을 확인하고 약사 또는 의사와 상담하십시오.' → '지금 할 일은 판정마다 아래에 따로 적어 두었습니다.'",
    "'복용량을 줄이세요.' → '입력한 하루 사용량이 허가상 상한을 넘었다고 판정했습니다.'",
    "'임신 중이라면 전문가와 상의가 필요합니다.' → '임신 조건은 이 제품 규칙으로 판정하지 못해 확인 범위 밖으로 남겼습니다.'",
    "",
    "문체:",
    "능동형으로 쓰십시오. '판정을 받았습니다·확인되지 않아·표시됩니다' 대신 '판정했습니다·확인하지 못해·보여드립니다'로 쓰십시오. '~게 되다'도 쓰지 마십시오.",
    "무엇을 말하는지 목적어를 밝히십시오. '일치합니다'가 아니라 '입력한 신장질환 조건이 이 제품의 주의 조건과 일치합니다'로 쓰십시오.",
    "입으로 쓰는 말을 쓰십시오. 섭취·유의·권장 대신 먹다·보다·권하다를 쓰십시오.",
  ].join("\n");
}

export async function explainOtcFindings(
  input: OtcExplainInput,
): Promise<AiExplainResponse> {
  const apiKey = getOpenAIApiKey();
  if (!apiKey) {
    console.warn("[otc-explain] fallback", { reason: "missing_api_key" });
    return aiExplainResponseSchema.parse({
      ok: false,
      reason: "missing_api_key",
      // 화면이 이 문장을 그대로 보여준다. 실패마다 다른 말을 써야 사용자가
      // "원래 없는 화면"과 "이번에 못 붙은 화면"을 가려낸다.
      notice: "이 서버에는 요약 기능이 켜져 있지 않아, 아래 엔진 결과만 보여드립니다.",
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
      console.warn("[otc-explain] fallback", {
        reason: "invalid_response",
        issues: explanation.error.issues.slice(0, 4),
      });
      return aiExplainResponseSchema.parse({
        ok: false,
        reason: "invalid_response",
        notice: "AI 응답 형식이 맞지 않아 아래 엔진 결과만 보여드립니다.",
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
        notice:
          "AI 가 쓴 요약이 검토 기준을 벗어나 버렸습니다. 아래 엔진 결과만 보여드립니다.",
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
      notice: timedOut
        ? "AI 응답이 제때 오지 않았습니다. 아래 엔진 결과만 보여드립니다. 다시 점검하면 붙을 수 있어요."
        : "AI 요약을 만들지 못했습니다. 아래 엔진 결과만 보여드립니다.",
    });
  }
}

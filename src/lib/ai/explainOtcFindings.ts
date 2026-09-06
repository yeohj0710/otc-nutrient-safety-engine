import "server-only";

import OpenAI from "openai";
import { z } from "zod";
import { zodTextFormat } from "openai/helpers/zod";
import { createHash } from "node:crypto";
import { buildOtcCounselingContext, validateOtcDiscussion } from "@/src/lib/ai/otc-counseling-context";

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
  type AiExplainResponse,
} from "@/src/lib/ai/schema";
import type { SafetyEvaluation, Severity, SelectedProduct, UserProfile } from "@/src/lib/otc/schema";

// 메인 화면(OtcProductSafetyClient)이 쓰는 엔진은 otc/engine.ts 이고 출력이
// SafetyEvaluation 이다. 기존 explainSafetyResults 는 구 knowledge-pack 엔진
// (rule-explorer-client) 전용이라 그대로는 못 쓴다. 출력 스키마와 심판은 같은
// 것을 재사용하고 payload 어댑터만 여기서 따로 만든다.
//
// 판정은 전부 엔진이 이미 끝냈다. 모델은 그 결과를 읽기 쉬운 한국어로 다시 쓸 뿐,
// 어떤 규칙이 걸렸는지는 바꾸지 못한다.

/** 심판이 비교할 라벨. 엔진 severity 를 화면 표현으로만 옮긴다. */
function severityToLabel(severity: Severity): "금지/중단" | "강한 주의" | "일반 주의" | "참고" {
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
const explanationCache = new Map<string, {expiresAt:number; response:AiExplainResponse}>();

function cut(text: string | undefined, limit = MAX_TEXT) {
  const value = (text ?? "").trim();
  return value.length > limit ? `${value.slice(0, limit)}…` : value;
}

export type OtcExplainInput = {
  evaluation: SafetyEvaluation;
  productNames: string[];
  profileSummary: string;
  selected?: SelectedProduct[];
  profile?: UserProfile;
};

/**
 * 심판이 허용 목록을 뽑을 수 있도록 ruleId·severity 키 이름을 그대로 쓴다.
 * refereeExplanation 이 payload 를 훑어 이 두 키를 모은다.
 */
export function buildOtcPayload(input: OtcExplainInput) {
  return {
    counseling: buildOtcCounselingContext(input.evaluation, input.selected ?? [], input.profile),
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
    "먼저 환자가 입력한 구체적인 질환·복용약·복용량과 제품의 실제 성분을 연결해 무엇을 확인해야 하는지 설명합니다. 단순히 주의 항목 개수나 시스템이 판정했다는 이야기로 채우지 않습니다.",
    "counseling에는 실제 제품의 함량·사용량, 환자 조건, 허가원문과 검토한 논문의 결과가 있습니다. 용량 초과는 입력량과 허가값을 같은 제품에 연결하고, 병용은 어떤 성분과 어떤 병용약 때문에 주의가 필요한지 밝힙니다.",
    "calculation의 amount와 reference는 구조화한 허가 기준에 입력값을 대조한 계산 결과입니다. sources에서 출처를 확인하되, 계산값을 허가원문의 직접 인용으로 표현하지 않습니다. productUse의 doseUnitLabel로 정·캡슐·mL 등 실제 복용 단위를 씁니다.",
    "evidenceDiscussion에는 규칙당 문단 하나로 연구 대상, 성분, 연구 설계, 사용량과 기간, 구체적인 결과, 그리고 입력한 환자에게 적용할 때의 차이를 설명합니다. papers의 population, exposure, outcome, limitation 값을 그대로 근거로 씁니다. 근거가 없는 수치, 조합, 효과를 만들지 않습니다.",
    "evidenceDiscussion의 ruleId와 pmids는 해당 counseling.evidence 항목에 제공한 값만 씁니다. relation이 direct가 아닌 문헌(입력 정보 부족, 연구 대상과 차이, 배경)은 이 환자와 성분을 직접 검증한 결과로 쓰지 않으며, statusKo와 limitation이 말하는 이유(어떤 입력이 비어 있는지, 무엇이 다른지)를 그 문단 안에서 밝힙니다. 논문의 위험비를 개인의 절대 위험으로 바꾸지 않습니다. 논문은 허가 판정을 바꾸지 않습니다.",
    "reviewStatus가 agent_screened_candidate인 문헌은 추가 선별 후보입니다. 그 문헌을 언급하는 문단에는 '추가 선별 후보'라는 말을 넣고, 검토를 마친 근거나 승인된 근거처럼 쓰지 않습니다. 후보의 지위는 statusKo 그대로 씁니다.",
    "literature.status가 none이면 '논문이 없습니다'로 끝내지 말고, authorization의 허가원문과 calculation으로 무엇을 확인했는지, 문헌으로는 무엇을 확인하지 못했는지를 구체적으로 씁니다. literature.headlineKo와 detailKo에 그 이유가 있습니다.",
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
  const key = createHash("sha256").update(JSON.stringify({model:AI_EXPLAIN_MODEL,effort:AI_EXPLAIN_REASONING_EFFORT,instructions:buildInstructions(),payload})).digest("hex");
  const cached = explanationCache.get(key);
  if (cached && cached.expiresAt > Date.now() && cached.response.ok) return {...cached.response,meta:{...cached.response.meta,cached:true}};
  const client = new OpenAI({ apiKey, timeout: AI_EXPLAIN_TIMEOUT_MS, maxRetries: 0 });
  // 실제 화면에 필요한 문장만 생성한다. 경보와 등급은 엔진 값에서 그대로 만든다.
  const ruleIds = [...new Set(payload.counseling.evidence.map(row=>row.ruleId))];
  const detailedSchema = z.object({summaryTitle:z.string(),summaryParagraph:z.string(),evidenceDiscussion:z.array(z.object({text:z.string(),ruleId:z.enum((ruleIds.length ? ruleIds : ["none"]) as [string,...string[]]),pmids:z.array(z.string())}))});

  try {
    const parsed = await client.responses.parse({
      model: AI_EXPLAIN_MODEL,
      instructions: buildInstructions() + "\n출력은 summaryTitle, summaryParagraph, evidenceDiscussion만 작성합니다. 요약은 3문장 이내, 문헌 설명은 환자와 가장 관련 있는 규칙 3개 이내, 규칙당 4문장 이내입니다. 경보와 다음 행동은 화면이 엔진 값에서 표시하므로 별도로 작성하지 않습니다. 입력에 없는 결과를 채우려고 하지 않습니다.",
      input: [
        {
          role: "user",
          content: [{ type: "input_text", text: JSON.stringify(payload) }],
        },
      ],
      text: { format: zodTextFormat(ruleIds.length ? detailedSchema : detailedSchema.omit({evidenceDiscussion:true}),"otc_personalized_explanation") },
      reasoning: { effort: AI_EXPLAIN_REASONING_EFFORT },
      max_output_tokens: AI_EXPLAIN_MAX_OUTPUT_TOKENS,
      store: false,
    });

    const generated = detailedSchema.safeParse(parsed.output_parsed ? {...parsed.output_parsed, ...(!ruleIds.length ? {evidenceDiscussion:[]} : {})} : null);
    const explanation = generated.success ? {success:true as const,data:{...generated.data,evidenceDiscussion:generated.data.evidenceDiscussion ?? [],topAlerts:payload.findings.filter(f=>f.severity!=="참고").slice(0,3).map(f=>({ruleId:f.ruleId,title:f.title,severity:f.severity,reason:f.detail})),groupedFindings:[],missingInformation:[],userFriendlyNextSteps:[],ruleCardActions:[],disclaimer:"문헌은 허가사항 판정을 보충하며 개인의 안전성을 보증하지 않습니다."}} : generated;
    if (!explanation.success) {
      console.warn("[otc-explain] fallback", {
        reason: "invalid_response",
        issues: explanation.error.issues.slice(0, 4),
        status: parsed.status, usage: parsed.usage,
      });
      return aiExplainResponseSchema.parse({
        ok: false,
        reason: "invalid_response",
        notice: "AI 응답 형식이 맞지 않아 아래 엔진 결과만 보여드립니다.",
      });
    }

    // 엔진이 하지 않은 판단을 더했는지 결정론으로 본다. 걸리면 전체를 버린다.
    const verdict = refereeExplanation({ explanation: explanation.data, payload });
    const discussionErrors=validateOtcDiscussion(explanation.data.evidenceDiscussion,payload.counseling);
    if (!verdict.ok || discussionErrors.length) {
      console.warn("[otc-explain] refereed out", {
        rejections: [...(!verdict.ok?verdict.rejections:[]),...discussionErrors].slice(0, 6),
      });
      return aiExplainResponseSchema.parse({
        ok: false,
        reason: "refereed_out",
        notice:
          "AI 가 쓴 요약이 검토 기준을 벗어나 버렸습니다. 아래 엔진 결과만 보여드립니다.",
      });
    }

    const response = aiExplainResponseSchema.parse({
      ok: true,
      explanation: explanation.data,
      evidenceDiscussion: explanation.data.evidenceDiscussion,
      meta: { cached: false, model: AI_EXPLAIN_MODEL, effort:AI_EXPLAIN_REASONING_EFFORT, requestId: "otc" },
    });
    if (explanationCache.size >= 120) explanationCache.delete(explanationCache.keys().next().value as string);
    explanationCache.set(key,{expiresAt:Date.now()+5*60_000,response});
    return response;
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

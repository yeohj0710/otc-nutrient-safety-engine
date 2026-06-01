import "server-only";

import { createHash, randomUUID } from "node:crypto";

import OpenAI from "openai";

import {
  AI_EXPLAIN_CACHE_TTL_MS,
  AI_EXPLAIN_MAX_EVIDENCE_PER_RULE,
  AI_EXPLAIN_MAX_OUTPUT_TOKENS,
  AI_EXPLAIN_MAX_RULES_PER_BUCKET,
  AI_EXPLAIN_MAX_TEXT_LENGTH,
  AI_EXPLAIN_MODEL,
  AI_EXPLAIN_TIMEOUT_MS,
  getOpenAIApiKey,
} from "@/src/lib/ai/config";
import {
  aiExplainRequestSchema,
  aiExplainResponseSchema,
  aiExplanationSchema,
  aiExplanationTextFormat,
  type AiExplainRequest,
  type AiExplainResponse,
} from "@/src/lib/ai/schema";
import type { RuleMatch } from "@/src/types/knowledge";

type CachedExplanation = {
  expiresAt: number;
  value: AiExplainResponse;
};

type OpenAIParseResponse = {
  output_parsed: unknown;
  _request_id?: string;
};

type OpenAIClientLike = {
  responses: {
    parse: (params: object, options?: object) => Promise<OpenAIParseResponse>;
  };
};

type ExplainDependencies = {
  client?: OpenAIClientLike;
  now?: () => number;
  cache?: Map<string, CachedExplanation>;
};

const explanationCache = new Map<string, CachedExplanation>();

function truncateText(text: string | null | undefined, maxLength = AI_EXPLAIN_MAX_TEXT_LENGTH) {
  if (!text) return null;
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

function sanitizeReason(text: string, fallback: string) {
  const trimmed = text.trim();
  if (!trimmed) return fallback;
  return /[�?]/.test(trimmed) ? fallback : trimmed;
}

function severityToLabel(severity: RuleMatch["resolvedSeverity"]) {
  switch (severity) {
    case "contraindicated":
    case "avoid":
      return "금지/중단";
    case "warn":
      return "강한 주의";
    case "monitor":
      return "일반 주의";
    default:
      return "참고";
  }
}

function summarizeEvidenceForAi(match: RuleMatch) {
  return match.supportingEvidenceChunks
    .slice(0, AI_EXPLAIN_MAX_EVIDENCE_PER_RULE)
    .map((chunk) => {
      const excerpt =
        chunk.quoteOriginal ??
        chunk.quoteTranslationKo ??
        chunk.summary ??
        chunk.quote ??
        chunk.chunkText;

      if (!excerpt) {
        return null;
      }

      const statusPrefix =
        chunk.verificationStatus === "verified_against_source"
          ? "[원문 확인] "
          : chunk.verificationStatus === "supported_inference"
            ? "[원문+해석] "
            : chunk.verificationStatus === "pending_manual_extraction"
              ? "[원문 발췌 대기] "
              : "";
      const locatorSuffix = chunk.locatorValue ? ` (${chunk.locatorValue})` : "";

      return truncateText(`${statusPrefix}${excerpt}${locatorSuffix}`);
    })
    .filter((item): item is string => Boolean(item));
}

function pickRules(matches: RuleMatch[]) {
  return matches.slice(0, AI_EXPLAIN_MAX_RULES_PER_BUCKET).map((match) => ({
    ruleId: match.ruleId,
    nutrientOrIngredient: match.rule.nutrientOrIngredient,
    severity: severityToLabel(match.resolvedSeverity),
    shortMessage: truncateText(match.resolvedMessage),
    matchedBecause: match.matchedBecause
      .slice(0, 2)
      .map((item) => truncateText(sanitizeReason(item, "프로필 조건과 규칙 조건이 일치했습니다.")) ?? "")
      .filter(Boolean),
    needsMoreInfo: match.needsMoreInfo
      .slice(0, 3)
      .map((item) => truncateText(sanitizeReason(item, "필수 프로필 정보가 더 필요합니다.")) ?? "")
      .filter(Boolean),
    sourceTitles: match.supportingSources.map((source) => source.title).slice(0, 3),
    evidence: summarizeEvidenceForAi(match),
  }));
}

function buildCompactPayload(input: AiExplainRequest) {
  const request = aiExplainRequestSchema.parse(input);

  return {
    profileSummary: truncateText(request.profileSummary, 300),
    selectedFilters: request.selectedFilters ?? null,
    totals: request.engineResponse.totalCounts,
    definitelyMatched: pickRules(request.engineResponse.definitely_matched),
    possiblyRelevant: pickRules(request.engineResponse.possibly_relevant),
    needsMoreInfo: pickRules(request.engineResponse.needs_more_info),
  };
}

function buildCacheKey(payload: ReturnType<typeof buildCompactPayload>) {
  return createHash("sha256").update(JSON.stringify({ model: AI_EXPLAIN_MODEL, payload })).digest("hex");
}

function createClient(apiKey: string) {
  return new OpenAI({
    apiKey,
    timeout: AI_EXPLAIN_TIMEOUT_MS,
    maxRetries: 0,
  });
}

function isTimeoutError(error: unknown) {
  return error instanceof Error && (/timeout/i.test(error.message) || /abort/i.test(error.message));
}

function buildInstructions() {
  return [
    "당신은 nutrition safety rule explorer의 보조 설명 계층입니다.",
    "결정적 규칙 엔진이 이미 규칙 매칭을 계산했습니다.",
    "규칙 매칭 여부를 새로 판단하지 마십시오.",
    "threshold, severity, contraindication, interaction, 숫자값을 수정하거나 추정하지 마십시오.",
    "주어진 deterministic 결과를 한국어로 짧고 보수적으로 정리하십시오.",
    "출처는 입력에 포함된 source title만 언급하십시오.",
    "논문, 저자, 저널, chunk ID를 새로 만들지 마십시오.",
    "정보가 부족하면 무엇이 부족한지 명시하십시오.",
    "설명은 비진단적이어야 하며 AI 정리라는 점이 드러나야 합니다.",
    "ruleCardActions에는 입력으로 받은 각 ruleId마다 recommendation을 하나씩 작성하십시오.",
    "recommendation은 사용자가 지금 어떻게 하면 되는지 바로 알 수 있게, 1문장 한국어 권고 형태로 쓰십시오.",
    "recommendation은 근거 문장을 쉬운 행동 지침으로 다시 말하되, 금지/주의/모니터링의 강도를 바꾸지 마십시오.",
  ].join(" ");
}

export async function explainSafetyResults(
  input: AiExplainRequest,
  dependencies: ExplainDependencies = {},
): Promise<AiExplainResponse> {
  const now = dependencies.now ?? Date.now;
  const cache = dependencies.cache ?? explanationCache;
  const compactPayload = buildCompactPayload(input);
  const cacheKey = buildCacheKey(compactPayload);
  const cached = cache.get(cacheKey);

  if (cached && cached.expiresAt > now()) {
    return aiExplainResponseSchema.parse(cached.value);
  }

  const apiKey = getOpenAIApiKey();
  if (!apiKey && !dependencies.client) {
    return aiExplainResponseSchema.parse({
      ok: false,
      reason: "missing_api_key",
      notice: "OPENAI_API_KEY가 없어 AI 정리를 건너뛰고 결정적 결과만 표시합니다.",
    });
  }

  const requestId = randomUUID();
  const client = dependencies.client ?? createClient(apiKey ?? "");

  try {
    const parsed = await client.responses.parse(
      {
        model: AI_EXPLAIN_MODEL,
        instructions: buildInstructions(),
        input: [
          {
            role: "user",
            content: [
              {
                type: "input_text",
                text: JSON.stringify(compactPayload),
              },
            ],
          },
        ],
        text: { format: aiExplanationTextFormat },
        max_output_tokens: AI_EXPLAIN_MAX_OUTPUT_TOKENS,
        store: false,
      },
      {
        headers: {
          "X-Client-Request-Id": requestId,
        },
      },
    );

    const explanation = aiExplanationSchema.safeParse(parsed.output_parsed);

    if (!explanation.success) {
      console.warn("[ai-explain] invalid structured output", {
        requestId,
        issueCount: explanation.error.issues.length,
      });

      return aiExplainResponseSchema.parse({
        ok: false,
        reason: "invalid_response",
        notice: "AI 정리 응답 형식이 올바르지 않아 결정적 결과만 표시합니다.",
      });
    }

    const response = aiExplainResponseSchema.parse({
      ok: true,
      explanation: explanation.data,
      meta: {
        cached: false,
        model: AI_EXPLAIN_MODEL,
        requestId: parsed._request_id ?? requestId,
      },
    });

    cache.set(cacheKey, {
      expiresAt: now() + AI_EXPLAIN_CACHE_TTL_MS,
      value: response,
    });

    console.info("[ai-explain] success", {
      requestId,
      openaiRequestId: parsed._request_id ?? null,
      matchedCount: compactPayload.definitelyMatched.length,
      possibleCount: compactPayload.possiblyRelevant.length,
      missingCount: compactPayload.needsMoreInfo.length,
    });

    return response;
  } catch (error) {
    const reason = isTimeoutError(error) ? "timeout" : "openai_error";

    console.warn("[ai-explain] fallback", {
      requestId,
      reason,
      message: error instanceof Error ? error.message : "unknown",
    });

    return aiExplainResponseSchema.parse({
      ok: false,
      reason,
      notice:
        reason === "timeout"
          ? "AI 정리 요청 시간이 초과되어 결정적 결과만 표시합니다."
          : "AI 정리 생성에 실패하여 결정적 결과만 표시합니다.",
    });
  }
}

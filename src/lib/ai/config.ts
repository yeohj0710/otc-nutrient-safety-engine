export const AI_EXPLAIN_MODEL = "gpt-5.6-luna";
/** 추론 모델이라 웜 2~4초, 콜드는 더 걸린다. 8초는 콜드에서 자주 끊겼다. */
export const AI_EXPLAIN_TIMEOUT_MS = 14_000;
export const AI_EXPLAIN_MAX_RULES_PER_BUCKET = 4;
export const AI_EXPLAIN_MAX_EVIDENCE_PER_RULE = 1;
export const AI_EXPLAIN_MAX_TEXT_LENGTH = 180;
/**
 * 추론 모델은 이 예산을 추론에 먼저 쓴다. 900 이면 추론만 하다 메시지 없이
 * status=incomplete 로 끝나 output_parsed 가 비고, 화면은 매번 "형식이 올바르지
 * 않다"는 폴백을 본다. 2,000 이상 확보한다.
 */
export const AI_EXPLAIN_MAX_OUTPUT_TOKENS = 2_400;
/** 이 화면은 설명만 하면 되므로 추론을 깊게 돌릴 이유가 없다. */
export const AI_EXPLAIN_REASONING_EFFORT = "low" as const;
export const AI_EXPLAIN_CACHE_TTL_MS = 5 * 60 * 1000;

export function getOpenAIApiKey() {
  const apiKey = process.env.OPENAI_API_KEY?.trim();
  return apiKey ? apiKey : null;
}

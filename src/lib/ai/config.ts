export const AI_EXPLAIN_MODEL = "gpt-5.4-mini";
export const AI_EXPLAIN_TIMEOUT_MS = 8_000;
export const AI_EXPLAIN_MAX_RULES_PER_BUCKET = 4;
export const AI_EXPLAIN_MAX_EVIDENCE_PER_RULE = 1;
export const AI_EXPLAIN_MAX_TEXT_LENGTH = 180;
export const AI_EXPLAIN_MAX_OUTPUT_TOKENS = 900;
export const AI_EXPLAIN_CACHE_TTL_MS = 5 * 60 * 1000;

export function getOpenAIApiKey() {
  const apiKey = process.env.OPENAI_API_KEY?.trim();
  return apiKey ? apiKey : null;
}

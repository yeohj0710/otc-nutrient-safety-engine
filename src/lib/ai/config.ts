import type { ReasoningEffort } from "openai/resources/shared";

export const AI_EXPLAIN_MODEL = "gpt-5.6-luna";
/**
 * Luna max가 환자 조건과 원자료를 대조하고 설명을 마칠 시간을 확보한다.
 * Vercel 함수 상한 300초 안에서 실패 사유와 대체 설명까지 반환한다.
 */
export const AI_EXPLAIN_TIMEOUT_MS = 240_000;
export const AI_EXPLAIN_MAX_RULES_PER_BUCKET = 4;
export const AI_EXPLAIN_MAX_EVIDENCE_PER_RULE = 1;
export const AI_EXPLAIN_MAX_TEXT_LENGTH = 180;
/**
 * 추론과 답변에 함께 쓰는 예산이다. 실제 max 호출에서 설명 생성 전
 * 예산이 소진되지 않도록 24,000토큰을 확보한다.
 */
export const AI_EXPLAIN_MAX_OUTPUT_TOKENS = 24_000;
/** 환자 조건과 문헌의 세부 결과를 대조하는 상담 설명 설정. */
// 설치된 SDK의 타입 목록보다 Luna의 지원 범위가 넓다. 전송 값은 공식 모델 문서의 max로 고정한다.
export const AI_EXPLAIN_REASONING_EFFORT = "max" as unknown as ReasoningEffort;
export const AI_EXPLAIN_CACHE_TTL_MS = 5 * 60 * 1000;

export function getOpenAIApiKey() {
  const apiKey = process.env.OPENAI_API_KEY?.trim();
  return apiKey ? apiKey : null;
}

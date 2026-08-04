import { NextResponse } from "next/server";
import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

import {
  AI_EXPLAIN_MODEL,
  AI_EXPLAIN_REASONING_EFFORT,
  AI_EXPLAIN_TIMEOUT_MS,
  getOpenAIApiKey,
} from "@/src/lib/ai/config";

export const runtime = "nodejs";
export const maxDuration = 60;

// 사람이 쓴 말을 검색어로 옮긴다. "머리 아플 때 먹는 약" 처럼 제품명을 모르는
// 사람이 그냥 상황을 적으면 지금 검색은 아무것도 못 찾는다.
//
// ★ 모델은 제품을 고르지 않는다. 화면이 준 성분 목록에서 성분명만 고르고, 그
//   성분으로 제품을 찾는 것은 지금까지와 같은 결정론 검색이다. 고른 성분은
//   화면에 그대로 보여 주고 사용자가 지울 수 있다.

const outputSchema = z.object({
  ingredients: z.array(z.string()),
  note: z.string(),
});
const outputFormat = zodTextFormat(outputSchema, "search_terms");

type Body = { text?: unknown; ingredients?: unknown };

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Body | null;
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  const vocabulary = Array.isArray(body?.ingredients)
    ? body.ingredients.filter((x): x is string => typeof x === "string").slice(0, 120)
    : [];

  if (!text) {
    return NextResponse.json({ ok: false, reason: "empty_text" }, { status: 400 });
  }
  if (text.length > 200) {
    return NextResponse.json({ ok: false, reason: "too_long" }, { status: 400 });
  }
  if (!vocabulary.length) {
    return NextResponse.json({ ok: false, reason: "no_vocabulary" }, { status: 400 });
  }

  const apiKey = getOpenAIApiKey();
  if (!apiKey) return NextResponse.json({ ok: false, reason: "missing_api_key" });

  const instructions = [
    "너는 일반의약품 점검 화면의 검색어 정리기다.",
    "사람이 쓴 말을 보고, 아래 성분 목록에서 관련된 성분만 고른다.",
    "목록에 없는 성분은 절대 쓰지 않는다. 새 이름을 지어내지 않는다.",
    "관련된 것이 없으면 빈 배열을 낸다.",
    "많이 고르지 않는다. 가장 관련 있는 것부터 최대 3개까지만 고른다.",
    "약을 권하지 않는다. 무엇을 먹으라고 쓰지 않는다. 너는 검색어만 고른다.",
    "note 에는 왜 그 성분을 골랐는지 한 문장으로 적는다. 없으면 빈 문자열.",
    "",
    "성분 목록:",
    vocabulary.join(", "),
  ].join("\n");

  try {
    const client = new OpenAI({ apiKey, timeout: AI_EXPLAIN_TIMEOUT_MS });
    const parsed = await client.responses.parse({
      model: AI_EXPLAIN_MODEL,
      instructions,
      input: [{ role: "user", content: [{ type: "input_text", text }] }],
      text: { format: outputFormat },
      reasoning: { effort: AI_EXPLAIN_REASONING_EFFORT },
      max_output_tokens: 1600,
      store: false,
    });

    const raw = outputSchema.safeParse(parsed.output_parsed);
    if (!raw.success) return NextResponse.json({ ok: false, reason: "invalid_response" });

    // 목록에 없는 성분은 버린다. 모델이 지어낸 이름으로는 검색이 안 돌아간다.
    const allowed = new Set(vocabulary);
    const ingredients = raw.data.ingredients
      .filter((name) => allowed.has(name))
      .slice(0, 3);

    if (!ingredients.length) {
      return NextResponse.json({ ok: false, reason: "no_match" });
    }

    return NextResponse.json({
      ok: true,
      ingredients,
      note: raw.data.note.slice(0, 120),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown";
    const timedOut = /time(?:d)?\s*out/i.test(message) || /abort/i.test(message);
    console.warn("[otc-search] fallback", {
      reason: timedOut ? "timeout" : "openai_error",
      message,
    });
    return NextResponse.json({ ok: false, reason: timedOut ? "timeout" : "openai_error" });
  }
}

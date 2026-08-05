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
import { refereeFindingLine } from "@/src/lib/ai/referee";

export const runtime = "nodejs";
export const maxDuration = 60;

// 판정 한 건만 풀어 쓴다. 화면의 판정 카드마다 따로 부른다.
//
// 전체를 한 번에 넘기면 "여러 제품의 용량 또는 투여 방식" 같은 뭉뚱그린 문장이
// 나온다. 한 건씩 부르면 그 판정이 왜 걸렸는지만 말하게 된다. 판정 자체는
// 엔진이 이미 끝냈고 모델은 이유를 사람 말로 옮기기만 한다.

const INSTRUCTIONS = [
  "너는 일반의약품 점검 결과의 판정 한 건을 쉬운 한국어 한 문장으로 옮긴다.",
  "이 판정이 왜 걸렸는지, 무엇이 무엇과 겹치거나 넘었는지만 말한다.",
  "다음에 무엇을 하라는 말은 쓰지 않는다. 화면에 '지금 할 일'이 따로 있어서 겹친다.",
  "상담하라·확인하라 같은 안내로 문장을 끝내지 않는다. 사실만 적는다.",
  "다른 판정이나 일반론을 덧붙이지 않는다.",
  "입으로 쓰는 말로 쓴다. 섭취·유의·권장 같은 말 대신 먹다·보다·권하다를 쓴다.",
  "능동형으로 쓰고 무엇을 말하는지 목적어를 밝힌다.",
  "주어진 자료에 없는 숫자를 쓰지 않는다. 용량·상한·기간을 지어내지 않는다.",
  "안전하다·위험하다·문제없다고 단정하지 않는다. 엔진은 등급만 매긴다.",
  "복용을 시작·중단·조절하라고 쓰지 않는다.",
  "되묻지 않는다. 물음표를 쓰지 않는다.",
  "한 문장, 80자 안팎으로 쓴다.",
].join("\n");

type Body = {
  ruleType?: unknown;
  titleKo?: unknown;
  detailKo?: unknown;
  nextActionKo?: unknown;
  amount?: unknown;
  reference?: unknown;
  productNames?: unknown;
};

const findingLineSchema = z.object({ line: z.string().min(1) });
const findingLineFormat = zodTextFormat(findingLineSchema, "finding_line");

const str = (v: unknown, n = 240) => (typeof v === "string" ? v.slice(0, n) : "");

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Body | null;
  if (!body) return NextResponse.json({ ok: false, reason: "bad_request" }, { status: 400 });

  const apiKey = getOpenAIApiKey();
  if (!apiKey) return NextResponse.json({ ok: false, reason: "missing_api_key" });

  const names = Array.isArray(body.productNames)
    ? body.productNames.filter((x): x is string => typeof x === "string").slice(0, 6)
    : [];

  // 모델이 볼 수 있는 것이자 심판이 숫자를 대조할 허용 목록이다.
  const source = [
    names.length ? `함께 담은 약: ${names.join(", ")}` : "",
    `판정 종류: ${str(body.ruleType, 60)}`,
    `제목: ${str(body.titleKo)}`,
    `내용: ${str(body.detailKo, 400)}`,
    `다음 할 일: ${str(body.nextActionKo)}`,
    str(body.amount) ? `계산된 값: ${str(body.amount, 40)}` : "",
    str(body.reference) ? `허가 기준값: ${str(body.reference, 40)}` : "",
  ]
    .filter(Boolean)
    .join("\n");

  try {
    const client = new OpenAI({ apiKey, timeout: AI_EXPLAIN_TIMEOUT_MS });
    const parsed = await client.responses.parse({
      model: AI_EXPLAIN_MODEL,
      instructions: INSTRUCTIONS,
      input: [{ role: "user", content: [{ type: "input_text", text: source }] }],
      // responses.parse 는 zod 기반 포맷을 받는다. 원시 json_schema 객체를 주면
      // 호출 자체가 실패한다(openai_error 로 잡혔다).
      text: { format: findingLineFormat },
      reasoning: { effort: AI_EXPLAIN_REASONING_EFFORT },
      max_output_tokens: 1600,
      store: false,
    });

    const raw = (parsed.output_parsed as { line?: unknown } | null)?.line;
    const verdict = refereeFindingLine({ line: raw, allowedText: source });
    if (!verdict.ok) {
      console.warn("[otc-finding] refereed out", { reason: verdict.reason });
      return NextResponse.json({ ok: false, reason: "refereed_out" });
    }
    return NextResponse.json({ ok: true, line: verdict.line });
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown";
    const timedOut = /time(?:d)?\s*out/i.test(message) || /abort/i.test(message);
    console.warn("[otc-finding] fallback", { reason: timedOut ? "timeout" : "openai_error", message });
    return NextResponse.json({ ok: false, reason: timedOut ? "timeout" : "openai_error" });
  }
}

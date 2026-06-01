import { NextResponse } from "next/server";

import { explainSafetyResults } from "@/src/lib/ai/explainSafetyResults";
import { aiExplainRequestSchema } from "@/src/lib/ai/schema";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const input = aiExplainRequestSchema.parse(payload);
    const response = await explainSafetyResults(input);
    return NextResponse.json(response);
  } catch (error) {
    const message = error instanceof Error ? error.message : "AI 설명 요청을 처리하지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}

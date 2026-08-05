import { NextResponse } from "next/server";

import { explainSafetyResults } from "@/src/lib/ai/explainSafetyResults";
import { aiExplainRequestSchema } from "@/src/lib/ai/schema";

export const runtime = "nodejs";
/** 모델 생성이 20초를 넘길 수 있어 함수 예산을 명시한다. */
export const maxDuration = 60;

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const input = aiExplainRequestSchema.parse(payload);
    const response = await explainSafetyResults(input);
    return NextResponse.json(response);
  } catch (error) {
    const message = error instanceof Error ? error.message : "보조 설명 요청을 처리하지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}

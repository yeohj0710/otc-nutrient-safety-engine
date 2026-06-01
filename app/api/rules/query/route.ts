import { NextResponse } from "next/server";

import { getKnowledgeIndex } from "@/src/lib/knowledge";
import { runSafetyEngine } from "@/src/lib/safety-engine";
import { engineQuerySchema } from "@/src/types/knowledge";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const query = engineQuerySchema.parse(payload);
    const response = runSafetyEngine(query, getKnowledgeIndex());
    return NextResponse.json(response);
  } catch (error) {
    const message = error instanceof Error ? error.message : "요청을 처리하지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}

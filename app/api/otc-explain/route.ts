import { NextResponse } from "next/server";

import { explainOtcFindings } from "@/src/lib/ai/explainOtcFindings";
import type { SafetyEvaluation } from "@/src/lib/otc/schema";

export const runtime = "nodejs";
/** 모델 생성이 20초를 넘길 수 있어 함수 예산을 명시한다. */
export const maxDuration = 60;

// 메인 화면의 OTC 제품 점검 결과를 설명한다. 판정은 클라이언트 엔진이 이미
// 끝냈고 여기서는 그 결과만 읽는다 — 어떤 규칙이 걸렸는지는 바뀌지 않는다.

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as {
      evaluation?: SafetyEvaluation;
      productNames?: unknown;
      profileSummary?: unknown;
    };

    const evaluation = payload.evaluation;
    if (!evaluation || !Array.isArray(evaluation.findings)) {
      return NextResponse.json(
        { ok: false, reason: "invalid_response", notice: "점검 결과가 없어 설명을 만들지 않았습니다." },
        { status: 400 },
      );
    }

    const response = await explainOtcFindings({
      evaluation,
      productNames: Array.isArray(payload.productNames)
        ? payload.productNames.filter((item): item is string => typeof item === "string")
        : [],
      profileSummary:
        typeof payload.profileSummary === "string" && payload.profileSummary.trim()
          ? payload.profileSummary
          : "프로필 정보 없음",
    });

    return NextResponse.json(response);
  } catch (error) {
    const message = error instanceof Error ? error.message : "요청을 처리하지 못했습니다.";
    return NextResponse.json({ ok: false, reason: "openai_error", notice: message }, { status: 400 });
  }
}

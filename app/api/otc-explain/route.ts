import { NextResponse } from "next/server";

import { explainOtcFindings } from "@/src/lib/ai/explainOtcFindings";
import { parseOtcExplainInput } from "@/src/lib/ai/otc-explain-input";

export const runtime = "nodejs";
/** 모델 생성이 20초를 넘길 수 있어 함수 예산을 명시한다. */
export const maxDuration = 300;

// 화면과 같은 엔진으로 판정을 재현한 뒤 제품 원자료와 함께 설명한다.

export async function POST(request: Request) {
  try {
    const input = parseOtcExplainInput(await request.json());
    if (!input) {
      return NextResponse.json(
        { ok: false, reason: "invalid_response", notice: "제품이나 입력값을 확인하지 못했습니다. 제품과 복용량을 확인한 뒤 다시 점검하세요." },
        { status: 400 },
      );
    }

    const response = await explainOtcFindings(input);

    return NextResponse.json(response);
  } catch (error) {
    // notice 는 화면에 그대로 나가는 문장이다. 여기에 원본 오류 메시지를 넣으면
    // 영어 스택 문구와 내부 사정이 사용자에게 보인다. 원인은 로그로 남긴다.
    console.warn("[otc-explain] request failed", {
      message: error instanceof Error ? error.message : "unknown",
    });
    return NextResponse.json(
      {
        ok: false,
        reason: "openai_error",
        notice: "AI 요약을 만들지 못했습니다. 아래 엔진 결과만 보여드립니다.",
      },
      { status: 400 },
    );
  }
}

import { NextResponse } from "next/server";

import { streamOtcExplanation } from "@/src/lib/ai/explainOtcFindings";
import type { OtcExplainEvent } from "@/src/lib/ai/otc-explain-stream";
import { parseOtcExplainInput } from "@/src/lib/ai/otc-explain-input";

export const runtime = "nodejs";
/** 모델 생성이 20초를 넘길 수 있어 함수 예산을 명시한다. */
export const maxDuration = 300;

// 화면과 같은 엔진으로 판정을 재현한 뒤 제품 원자료와 함께 설명한다.
//
// 응답은 NDJSON 이다. 요약과 판정별 문단을 따로 만들어 동시에 보내고, 끝나는
// 것부터 줄 하나씩 내보낸다(interim → summary/discussion → heartbeat → result).
// 예전처럼 JSON 하나를 끝까지 붙들면 실측 195초 동안 화면이 뼈대만 그린다.

const HEARTBEAT_MS = 8_000;

export async function POST(request: Request) {
  let input: ReturnType<typeof parseOtcExplainInput> = null;
  try {
    input = parseOtcExplainInput(await request.json());
  } catch (error) {
    console.warn("[otc-explain] request failed", {
      message: error instanceof Error ? error.message : "unknown",
    });
  }
  if (!input) {
    return NextResponse.json(
      { ok: false, reason: "invalid_response", notice: "제품이나 입력값을 확인하지 못했습니다. 제품과 복용량을 확인한 뒤 다시 점검하세요." },
      { status: 400 },
    );
  }
  const ready = input;

  const started = Date.now();
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let closed = false;
      const send = (event: OtcExplainEvent) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
        } catch {
          closed = true;
        }
      };
      const finish = () => {
        if (closed) return;
        closed = true;
        clearInterval(heartbeat);
        try {
          controller.close();
        } catch {
          // 이미 닫힌 연결이다.
        }
      };
      const heartbeat = setInterval(() => send({ type: "heartbeat", elapsedMs: Date.now() - started }), HEARTBEAT_MS);
      // 화면을 떠나거나 조건을 바꾸면 모델 호출도 함께 끊는다.
      const abort = new AbortController();
      request.signal?.addEventListener("abort", () => { abort.abort(); finish(); }, { once: true });

      streamOtcExplanation(ready, send, abort.signal)
        .then((response) => send({ type: "result", response, elapsedMs: Date.now() - started }))
        .catch((error: unknown) => {
          // notice 는 화면에 그대로 나가는 문장이다. 여기에 원본 오류 메시지를 넣으면
          // 영어 스택 문구와 내부 사정이 사용자에게 보인다. 원인은 로그로 남긴다.
          console.warn("[otc-explain] request failed", {
            message: error instanceof Error ? error.message : "unknown",
          });
          send({
            type: "result",
            response: {
              ok: false,
              reason: "openai_error",
              notice: "AI 요약을 만들지 못했습니다. 아래 엔진 결과만 보여드립니다.",
            },
            elapsedMs: Date.now() - started,
          });
        })
        .finally(finish);
    },
    cancel() {
      // 읽는 쪽이 사라졌다. 남은 정리는 위의 abort 처리가 맡는다.
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "application/x-ndjson; charset=utf-8",
      "cache-control": "no-store",
      "x-accel-buffering": "no",
    },
  });
}

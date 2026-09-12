import type { OtcGroundingLine } from "@/src/lib/ai/otc-counseling-context";
import type { AiExplainResponse } from "@/src/lib/ai/schema";

// 보조 설명을 줄 단위(NDJSON)로 주고받는다. 서버 전용 모듈을 끌어오지 않아서
// 화면 컴포넌트에서도 그대로 쓴다.
//
// 예전에는 요약 전체를 한 번에 만들고 끝날 때까지 JSON 하나를 붙들었다. 프로덕션
// 실측이 195초였고 그동안 화면은 뼈대만 그린 채였다. 지금은 요약과 판정별 문단을
// 따로 만들어 동시에 보내고, 끝나는 것부터 줄 하나씩 내보낸다.

export type OtcExplainDiscussion = { text: string; ruleId: string; pmids: string[] };

export type OtcExplainEvent =
  /** 서버 원자료로 만든 판정별 설명. 모델을 기다리는 동안 읽는다. */
  | { type: "interim"; lines: OtcGroundingLine[] }
  | { type: "heartbeat"; elapsedMs: number }
  /** 요약이 먼저 끝났다. 판정별 문단은 아직 오는 중이다. */
  | { type: "summary"; summaryTitle: string; summaryParagraph: string; elapsedMs: number }
  /** 판정 한 건의 문단이 끝났다. */
  | { type: "discussion"; item: OtcExplainDiscussion; elapsedMs: number }
  | { type: "result"; response: AiExplainResponse; elapsedMs: number };

/** NDJSON 한 덩어리를 줄 단위 사건으로 나눈다. 마지막에 잘린 줄은 남겨서 돌려준다. */
export function splitOtcNdjson(buffer: string): { events: OtcExplainEvent[]; rest: string } {
  const lines = buffer.split("\n");
  const rest = lines.pop() ?? "";
  const events: OtcExplainEvent[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const parsed = JSON.parse(trimmed) as OtcExplainEvent;
      if (parsed && typeof parsed === "object" && "type" in parsed) events.push(parsed);
    } catch {
      // 깨진 줄은 버린다. 결과 줄은 서버가 마지막에 한 번만 보낸다.
    }
  }
  return { events, rest };
}

/**
 * 브라우저 쪽에서 보조 설명 응답을 읽는다. 서버는 두 모양으로 답한다.
 *   - application/json      : 키가 없거나 판정이 없거나 캐시가 맞은 경우. 한 번에 끝.
 *   - application/x-ndjson  : 모델을 부르는 경우. interim → summary/discussion → result.
 * 어느 쪽이든 마지막에는 result 하나를 넘긴다.
 */
export async function readOtcExplainResponse(
  response: Response,
  onEvent: (event: OtcExplainEvent) => void,
): Promise<void> {
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("x-ndjson") || !response.body) {
    const body = (await response.json()) as AiExplainResponse;
    onEvent({ type: "result", response: body, elapsedMs: 0 });
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawResult = false;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const split = splitOtcNdjson(buffer);
    buffer = split.rest;
    for (const event of split.events) {
      if (event.type === "result") sawResult = true;
      onEvent(event);
    }
  }
  for (const event of splitOtcNdjson(`${buffer}${decoder.decode()}\n`).events) {
    if (event.type === "result") sawResult = true;
    onEvent(event);
  }
  if (!sawResult) throw new Error("otc explain stream ended without a result");
}

/** 기다린 시간을 사람 말로. "1분 20초째" 처럼 읽힌다. */
export function otcElapsedLabel(elapsedMs: number) {
  const seconds = Math.max(0, Math.round(elapsedMs / 1000));
  if (seconds < 60) return `${seconds}초째`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes}분 ${rest}초째` : `${minutes}분째`;
}

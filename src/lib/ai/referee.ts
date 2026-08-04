import type { AiExplanation } from "@/src/lib/ai/schema";

// 모델이 쓴 보조 설명이 화면에 닿기 전에 통과해야 하는 결정론 관문이다.
//
// 이 사이트는 여형준 쪽과 사정이 다르다. 여기서는 엔진이 이미 심각도를 판정한다
// (금지/중단·강한 주의·일반 주의·참고). 그래서 심판이 막아야 하는 것은 "판단을
// 했다"가 아니라 **엔진이 하지 않은 판단을 모델이 더한 것**이다. 셋을 본다.
//
//   1. 엔진이 낸 적 없는 심각도 라벨을 쓰지 못한다(등급 부풀리기 차단).
//   2. 엔진이 준 적 없는 ruleId 를 쓰지 못한다(규칙 환각 차단).
//   3. 엔진이 준 적 없는 숫자를 쓰지 못한다(용량·상한 환각 차단).
//
// 한 군데라도 걸리면 보조 설명 전체를 버리고 화면은 엔진 결과만 보여준다.
// 부분만 지우면 남은 문장이 지워진 문장을 가리켜 더 위험하다.

export type RefereeInput = {
  explanation: AiExplanation;
  /** 모델에 실제로 보낸 compact payload. 허용 목록의 유일한 출처다. */
  payload: unknown;
};

export type RefereeVerdict =
  | { ok: true }
  | { ok: false; rejections: string[] };

const MAX_PARAGRAPH_CHARS = 700;

/** 되묻는 문장은 답을 받을 자리가 없다. */
const QUESTION = /[?？]/;

/** 엔진 판정을 넘어서는 단정. 엔진은 등급을 주지 "안전하다"고 말하지 않는다. */
const OVERREACH = [
  /안전합니다|안전해요|문제없습니다|문제 없습니다|괜찮습니다/,
  /위험하지 않습니다|걱정하지 않으셔도/,
  /반드시 중단하|즉시 끊으|절대 드시지/,
];

function collectStrings(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) for (const item of value) collectStrings(item, out);
  else if (value && typeof value === "object") {
    for (const item of Object.values(value)) collectStrings(item, out);
  } else if (typeof value === "number") out.push(String(value));
  return out;
}

/**
 * 검사 대상 숫자만 고른다.
 *
 * 모든 숫자를 보면 "1일 3회", "1단계" 같은 관용 표현의 1 까지 환각으로 잡혀
 * 심판이 상시 발동한다(실제로 프로덕션 첫 호출이 unsupported_number:1 로
 * 전건 거부됐다). 막아야 하는 것은 용량·상한 같은 크기이므로 두 자리 이상이거나
 * 단위가 바로 붙은 숫자만 본다.
 */
const UNIT = "(?:mg|g|mcg|µg|ug|ml|mL|L|IU|%|정|캡슐|포|알|배|세)";

function collectNumbers(text: string) {
  const found = new Set<string>();
  // 템플릿 리터럴 안에서는 \d 가 그냥 d 로 죽는다. 반드시 \\d 로 쓴다.
  for (const match of text.matchAll(
    new RegExp(`(\\d+(?:[.,]\\d+)*)\\s*${UNIT}?`, "g"),
  )) {
    const raw = match[1].replace(/,/g, "");
    const hasUnit = match[0].length > match[1].length;
    if (hasUnit || raw.replace(/[^0-9]/g, "").length >= 2) found.add(raw);
  }
  return found;
}

/** payload 안에 실제로 등장한 ruleId 와 심각도 라벨. */
function allowedFromPayload(payload: unknown) {
  const ruleIds = new Set<string>();
  const severities = new Set<string>();
  const walk = (value: unknown) => {
    if (Array.isArray(value)) {
      for (const item of value) walk(item);
      return;
    }
    if (!value || typeof value !== "object") return;
    const row = value as Record<string, unknown>;
    if (typeof row.ruleId === "string") ruleIds.add(row.ruleId);
    if (typeof row.severity === "string") severities.add(row.severity);
    for (const item of Object.values(row)) walk(item);
  };
  walk(payload);
  return { ruleIds, severities };
}

export function refereeExplanation({
  explanation,
  payload,
}: RefereeInput): RefereeVerdict {
  const rejections: string[] = [];
  const { ruleIds, severities } = allowedFromPayload(payload);
  const allowedNumbers = collectNumbers(collectStrings(payload).join("\n"));

  // 1) 엔진이 낸 적 없는 심각도를 붙이면 안 된다.
  for (const alert of explanation.topAlerts) {
    if (!severities.has(alert.severity)) {
      rejections.push(`unseen_severity:${alert.severity}`);
    }
  }

  // 2) 엔진이 준 적 없는 규칙을 가리키면 안 된다.
  for (const action of explanation.ruleCardActions) {
    if (!ruleIds.has(action.ruleId)) {
      rejections.push(`unknown_rule:${action.ruleId}`);
    }
  }

  // 3) 사람이 읽는 모든 문장에 대해 숫자·되묻기·과잉 단정을 본다.
  //
  // missingInformation 만 되묻기를 허용한다. 이 칸은 엔진의 "조건 부족" 목록이라
  // 물음 형태가 자연스럽고, 화면에 프로필 입력란이라는 답할 자리가 실제로 있다.
  // 나머지 칸은 설명문이라 물음표가 오면 답을 받을 곳이 없다.
  const prose: { line: string; mayAsk: boolean }[] = [
    { line: explanation.summaryTitle, mayAsk: false },
    { line: explanation.summaryParagraph, mayAsk: false },
    ...explanation.topAlerts.flatMap((item) => [
      { line: item.title, mayAsk: false },
      { line: item.reason, mayAsk: false },
    ]),
    ...explanation.groupedFindings.flatMap((group) => [
      { line: group.sectionTitle, mayAsk: false },
      ...group.items.map((item) => ({ line: item, mayAsk: false })),
    ]),
    ...explanation.missingInformation.map((line) => ({ line, mayAsk: true })),
    ...explanation.userFriendlyNextSteps.map((line) => ({ line, mayAsk: false })),
    ...explanation.ruleCardActions.map((item) => ({
      line: item.recommendation,
      mayAsk: false,
    })),
    { line: explanation.disclaimer, mayAsk: false },
  ];

  for (const [index, { line, mayAsk }] of prose.entries()) {
    if (line.length > MAX_PARAGRAPH_CHARS) rejections.push(`too_long:${index}`);
    if (!mayAsk && QUESTION.test(line)) rejections.push(`question:${index}`);
    for (const pattern of OVERREACH) {
      if (pattern.test(line)) {
        rejections.push(`overreach:${index}:${pattern.source}`);
        break;
      }
    }
    for (const number of collectNumbers(line)) {
      if (!allowedNumbers.has(number)) {
        rejections.push(`unsupported_number:${index}:${number}`);
        break;
      }
    }
  }

  if (rejections.length) return { ok: false, rejections };
  return { ok: true };
}

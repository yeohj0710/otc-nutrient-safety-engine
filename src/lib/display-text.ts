export function cleanDisplayText(
  value: string | null | undefined,
): string | null {
  if (!value) return null;

  return value
    .replace(/(\d)\s*[\u2013\u2014\u2015]\s*(\d)/g, "$1~$2")
    .replace(/[\u2013\u2014\u2015]/g, " ")
    .replace(/\u00b7/g, " 및 ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function cleanDisplayList(
  items: Array<string | null | undefined>,
  fallback = "해당 없음",
) {
  const cleaned = items
    .map((item) => cleanDisplayText(item))
    .filter((item): item is string => Boolean(item));

  return cleaned.length > 0 ? cleaned.join(", ") : fallback;
}

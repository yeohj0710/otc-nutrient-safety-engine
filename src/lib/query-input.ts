export type ParsedDailyIntake = {
  value: number;
  unit: string;
};

const doseUnitPattern =
  "(mcg\\s*rae|ug\\s*rae|µg\\s*rae|mcg|ug|µg|mg|g|iu|i\\.?u\\.?|아이유|마이크로그램|밀리그램|그램)";

const doseRegex = new RegExp(
  `(\\d{1,3}(?:,\\d{3})*|\\d+(?:\\.\\d+)?)\\s*${doseUnitPattern}`,
  "i",
);

const allDoseRegex = new RegExp(
  `(\\d{1,3}(?:,\\d{3})*|\\d+(?:\\.\\d+)?)\\s*${doseUnitPattern}`,
  "gi",
);

const durationRegexes: Array<{ pattern: RegExp; multiplier: number }> = [
  { pattern: /(\d+(?:\.\d+)?)\s*(년|year|years)/i, multiplier: 365 },
  { pattern: /(\d+(?:\.\d+)?)\s*(개월|달|month|months)/i, multiplier: 30 },
  { pattern: /(\d+(?:\.\d+)?)\s*(주|week|weeks)/i, multiplier: 7 },
  { pattern: /(\d+(?:\.\d+)?)\s*(일|day|days)/i, multiplier: 1 },
];

export function toNullableNumber(value: string) {
  const normalized = value.trim().replace(/,/g, "");
  if (!normalized) return null;

  const parsed = Number(normalized);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function normalizeDailyIntakeUnit(unit: string) {
  const normalized = unit
    .trim()
    .toLowerCase()
    .replace(/µ/g, "u")
    .replace(/\./g, "")
    .replace(/\s+/g, " ");

  if (!normalized) return null;
  if (normalized.includes("rae") && normalized.includes("g")) {
    return "mcg RAE/day";
  }
  if (normalized === "iu" || normalized === "i u" || normalized === "아이유") {
    return "iu/day";
  }
  if (normalized === "mg" || normalized === "밀리그램") {
    return "mg/day";
  }
  if (
    normalized === "mcg" ||
    normalized === "ug" ||
    normalized === "마이크로그램"
  ) {
    return "mcg/day";
  }
  if (normalized === "g" || normalized === "그램") {
    return "g/day";
  }
  if (normalized.endsWith("/day")) {
    return normalized.replace("mcg rae", "mcg RAE");
  }

  return normalized;
}

export function parseDailyIntakeText(text: string): ParsedDailyIntake | null {
  const match = text.match(doseRegex);
  if (!match) return null;

  const value = toNullableNumber(match[1] ?? "");
  const unit = normalizeDailyIntakeUnit(match[2] ?? "");
  if (value === null || !unit) return null;

  if (unit === "g/day") {
    return { value: value * 1000, unit: "mg/day" };
  }

  return { value, unit };
}

export function parseLongTermUseDays(text: string) {
  for (const entry of durationRegexes) {
    const match = text.match(entry.pattern);
    if (!match) continue;

    const value = toNullableNumber(match[1] ?? "");
    if (value !== null) {
      return Math.round(value * entry.multiplier);
    }
  }

  return null;
}

export function removeDoseAndDurationText(text: string) {
  let cleaned = text.replace(allDoseRegex, " ");
  for (const entry of durationRegexes) {
    cleaned = cleaned.replace(entry.pattern, " ");
  }

  return cleaned.replace(/\s+/g, " ").trim();
}

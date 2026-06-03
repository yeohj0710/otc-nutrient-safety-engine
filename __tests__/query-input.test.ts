import { describe, expect, it } from "vitest";

import {
  normalizeDailyIntakeUnit,
  parseDailyIntakeText,
  parseLongTermUseDays,
  removeDoseAndDurationText,
  toNullableNumber,
} from "@/src/lib/query-input";

describe("query input parsing", () => {
  it("extracts vitamin D IU dose from a free text ingredient entry", () => {
    expect(parseDailyIntakeText("비타민 D 5000 IU")).toEqual({
      value: 5000,
      unit: "iu/day",
    });
  });

  it("converts gram input to mg/day for fish oil style doses", () => {
    expect(parseDailyIntakeText("fish oil 4 g")).toEqual({
      value: 4000,
      unit: "mg/day",
    });
  });

  it("parses long term use phrases into days", () => {
    expect(parseLongTermUseDays("B6 50mg 6개월")).toBe(180);
  });

  it("normalizes manual unit and numeric input", () => {
    expect(toNullableNumber("1,200")).toBe(1200);
    expect(normalizeDailyIntakeUnit("mcg RAE/day")).toBe("mcg RAE/day");
  });

  it("removes dose and duration terms before ingredient lookup", () => {
    expect(removeDoseAndDurationText("vitamin B6 50mg 6개월")).toBe(
      "vitamin B6",
    );
  });
});

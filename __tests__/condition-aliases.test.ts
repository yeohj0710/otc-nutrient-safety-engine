import { describe, expect, it } from "vitest";

import {
  getConditionAliases,
  getConditionDisplayLabel,
  getConditionPresetCanonicalValues,
} from "@/src/lib/knowledge/condition-aliases";

describe("condition aliases", () => {
  it("includes common user-facing condition keywords such as obesity", () => {
    expect(getConditionDisplayLabel("obesity")).toBe("비만");
    expect(getConditionAliases("obesity")).toContain("비만");
    expect(getConditionPresetCanonicalValues()).toContain("obesity");
  });
});

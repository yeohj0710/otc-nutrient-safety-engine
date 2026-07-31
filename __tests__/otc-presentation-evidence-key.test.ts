import { describe, expect, it } from "vitest";

import { groupFindingsForDisplay } from "@/src/lib/otc/presentation";
import type { SafetyFinding } from "@/src/lib/otc/schema";

const duplicateFinding = (
  findingId: string,
  ingredientId: string,
  sourceVersion: string,
): SafetyFinding => ({
  findingId,
  ruleId: "OTC-RULE-001",
  decisionBasis: "released_rule",
  ruleType: "duplicate_ingredient",
  severity: "high",
  titleKo: "같은 성분이 여러 제품에 들어 있습니다",
  detailKo: `${ingredientId} 성분이 겹칩니다.`,
  nextActionKo: "포장과 허가사항을 확인하세요.",
  productIds: ["P1", "P2"],
  ingredientIds: [ingredientId],
  evidence: [
    {
      sourceId: "MFDS-ITEM-TEST",
      sourceVersion,
      locator: "p.2 paragraph 7",
      url: "https://example.test/mfds-item.pdf",
    },
  ],
});

describe("presentation evidence identity", () => {
  it("keeps different source snapshots at the same locator distinct", () => {
    const firstSnapshot = duplicateFinding(
      "duplicate:A",
      "ING-A",
      "sha256:first-snapshot",
    );
    const duplicateFirstSnapshot = duplicateFinding(
      "duplicate:B",
      "ING-B",
      "sha256:first-snapshot",
    );
    const secondSnapshot = duplicateFinding(
      "duplicate:C",
      "ING-C",
      "sha256:second-snapshot",
    );

    const [grouped] = groupFindingsForDisplay(
      [firstSnapshot, duplicateFirstSnapshot, secondSnapshot],
      new Map(),
    );

    expect(grouped.evidence).toHaveLength(2);
    expect(grouped.evidence.map((evidence) => evidence.sourceVersion)).toEqual([
      "sha256:first-snapshot",
      "sha256:second-snapshot",
    ]);
  });
});

import { expect, it } from "vitest";
import { isRetractedPublication } from "@/src/lib/publication-status";
import pool from "@/src/generated/recollect/rule-literature-pool.json";

it("recognizes withdrawn records that remain in the bibliographic archive", () => {
  const withdrawn = Object.values(pool.papers).filter((paper) => isRetractedPublication(paper.publication_types));
  expect(withdrawn.map((paper) => paper.record_id).sort()).toEqual(["PMID-22266604", "PMID-40557054"]);
});

it("distinguishes retraction notices from ordinary errata", () => {
  expect(isRetractedPublication(" Retraction of Publication ")).toBe(true);
  expect(isRetractedPublication("Journal Article|Published Erratum")).toBe(false);
});

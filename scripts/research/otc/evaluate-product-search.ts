import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { searchOtcProducts } from "../../../src/lib/otc/search";
import type { OtcProduct } from "../../../src/lib/otc/schema";

const root = resolve(import.meta.dirname, "../../..");
const casesPath = resolve(root, "research_v3/otc/validation/product_search_cases.csv");
const runtimePath = resolve(root, "src/generated/otc-runtime.json");
const outputPath = resolve(root, "research_v3/otc/validation/product_search_evaluation.json");
const canonicalText = (path: string) =>
  readFileSync(path, "utf8")
    .replace(/^\uFEFF/, "")
    .replace(/\r\n?/g, "\n");
const sha256 = (path: string) =>
  createHash("sha256").update(canonicalText(path), "utf8").digest("hex");

const lines = readFileSync(casesPath, "utf8").replace(/^\uFEFF/, "").trim().split(/\r?\n/);
const fields = lines[0].split(",");
const cases = lines.slice(1).map((line) => Object.fromEntries(fields.map((field, index) => [field, line.split(",")[index]])));
const runtime = JSON.parse(readFileSync(runtimePath, "utf8")) as { products: OtcProduct[]; officialCandidates: Array<{ productName: string }> };
const results = cases.map((item) => {
  const found = searchOtcProducts(runtime.products, runtime.officialCandidates, item.query).verified.map((product) => product.itemSequence);
  return { case_id: item.case_id, case_type: item.case_type, query: item.query, expected_item_sequence: item.expected_item_sequence, found_item_sequences: found, success: found.includes(item.expected_item_sequence) };
});
const successes = results.filter((item) => item.success).length;
const payload = { schema_version: "1.0.0", status: "evaluated_fixed_development_cases_not_external_user_study", cases: results.length, successes, value: successes / results.length, cases_sha256: sha256(casesPath), runtime_sha256: sha256(runtimePath), results };
writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ cases: results.length, successes, value: payload.value }));

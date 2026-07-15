import { createHash } from "node:crypto";
import { readFileSync, renameSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  predictLockedIndependentScenarios,
  type IndependentScenarioIndexRow,
  type IndependentScenarioPayload,
  type ReleasedRuntime,
} from "../../../src/lib/otc/independent-evaluation";

const root = resolve(import.meta.dirname, "../../..");
const validation = resolve(root, "research_v3/otc/validation");
const indexPath = resolve(validation, "independent_scenarios.csv");
const runtimePath = resolve(root, "src/generated/otc-runtime.json");
const auditPath = resolve(validation, "independent_prediction_audit.json");

function parseCsv(text: string): { fields: string[]; rows: Record<string, string>[] } {
  const lines = text.replace(/^\uFEFF/, "").trimEnd().split(/\r?\n/);
  const fields = lines[0].split(",");
  return { fields, rows: lines.slice(1).map((line) => Object.fromEntries(fields.map((field, index) => [field, line.split(",")[index] ?? ""]))) };
}

function csv(fields: string[], rows: Record<string, string>[]): string {
  return `\uFEFF${fields.join(",")}\r\n${rows.map((row) => fields.map((field) => row[field] ?? "").join(",")).join("\r\n")}\r\n`;
}

function sha256(path: string): string {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

const parsed = parseCsv(readFileSync(indexPath, "utf8"));
const rows = parsed.rows as IndependentScenarioIndexRow[];
const payloads = rows.map((row) => JSON.parse(readFileSync(resolve(validation, row.case_payload_ref), "utf8")) as IndependentScenarioPayload);
const runtime = JSON.parse(readFileSync(runtimePath, "utf8")) as ReleasedRuntime;
const predictions = predictLockedIndependentScenarios(rows, payloads, runtime);
const byId = new Map(predictions.map((item) => [item.scenarioId, item]));
const updated = parsed.rows.map((row) => ({ ...row, prediction: byId.get(row.scenario_id)!.prediction, status: "human_label_locked_prediction_recorded" }));
const temporary = `${indexPath}.tmp`;
writeFileSync(temporary, csv(parsed.fields, updated), "utf8");
renameSync(temporary, indexPath);
writeFileSync(auditPath, `${JSON.stringify({
  schema_version: "1.0.0",
  research_direction: "korean_otc_product_safety",
  prediction_mode: "deterministic_released_rules_only",
  scenarios: predictions,
  runtime_sha256: sha256(runtimePath),
  case_payload_sha256: Object.fromEntries(rows.map((row) => [row.scenario_id, sha256(resolve(validation, row.case_payload_ref))])),
}, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ predictions: predictions.length, released_rule_types: runtime.releasedRuleTypes.length, audit: auditPath }));

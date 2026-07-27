/**
 * P3-B 규칙엔진 예측 기록기.
 *
 * 이 스크립트는 AI 참조 라벨이 잠긴 뒤에만 실행한다. 잠금 파일의 SHA-256 을 먼저 검증하고,
 * 그 다음에야 배포된 규칙만으로 엔진 예측을 계산해 감사 로그에 기록한다. 참조 라벨은 읽지
 * 않으며(잠금 파일에서 case_id 목록과 해시만 사용), 지표 계산도 하지 않는다. 지표는
 * `tools/ai_independent_eval.py finalize` 가 잠금 시각 < 예측 시각을 검증한 뒤 계산한다.
 */
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { evaluateOtcSafety } from "../../../src/lib/otc/engine";
import type { OtcProduct, SelectedProduct, UserProfile } from "../../../src/lib/otc/schema";

// tsx 가 CJS 로 변환하면 import.meta.dirname 이 undefined 라 저장소 루트에서 실행하는 것을 전제로 한다.
const root = process.cwd();
if (!existsSync(resolve(root, "package.json"))) {
  throw new Error(`run_from_repository_root: ${root}`);
}
const validation = resolve(root, "research_v3/otc/validation");
const caseDir = resolve(validation, "ai_independent_cases");
const legacyCaseDir = resolve(validation, "independent_cases");
const evalDir = resolve(validation, "ai_independent_evaluation");
const lockPath = resolve(evalDir, "ai_reference_labels.locked.json");
const lockDigestPath = resolve(evalDir, "ai_reference_labels.lock.sha256.json");
const runtimePath = resolve(root, "src/generated/otc-runtime.json");
const auditPath = resolve(evalDir, "ai_independent_prediction_audit.json");

type VerifiedProductInput = {
  inputType: "verified_product";
  itemSequence: string;
  unitsPerDose: number;
  dosesPerDay: number;
  hoursSincePreviousDose?: number;
  continuousDays?: number;
};
type ProductSearchInput = { inputType: "product_search_query"; productNameQuery: string };
type CasePayload = {
  caseId?: string;
  scenarioId?: string;
  productInputs: Array<VerifiedProductInput | ProductSearchInput>;
  userProfile: UserProfile;
  referenceLabel?: null;
  prediction?: null;
};
type ReleasedRuntime = {
  rulesReleased: number;
  releasedRuleTypes: string[];
  products: OtcProduct[];
  urgentReferralBindings?: Array<{ itemSequence: string; terms: string[] }>;
};

function sha256(path: string): string {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function readJson<T>(path: string): T {
  return JSON.parse(readFileSync(path, "utf8").replace(/^﻿/, "")) as T;
}

// 1) 잠금 검증. 해시가 어긋나면 예측을 시작조차 하지 않는다.
const lockDigest = readJson<{ locked_file: string; sha256: string; locked_at_utc: string }>(
  lockDigestPath,
);
const actualLockSha = sha256(lockPath);
if (actualLockSha !== lockDigest.sha256) {
  throw new Error(`lock_sha256_mismatch expected=${lockDigest.sha256} actual=${actualLockSha}`);
}

const lock = readJson<{
  created_at_utc: string;
  cases_total: number;
  labels: Array<{ case_id: string; track: string; target_rule_type: string | null }>;
}>(lockPath);

// 2) 배포 런타임 확인. 배포 규칙 수와 규칙 유형 수가 어긋나면 예측하지 않는다.
const runtime = readJson<ReleasedRuntime>(runtimePath);
if (!runtime.rulesReleased || runtime.releasedRuleTypes.length !== runtime.rulesReleased) {
  throw new Error("released_runtime_required_for_prediction");
}

const productBySequence = new Map(runtime.products.map((product) => [product.itemSequence, product]));
const enabledRuleTypes = new Set(runtime.releasedRuleTypes);

function loadCase(caseId: string): CasePayload {
  const path = caseId.startsWith("AIC-OTC-")
    ? resolve(caseDir, `${caseId}.json`)
    : resolve(legacyCaseDir, `${caseId}.json`);
  const payload = readJson<CasePayload>(path);
  if (payload.referenceLabel != null || payload.prediction != null) {
    throw new Error(`case_payload_must_remain_blinded:${caseId}`);
  }
  return payload;
}

const cases = lock.labels.map((entry) => {
  const payload = loadCase(entry.case_id);
  const selected: SelectedProduct[] = payload.productInputs.flatMap((input) => {
    if (input.inputType !== "verified_product") return [];
    const product = productBySequence.get(input.itemSequence);
    if (!product) {
      throw new Error(`verified_product_missing_from_runtime:${entry.case_id}:${input.itemSequence}`);
    }
    return [
      {
        product,
        unitsPerDose: input.unitsPerDose,
        dosesPerDay: input.dosesPerDay,
        hoursSincePreviousDose: input.hoursSincePreviousDose,
        continuousDays: input.continuousDays,
      },
    ];
  });
  const result = evaluateOtcSafety(
    selected,
    payload.userProfile,
    enabledRuleTypes,
    runtime.urgentReferralBindings ?? [],
  );
  const findingRuleTypes = [...new Set(result.findings.map((finding) => finding.ruleType))].sort();
  return {
    caseId: entry.case_id,
    track: entry.track,
    targetRuleType: entry.target_rule_type,
    enginePositive: findingRuleTypes.length > 0,
    findingRuleTypes,
  };
});

const audit = {
  schema_version: "1.0.0",
  research_direction: "korean_otc_product_safety",
  prediction_mode: "deterministic_released_rules_only",
  purpose_ko:
    "P3-B AI 맹검 독립평가의 엔진 예측 기록. 잠금 파일 해시를 검증한 뒤에만 예측했다.",
  predicted_at_utc: new Date().toISOString(),
  verified_lock_sha256: actualLockSha,
  locked_at_utc: lockDigest.locked_at_utc,
  runtime_sha256: sha256(runtimePath),
  rules_released: runtime.rulesReleased,
  releasedRuleTypes: [...runtime.releasedRuleTypes].sort(),
  cases_total: cases.length,
  engine_positive_count: cases.filter((item) => item.enginePositive).length,
  reference_labels_read: false,
  human_labels_read: false,
  cases,
};
writeFileSync(auditPath, `${JSON.stringify(audit, null, 2)}\n`, "utf8");
console.log(
  JSON.stringify({
    cases: cases.length,
    engine_positive: audit.engine_positive_count,
    released_rule_types: runtime.releasedRuleTypes.length,
    verified_lock_sha256: actualLockSha,
  }),
);

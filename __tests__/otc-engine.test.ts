import { describe, expect, it } from "vitest";
import { evaluateOtcSafety } from "@/src/lib/otc/engine";
import type { OtcProduct, UserProfile } from "@/src/lib/otc/schema";

const evidence = { sourceId: "TEST-SOURCE", locator: "검증용 원문 위치", url: "https://example.test/source" };
const ingredient = (ingredientId: string, nameKo: string, classes: string[], flags: string[] = []) => ({ ingredientId, nameKo, amountPerUnit: 100, unit: "mg" as const, pharmacologicClasses: classes, maxDailyAmount: 300, minimumIntervalHours: 4, flags, evidence });
const product = (productId: string, productName: string, ingredients: ReturnType<typeof ingredient>[], flags: string[] = []): OtcProduct => ({ productId, itemSequence: productId, productName, classification: "일반의약품", authorizationStatus: "active", doseUnitLabel: "정", ingredients, flags, evidence });
const profile = (values: Partial<UserProfile> = {}): UserProfile => ({ medications: [], redFlagSymptoms: [], ...values });

describe("deterministic OTC safety engine", () => {
  it("detects duplicate ingredients and calculates the selected-product daily total", () => {
    const same = ingredient("ING-test", "검증성분", []);
    const result = evaluateOtcSafety([
      { product: product("P1", "검증제품1", [same]), unitsPerDose: 1, dosesPerDay: 2 },
      { product: product("P2", "검증제품2", [same]), unitsPerDose: 1, dosesPerDay: 2 },
    ], profile());
    expect(result.ingredientDailyTotals["ING-test"]).toEqual({ amount: 400, unit: "mg" });
    expect(result.findings.map((finding) => finding.ruleType)).toEqual(expect.arrayContaining(["duplicate_ingredient", "max_daily_dose"]));
    expect(result.decisionMode).toBe("deterministic");
  });

  it("detects different ingredients in the same NSAID class", () => {
    const result = evaluateOtcSafety([
      { product: product("P1", "검증NSAID1", [ingredient("I1", "검증NSAID성분1", ["NSAID"])]), unitsPerDose: 1, dosesPerDay: 1 },
      { product: product("P2", "검증NSAID2", [ingredient("I2", "검증NSAID성분2", ["NSAID"])]), unitsPerDose: 1, dosesPerDay: 1 },
    ], profile());
    expect(result.findings.some((finding) => finding.ruleType === "duplicate_pharmacologic_class")).toBe(true);
  });

  it("detects different first- and second-generation antihistamines through their shared class", () => {
    const result = evaluateOtcSafety([
      { product: product("P1", "감기약", [ingredient("I1", "클로르페니라민", ["antihistamine", "first_generation_antihistamine"])]), unitsPerDose: 1, dosesPerDay: 1 },
      { product: product("P2", "알레르기약", [ingredient("I2", "세티리진", ["antihistamine", "second_generation_antihistamine"])]), unitsPerDose: 1, dosesPerDay: 1 },
    ], profile());
    expect(result.findings.some((finding) => finding.findingId === "duplicate-class:antihistamine")).toBe(true);
  });

  it("returns only explicitly released rule types when an enablement set is supplied", () => {
    const same = ingredient("ING-test", "검증성분", []);
    const result = evaluateOtcSafety([
      { product: product("P1", "검증제품1", [same]), unitsPerDose: 2, dosesPerDay: 2 },
      { product: product("P2", "검증제품2", [same]), unitsPerDose: 1, dosesPerDay: 1 },
    ], profile(), new Set(["duplicate_ingredient"]));
    expect(result.findings.map((finding) => finding.ruleType)).toEqual(["duplicate_ingredient"]);
  });

  it("detects interval, age, duration, disease, medication, driving, alcohol, and urgent conditions", () => {
    const flagged = ingredient("I1", "검증성분", [], ["sedation_driving", "alcohol", "renal_disease", "anticoagulant_antiplatelet"]);
    const p = { ...product("P1", "검증제품", [flagged], ["decongestant_hypertension"]), minimumAgeYears: 12, maximumContinuousDays: 3 };
    const result = evaluateOtcSafety([{ product: p, unitsPerDose: 1, dosesPerDay: 1, hoursSincePreviousDose: 2, continuousDays: 4 }], profile({ ageYears: 10, kidneyDisease: true, willDrive: true, alcohol: true, hypertensionOrCardiovascularDisease: true, medications: ["와파린"], redFlagSymptoms: ["호흡곤란"] }));
    const types = new Set(result.findings.map((finding) => finding.ruleType));
    expect(types).toEqual(new Set(["urgent_referral", "age_restriction", "alcohol", "anticoagulant_antiplatelet", "decongestant_hypertension", "maximum_duration", "minimum_interval", "renal_disease", "sedation_driving"]));
    expect(result.findings[0].severity).toBe("urgent");
  });

  it("returns no findings for a supported normal-use fixture", () => {
    const p = product("P1", "검증제품", [ingredient("I1", "검증성분", [])]);
    expect(evaluateOtcSafety([{ product: p, unitsPerDose: 1, dosesPerDay: 1, hoursSincePreviousDose: 6 }], profile()).findings).toEqual([]);
  });

  it("matches urgent symptoms only for the product and terms in a released binding", () => {
    const p = product("202106092", "타이레놀", [ingredient("I1", "아세트아미노펜", [])]);
    const bindings = [{ itemSequence: "202106092", terms: ["호흡곤란", "얼굴부기"] }];
    const matched = evaluateOtcSafety([{ product: p, unitsPerDose: 1, dosesPerDay: 1 }], profile({ redFlagSymptoms: ["심한 호흡곤란"] }), new Set(["urgent_referral"]), bindings);
    expect(matched.findings.map((finding) => finding.ruleType)).toEqual(["urgent_referral"]);
  });

  it("does not turn arbitrary symptoms or another product into an urgent finding", () => {
    const other = product("OTHER", "다른 제품", [ingredient("I1", "검증성분", [])]);
    const bindings = [{ itemSequence: "202106092", terms: ["호흡곤란"] }];
    expect(evaluateOtcSafety([{ product: other, unitsPerDose: 1, dosesPerDay: 1 }], profile({ redFlagSymptoms: ["호흡곤란"] }), new Set(["urgent_referral"]), bindings).findings).toEqual([]);
    expect(evaluateOtcSafety([{ product: { ...other, itemSequence: "202106092" }, unitsPerDose: 1, dosesPerDay: 1 }], profile({ redFlagSymptoms: ["가벼운 콧물"] }), new Set(["urgent_referral"]), bindings).findings).toEqual([]);
  });
});

import { describe, expect, it } from "vitest";

import {
  buildSelectedProducts,
  searchRuntime,
  type OtcRuntime,
} from "@/src/components/otc-product-safety-client";
import type { OtcProduct } from "@/src/lib/otc/schema";

const product = (productId: string, productName: string): OtcProduct => ({
  productId,
  itemSequence: productId,
  productName,
  classification: "일반의약품",
  authorizationStatus: "active",
  doseUnitLabel: "정",
  ingredients: [],
  flags: [],
  evidence: {
    sourceId: "TEST-SOURCE",
    locator: "검증용 원문 위치",
    url: "https://example.test/source",
  },
});

const runtime: OtcRuntime = {
  schemaVersion: "1.0.0",
  generatedAt: "2026-07-14",
  researchDirection: "korean_otc_product_safety",
  releaseReady: false,
  rulesReleased: 0,
  releasedRuleTypes: [],
  products: [product("P1", "검증제품1"), product("P2", "검증제품2")],
  officialCandidates: [
    { candidateId: "C1", productName: "검증대기감기정", className: "종합감기약", status: "authorization_pending" },
  ],
};

describe("product-name search flow", () => {
  it("shows no results before the user searches", () => {
    expect(searchRuntime(runtime, "")).toEqual({ verified: [], candidates: [] });
  });

  it("returns an official candidate separately from selectable verified products", () => {
    expect(searchRuntime(runtime, "감기")).toEqual({ verified: [], candidates: runtime.officialCandidates });
  });

  it("does not convert an unsupported name into a guessed product", () => {
    expect(searchRuntime(runtime, "없는제품")).toEqual({ verified: [], candidates: [] });
  });

  it("builds a quick-check selection in requested order without unknowns or duplicates", () => {
    expect(buildSelectedProducts(runtime, ["P2", "UNKNOWN", "P1", "P2"])).toEqual([
      { product: runtime.products[1], unitsPerDose: 1, dosesPerDay: 1 },
      { product: runtime.products[0], unitsPerDose: 1, dosesPerDay: 1 },
    ]);
  });
});

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const componentSource = readFileSync(
  resolve(process.cwd(), "src/components/otc-product-safety-client.tsx"),
  "utf8",
);
const styleSource = readFileSync(
  resolve(process.cwd(), "src/components/otc-product-safety.module.css"),
  "utf8",
);

describe("OTC checker layout contract", () => {
  it("keeps the two input panels in one independent flow column", () => {
    expect(componentSource).toContain("className={styles.inputColumn}");
    expect(styleSource).toContain(".inputColumn");
    expect(styleSource).not.toContain("grid-row: 1 / span 2");
  });

  it("uses a left-aligned uniform grid for example actions", () => {
    expect(styleSource).toMatch(
      /\.quickCheckList\s*\{[\s\S]*?grid-template-columns:[\s\S]*?justify-content:\s*start/,
    );
    expect(componentSource).not.toContain(
      "<small>{quickCheck.description}</small>",
    );
  });

  it("separates authorization evidence from reference literature in wording and markup", () => {
    // 판정 근거는 허가원문, 문헌은 설명용. 화면에서 두 블록이 분리돼 있어야 한다.
    expect(componentSource).toContain('aria-label="판정에 사용한 식약처 허가 근거"');
    expect(componentSource).toContain('aria-label="참고 문헌 · 판정 근거 아님"');
    expect(componentSource).toContain("<strong>판정 규칙 근거</strong>");
    expect(componentSource).toContain("<strong>참고 문헌</strong>");
    expect(componentSource).toContain("판정 근거 아님");
    // 요약 줄도 두 축을 나눠 센다.
    expect(componentSource).toContain("판정 근거(식약처 허가원문)");
    // 예전 표현이 남아 있으면 문헌이 판정 근거처럼 읽힌다.
    expect(componentSource).not.toContain("직접 연결 학술문헌");
  });

  it("always shows the literature disclaimer next to reference papers", () => {
    expect(componentSource).toContain(
      "참고 문헌은 판정 근거가 아니며 허가원문 판정을 바꾸지 않습니다.",
    );
    expect(componentSource).toContain("styles.literatureDisclaimer");
    expect(styleSource).toContain(".literatureDisclaimer");
  });

  it("shows the sentence-level locator and preserved authorization conflicts", () => {
    expect(componentSource).toContain("styles.literatureLocator");
    expect(componentSource).toContain("link.locatorQuoteEn");
    expect(componentSource).toContain('authorizationAlignment === "conflict"');
    expect(componentSource).toContain("<strong>허가원문과 다른 점</strong>");
    expect(styleSource).toContain(".literatureConflict");
  });

  it("announces a non-blocking calculation state with reduced-motion support", () => {
    expect(componentSource).toContain("aria-busy={isEvaluating}");
    expect(componentSource).toContain("styles.calculationStatus");
    expect(styleSource).toContain("@keyframes calculationSpin");
    expect(styleSource).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.calculationSpinner/,
    );
  });
});

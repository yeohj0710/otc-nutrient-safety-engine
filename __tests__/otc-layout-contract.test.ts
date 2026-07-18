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

  it("announces a non-blocking calculation state with reduced-motion support", () => {
    expect(componentSource).toContain("aria-busy={isEvaluating}");
    expect(componentSource).toContain("styles.calculationStatus");
    expect(styleSource).toContain("@keyframes calculationSpin");
    expect(styleSource).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.calculationSpinner/,
    );
  });
});

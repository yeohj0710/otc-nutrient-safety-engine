import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import manifest from "@/app/manifest";
import sitemap from "@/app/sitemap";

const readSource = (path: string) =>
  readFileSync(resolve(process.cwd(), path), "utf8");

describe("active OTC site boundary", () => {
  it("publishes only the active checker and v5.0 research page in the sitemap", () => {
    const paths = sitemap().map((entry) => new URL(entry.url).pathname);

    expect(paths).toEqual(["/", "/research"]);
  });

  it("names the installed app after the current OTC checker", () => {
    const appManifest = manifest();

    expect(appManifest.name).toBe("국내 일반의약품 안전성 조회 시스템");
    expect(appManifest.short_name).toBe("OTC 함께복용 점검");
    expect(appManifest.start_url).toBe("/");
  });

  it("keeps legacy ingredient and rule pages out of search indexes", () => {
    const ingredientIndex = readSource("app/ingredients/page.tsx");
    const ruleDetail = readSource("app/rules/[id]/page.tsx");

    expect(ingredientIndex).toMatch(
      /robots:\s*\{\s*index:\s*false,\s*follow:\s*false,?\s*\}/,
    );
    expect(ruleDetail.match(/index:\s*false/g)).toHaveLength(2);
    expect(ruleDetail.match(/follow:\s*false/g)).toHaveLength(2);
  });
});

describe("shared site accessibility shell", () => {
  const auxiliaryScreens = [
    "app/loading.tsx",
    "app/not-found.tsx",
    "app/error.tsx",
    "app/global-error.tsx",
    "app/ingredients/page.tsx",
    "app/ingredients/[id]/page.tsx",
    "app/rules/[id]/page.tsx",
    "app/sources/page.tsx",
    "app/sources/[id]/page.tsx",
    "src/components/research-summary.tsx",
    "src/components/research-v3-explorer.tsx",
  ];

  it.each(auxiliaryScreens)("provides a focusable skip target in %s", (path) => {
    const source = readSource(path);

    expect(source).toContain('id="main-content"');
    expect(source).toContain("tabIndex={-1}");
  });

  it("moves focus to the main landmark even when a page omitted tabIndex", () => {
    const frame = readSource("src/components/site-frame.tsx");

    expect(frame).toContain('href="#main-content"');
    expect(frame).toContain('document.getElementById("main-content")');
    expect(frame).toContain("target.tabIndex = -1");
    expect(frame).toContain("target.focus()");
  });

  it("uses the shared shell, spacing, touch, focus, safe-area, and motion contracts", () => {
    const css = readSource("app/globals.css");

    expect(css).toContain("--page-shell-max: 77.5rem");
    expect(css).toContain("--space-1: 0.25rem");
    expect(css).toContain("--space-8: 2rem");
    expect(css).toContain("--control-min-size: 2.75rem");
    expect(css).toContain("env(safe-area-inset-left)");
    expect(css).toContain("env(safe-area-inset-right)");
    expect(css).toContain('.collapsible-panel[data-open="false"]');
    expect(css).toMatch(
      /\.collapsible-panel\[data-open="false"\][\s\S]*?visibility:\s*hidden/,
    );
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});

import os from "node:os";
import path from "node:path";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";

import { afterEach, describe, expect, it } from "vitest";

import { buildKnowledgeIndex } from "@/src/lib/knowledge/normalize";

const tempDirs: string[] = [];

async function createProjectRoot() {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "knowledge-normalize-"));
  tempDirs.push(projectRoot);
  await mkdir(path.join(projectRoot, "data"), { recursive: true });
  return projectRoot;
}

async function writeJson(projectRoot: string, relativePath: string, value: unknown) {
  await writeFile(path.join(projectRoot, relativePath), `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function buildKnowledgePack(packageName: string, ingredientId: string) {
  return {
    package_meta: {
      package_name: packageName,
      version: "1.0.0",
      generated_at: "2026-03-23T00:00:00.000Z",
      description_ko: `${packageName} description`,
    },
    sources: [
      {
        source_id: `${ingredientId}-source`,
        title: `${ingredientId} source`,
        source_type: "government_fact_sheet",
        publication_year: 2026,
        publication_date: "2026-03-23",
        url: `https://example.com/${ingredientId}`,
        evidence_tier: "high",
      },
    ],
    ingredients: [
      {
        ingredient_id: ingredientId,
        ingredient_name_ko: `${ingredientId} ko`,
        ingredient_name_en: `${ingredientId} en`,
      },
    ],
    evidence_chunks: [
      {
        chunk_id: `${ingredientId}-chunk`,
        source_id: `${ingredientId}-source`,
        ingredient_ids: [ingredientId],
        locator: {
          locator_type: "abstract",
          locator_value: "Results",
        },
        excerpt_summary_ko: `${ingredientId} excerpt`,
        quote_original: `${ingredientId} original quote`,
        quote_translation_ko: `${ingredientId} translated quote`,
        verification_status: "verified_against_source",
        extraction_method: "manual_from_source",
        quote_capture_status: "verified_short_excerpt",
        used_in_rule_ids: [],
        quote_original_word_count: 3,
        verbatim_note_ko: `${ingredientId} note`,
        confidence: "high",
      },
    ],
    safety_rules: [
      {
        rule_id: `${ingredientId}-rule`,
        ingredient_id: ingredientId,
        rule_name_ko: `${ingredientId} rule`,
        rule_category: "dose_limit",
        severity: "warn",
        priority: 1,
        action_text_ko: `${ingredientId} should be limited`,
        rationale_ko: `${ingredientId} rationale`,
        evidence_chunk_ids: [`${ingredientId}-chunk`],
        source_ids: [`${ingredientId}-source`],
      },
    ],
  };
}

afterEach(async () => {
  await Promise.all(tempDirs.splice(0).map((directory) => rm(directory, { recursive: true, force: true })));
});

describe("buildKnowledgeIndex", () => {
  it("uses knowledge_pack.json as the single source of truth when it exists", async () => {
    const projectRoot = await createProjectRoot();

    await writeJson(projectRoot, "data/knowledge_pack.json", buildKnowledgePack("pack-primary", "pack_ing"));
    await writeJson(projectRoot, "data/source_registry.json", [
      {
        source_id: "legacy-source",
        title: "legacy source",
        source_type: "review",
      },
    ]);
    await writeJson(projectRoot, "data/ingredients.json", [
      {
        ingredient_id: "legacy_ing",
        ingredient_name_ko: "legacy ingredient",
      },
    ]);
    await writeJson(projectRoot, "data/evidence_chunks.json", [
      {
        chunk_id: "legacy-chunk",
        source_id: "legacy-source",
      },
    ]);
    await writeJson(projectRoot, "data/safety_rules.json", [
      {
        rule_id: "legacy-rule",
        ingredient_id: "legacy_ing",
        rule_name_ko: "legacy rule",
        rule_category: "dose_limit",
        severity: "warn",
        priority: 99,
        action_text_ko: "legacy action",
        rationale_ko: "legacy rationale",
      },
    ]);

    const knowledgeIndex = await buildKnowledgeIndex(projectRoot);

    expect(knowledgeIndex.meta.dataSource).toBe("knowledge_pack");
    expect(knowledgeIndex.meta.packageName).toBe("pack-primary");
    expect(knowledgeIndex.meta.originalExcerptCount).toBe(1);
    expect(knowledgeIndex.meta.verifiedAgainstSourceCount).toBe(1);
    expect(knowledgeIndex.meta.pendingManualExtractionCount).toBe(0);
    expect(knowledgeIndex.ingredients.map((ingredient) => ingredient.id)).toEqual(["pack_ing"]);
    expect(knowledgeIndex.safetyRules.map((rule) => rule.id)).toEqual(["pack_ing-rule"]);
    expect(knowledgeIndex.evidenceChunks[0]).toMatchObject({
      locatorType: "abstract",
      locatorValue: "Results",
      quoteOriginal: "pack_ing original quote",
      quoteTranslationKo: "pack_ing translated quote",
      verificationStatus: "verified_against_source",
      extractionMethod: "manual_from_source",
      quoteCaptureStatus: "verified_short_excerpt",
      quoteOriginalWordCount: 3,
      verbatimNoteKo: "pack_ing note",
      usedInRuleIds: ["pack_ing-rule"],
    });
  });

  it("throws when knowledge_pack.json exists but is malformed instead of silently falling back", async () => {
    const projectRoot = await createProjectRoot();

    await writeFile(path.join(projectRoot, "data", "knowledge_pack.json"), "{ invalid json", "utf8");
    await writeJson(projectRoot, "data/source_registry.json", []);
    await writeJson(projectRoot, "data/ingredients.json", []);
    await writeJson(projectRoot, "data/evidence_chunks.json", []);
    await writeJson(projectRoot, "data/safety_rules.json", []);

    await expect(buildKnowledgeIndex(projectRoot)).rejects.toThrow();
  });
});

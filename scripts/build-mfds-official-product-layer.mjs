import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import {
  readMfdsManifest,
  streamMfdsDataset,
} from "./kr-drug-data-reader.mjs";

const repositoryRoot = resolve(import.meta.dirname, "..");
const runtimePath = resolve(repositoryRoot, "src/generated/otc-runtime.json");
const outputPath = resolve(
  repositoryRoot,
  "src/generated/otc-official-product-info.json",
);

const runtime = JSON.parse(await readFile(runtimePath, "utf8"));
if (!Array.isArray(runtime.products) || runtime.products.length === 0) {
  throw new Error("otc-runtime.json has no products");
}

const productsByItemSequence = new Map(
  runtime.products.map((product) => [product.itemSequence, product]),
);
if (productsByItemSequence.size !== runtime.products.length) {
  throw new Error("otc-runtime.json contains duplicate itemSequence values");
}

const manifest = await readMfdsManifest("permit");
if (
  manifest.candidateOnly !== true ||
  manifest.clinicalUseProhibited !== true
) {
  throw new Error("Unsafe MFDS permit manifest");
}

const matches = new Map();
for await (const row of streamMfdsDataset("permit")) {
  const itemSequence = String(row.itemSeq ?? row.fields?.ITEM_SEQ ?? "");
  if (!productsByItemSequence.has(itemSequence)) continue;
  if (matches.has(itemSequence)) {
    throw new Error(`Duplicate permit itemSeq: ${itemSequence}`);
  }

  const fields = row.fields ?? {};
  matches.set(itemSequence, {
    itemSequence,
    productId: productsByItemSequence.get(itemSequence).productId,
    runtimeProductName: productsByItemSequence.get(itemSequence).productName,
    officialProductName: fields.ITEM_NAME ?? row.productName ?? null,
    official: {
      materialName: fields.MATERIAL_NAME ?? null,
      dosageForm: fields.CHART ?? null,
      classification: fields.ETC_OTC_CODE ?? null,
      authorizationStatus: fields.CANCEL_NAME ?? null,
    },
    source: {
      dataset: "permit",
      provider: row.provider ?? manifest.provider ?? null,
      itemSequenceField: "itemSeq",
      officialFields: {
        materialName: "MATERIAL_NAME",
        dosageForm: "CHART",
        classification: "ETC_OTC_CODE",
        authorizationStatus: "CANCEL_NAME",
      },
    },
  });
}

const missingItemSequences = runtime.products
  .map((product) => product.itemSequence)
  .filter((itemSequence) => !matches.has(itemSequence));

const output = {
  schemaVersion: "1.0.0",
  generatedAt: new Date().toISOString(),
  candidateOnly: manifest.candidateOnly,
  clinicalUseProhibited: manifest.clinicalUseProhibited,
  source: {
    dataset: "permit",
    manifestGeneratedAt: manifest.generatedAt,
    recordCount: manifest.recordCount,
    expectedRecordCount: manifest.expectedRecordCount,
    catalogSha256: manifest.catalogSha256,
    sourceSnapshot: manifest.sourceSnapshot,
    joinKey: "itemSeq",
  },
  products: runtime.products.map((product) => matches.get(product.itemSequence)),
  matching: {
    requestedCount: runtime.products.length,
    matchedCount: matches.size,
    missingItemSequences,
  },
};

if (missingItemSequences.length > 0) {
  throw new Error(
    `Permit catalog matching failed for itemSequence: ${missingItemSequences.join(", ")}`,
  );
}

await writeFile(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");

console.log(
  JSON.stringify(
    {
      outputPath,
      requestedCount: output.matching.requestedCount,
      matchedCount: output.matching.matchedCount,
      missingItemSequences: output.matching.missingItemSequences,
      sample: output.products.slice(0, 10).map((product) => ({
        itemSequence: product.itemSequence,
        productName: product.officialProductName,
        classification: product.official.classification,
        authorizationStatus: product.official.authorizationStatus,
      })),
    },
    null,
    2,
  ),
);

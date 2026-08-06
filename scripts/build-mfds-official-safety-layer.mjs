import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const repositoryRoot = resolve(import.meta.dirname, "..");
const permitPath = resolve(
  repositoryRoot,
  "src/generated/otc-official-product-info.json",
);
const durPath = resolve(
  repositoryRoot,
  "src/generated/otc-official-dur-info.json",
);
const outputPath = resolve(
  repositoryRoot,
  "src/generated/otc-official-safety-layer.json",
);

const permit = JSON.parse(await readFile(permitPath, "utf8"));
const dur = JSON.parse(await readFile(durPath, "utf8"));
if (
  permit.candidateOnly !== true ||
  permit.clinicalUseProhibited !== true ||
  dur.candidateOnly !== true ||
  dur.clinicalUseProhibited !== true
) {
  throw new Error("Unsafe official data layer input");
}

const permitByItemSequence = new Map(
  permit.products.map((product) => [product.itemSequence, product]),
);
const durByItemSequence = new Map(
  dur.products.map((product) => [product.itemSequence, product]),
);
if (permitByItemSequence.size !== permit.products.length) {
  throw new Error("Duplicate permit itemSequence values");
}
if (durByItemSequence.size !== dur.products.length) {
  throw new Error("Duplicate DUR itemSequence values");
}

const permitSnapshot = permit.source.sourceSnapshot;
const products = permit.products.map((permitProduct) => {
  const durProduct = durByItemSequence.get(permitProduct.itemSequence);
  if (!durProduct) {
    throw new Error(
      `Missing DUR layer product: ${permitProduct.itemSequence}`,
    );
  }

  return {
    itemSequence: permitProduct.itemSequence,
    productId: permitProduct.productId,
    runtimeProductName: permitProduct.runtimeProductName,
    officialProductName: permitProduct.officialProductName,
    permit: {
      queriedAt: permitSnapshot?.fetched_at ?? null,
      layerGeneratedAt: permit.generatedAt,
      dataset: permit.source.dataset,
      rawFields: {
        ITEM_SEQ: permitProduct.itemSequence,
        ITEM_NAME: permitProduct.officialProductName,
        MATERIAL_NAME: permitProduct.official.materialName,
        CHART: permitProduct.official.dosageForm,
        ETC_OTC_CODE: permitProduct.official.classification,
        CANCEL_NAME: permitProduct.official.authorizationStatus,
      },
      fieldMap: permitProduct.source.officialFields,
    },
    dur: {
      queriedAtByDataset: Object.fromEntries(
        Object.entries(dur.sourceDatasets).map(([key, source]) => [
          key,
          source.sourceSnapshots.map((snapshot) => snapshot.fetched_at ?? null),
        ]),
      ),
      records: durProduct.dur,
    },
  };
});

const productWithDurCount = products.filter((product) =>
  Object.values(product.dur.records).some((records) => records.length > 0),
).length;
const attachedRecordCounts = Object.fromEntries(
  Object.entries(dur.matching.overall.typeCounts),
);

const output = {
  schemaVersion: "1.0.0",
  generatedAt: new Date().toISOString(),
  candidateOnly: true,
  clinicalUseProhibited: true,
  joinKey: "itemSequence",
  sourceLayers: {
    permit: {
      path: "src/generated/otc-official-product-info.json",
      generatedAt: permit.generatedAt,
      dataset: permit.source.dataset,
      sourceSnapshot: permitSnapshot,
      candidateOnly: permit.candidateOnly,
      clinicalUseProhibited: permit.clinicalUseProhibited,
    },
    dur: {
      path: "src/generated/otc-official-dur-info.json",
      generatedAt: dur.generatedAt,
      datasets: dur.sourceDatasets,
      candidateOnly: dur.candidateOnly,
      clinicalUseProhibited: dur.clinicalUseProhibited,
    },
  },
  products,
  matching: {
    productCount: products.length,
    productsWithAnyDurCount: productWithDurCount,
    productsWithoutDur: products
      .filter((product) =>
        !Object.values(product.dur.records).some((records) => records.length > 0),
      )
      .map((product) => ({
        itemSequence: product.itemSequence,
        productName: product.runtimeProductName,
      })),
    attachedRecordCounts,
  },
};

await writeFile(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");

console.log(
  JSON.stringify(
    {
      outputPath,
      productCount: output.matching.productCount,
      productsWithAnyDurCount: output.matching.productsWithAnyDurCount,
      productsWithoutDur: output.matching.productsWithoutDur,
      attachedRecordCounts: output.matching.attachedRecordCounts,
      sample: output.products.slice(0, 10).map((product) => ({
        itemSequence: product.itemSequence,
        productName: product.officialProductName,
        permitQueriedAt: product.permit.queriedAt,
        durRecordCount: Object.values(product.dur.records).reduce(
          (count, records) => count + records.length,
          0,
        ),
      })),
    },
    null,
    2,
  ),
);

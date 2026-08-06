import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import {
  readMfdsManifest,
  streamMfdsDataset,
} from "./kr-drug-data-reader.mjs";

const repositoryRoot = resolve(import.meta.dirname, "..");
const inputPath = resolve(
  repositoryRoot,
  "src/generated/otc-official-product-info.json",
);
const outputPath = resolve(
  repositoryRoot,
  "src/generated/otc-official-dur-info.json",
);

const datasets = [
  {
    key: "usjntTaboo",
    dataset: "dur-ingredient:usjnt-taboo",
    type: "병용금기",
  },
  {
    key: "pwnmTaboo",
    dataset: "dur-ingredient:pwnm-taboo",
    type: "임부금기",
  },
  {
    key: "cpctyAtent",
    dataset: "dur-ingredient:cpcty-atent",
    type: "용량주의",
  },
  {
    key: "mdctnPdAtent",
    dataset: "dur-ingredient:mdctn-pd-atent",
    type: "투여기간주의",
  },
  {
    key: "odsnAtent",
    dataset: "dur-ingredient:odsn-atent",
    type: "노인주의",
  },
  {
    key: "spcifyAgrdeTaboo",
    dataset: "dur-ingredient:spcify-agrde-taboo",
    type: "특정연령대금기",
  },
  {
    key: "efcyDplct",
    dataset: "dur-ingredient:efcy-dplct",
    type: "효능군중복",
  },
];

const input = JSON.parse(await readFile(inputPath, "utf8"));
if (
  input.candidateOnly !== true ||
  input.clinicalUseProhibited !== true ||
  !Array.isArray(input.products)
) {
  throw new Error("Unsafe or invalid official product layer");
}

const canonical = (value) =>
  String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("ko-KR")
    .replace(/[∙ㆍ]/g, "·")
    .replace(/\s+/g, "")
    .replace(/\([^()]*\)/g, "")
    .trim();

const nameVariants = (value) => {
  const raw = String(value ?? "").trim();
  const withoutParenthetical = raw.replace(/\([^()]*\)/g, "").trim();
  return new Set(
    [raw, withoutParenthetical]
      .map(canonical)
      .filter(Boolean),
  );
};

const parseMaterialIngredientNames = (materialName) => {
  const names = [
    ...String(materialName ?? "").matchAll(
      /(?:^|[;|])성분명\s*:\s*([^|;]*)/g,
    ),
  ]
    .map((match) => match[1].trim())
    .filter(Boolean);
  const seen = new Set();
  return names.filter((name) => {
    const key = canonical(name);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const parseMixtureComponents = (value) => {
  if (!value) return [];
  return String(value)
    .split("/")
    .map((part) => {
      const raw = part.trim();
      const code = raw.match(/^\[([^\]]+)\]/)?.[1] ?? null;
      const names = [...raw.matchAll(/\(([^()]*)\)/g)];
      const name = names.at(-1)?.[1]?.trim() ?? raw.replace(/^\[[^\]]+\]/, "").trim();
      return { ingredientCode: code, ingredientName: name };
    })
    .filter((component) => component.ingredientName);
};

const rowComponents = (row) => {
  const fields = row.fields ?? {};
  const primaryName = fields.INGR_KOR_NAME ?? fields.INGR_NAME ?? null;
  const primary = primaryName
    ? [
        {
          role: "primary",
          ingredientCode: row.ingredientCode ?? fields.INGR_CODE ?? null,
          ingredientName: String(primaryName).trim(),
        },
      ]
    : [];
  const mixtureName =
    fields.MIXTURE_INGR_KOR_NAME ?? fields.MIX_INGR ?? null;
  const mixtureCode = fields.MIXTURE_INGR_CODE ?? null;
  const mixture = mixtureName
    ? parseMixtureComponents(mixtureName).map((component, index) => ({
        role: "mixture",
        ingredientCode:
          component.ingredientCode ?? (index === 0 ? mixtureCode : null),
        ingredientName: component.ingredientName,
      }))
    : [];
  return [...primary, ...mixture].map((component) => ({
    ...component,
    variants: nameVariants(component.ingredientName),
  }));
};

const productInputs = input.products.map((product) => ({
  product,
  ingredientNames: parseMaterialIngredientNames(
    product.official?.materialName,
  ),
}));

const productOutputs = new Map(
  productInputs.map(({ product, ingredientNames }) => [
    product.itemSequence,
    {
      itemSequence: product.itemSequence,
      productId: product.productId,
      runtimeProductName: product.runtimeProductName,
      ingredientNames,
      dur: Object.fromEntries(datasets.map(({ key }) => [key, []])),
    },
  ]),
);

const sourceDatasets = {};
const matching = {};

for (const definition of datasets) {
  const manifest = await readMfdsManifest(definition.dataset);
  const snapshots = manifest.sourceSnapshot
    ? [manifest.sourceSnapshot]
    : manifest.sourceSnapshots?.map((entry) => entry.sourceSnapshot) ?? [];
  if (
    manifest.candidateOnly !== true ||
    manifest.clinicalUseProhibited !== true ||
    snapshots.length === 0 ||
    snapshots.some((snapshot) => snapshot.status !== "parsed")
  ) {
    throw new Error(`Unsafe or incomplete MFDS manifest: ${definition.dataset}`);
  }
  sourceDatasets[definition.key] = {
    dataset: definition.dataset,
    type: definition.type,
    provider: manifest.provider,
    recordCount: manifest.recordCount,
    candidateOnly: manifest.candidateOnly,
    clinicalUseProhibited: manifest.clinicalUseProhibited,
    activeFilter: { field: "DEL_YN", value: "정상" },
    ingredientMatchRoles:
      definition.key === "usjntTaboo" ? ["primary", "mixture"] : ["primary"],
    sourceSnapshots: snapshots,
  };

  let scannedRecordCount = 0;
  let excludedRecordCount = 0;
  let attachedRecordCount = 0;
  const matchedProducts = new Set();
  for await (const row of streamMfdsDataset(definition.dataset)) {
    scannedRecordCount += 1;
    if (row.fields?.DEL_YN !== "정상") {
      excludedRecordCount += 1;
      continue;
    }
    const components = rowComponents(row);
    for (const { product, ingredientNames } of productInputs) {
      const productVariants = new Map(
        ingredientNames.flatMap((name) =>
          [...nameVariants(name)].map((variant) => [variant, name]),
        ),
      );
      const matchedIngredients = components
        .filter(
          (component) =>
            definition.key === "usjntTaboo" || component.role === "primary",
        )
        .filter((component) =>
          [...component.variants].some((variant) => productVariants.has(variant)),
        )
        .map((component) => ({
          role: component.role,
          ingredientCode: component.ingredientCode,
          durIngredientName: component.ingredientName,
          productIngredientNames: [
            ...new Set(
              [...component.variants]
                .map((variant) => productVariants.get(variant))
                .filter(Boolean),
            ),
          ],
        }));
      if (matchedIngredients.length === 0) continue;

      const output = productOutputs.get(product.itemSequence);
      output.dur[definition.key].push({
        ruleType: definition.type,
        ingredientCode: row.ingredientCode ?? row.fields?.INGR_CODE ?? null,
        matchedIngredients,
        source: {
          provider: row.provider ?? manifest.provider ?? null,
          candidateOnly: row.candidateOnly === true,
          dataset: definition.dataset,
        },
        fields: row.fields ?? {},
      });
      attachedRecordCount += 1;
      matchedProducts.add(product.itemSequence);
    }
  }

  const unmatchedProducts = productInputs
    .filter(({ product }) => !matchedProducts.has(product.itemSequence))
    .map(({ product }) => ({
      itemSequence: product.itemSequence,
      productName: product.runtimeProductName,
    }));
  matching[definition.key] = {
    type: definition.type,
    scannedRecordCount,
    excludedRecordCount,
    activeRecordCount: scannedRecordCount - excludedRecordCount,
    attachedRecordCount,
    matchedProductCount: matchedProducts.size,
    unmatchedProducts,
  };
}

const output = {
  schemaVersion: "1.0.0",
  generatedAt: new Date().toISOString(),
  candidateOnly: true,
  clinicalUseProhibited: true,
  joinKey: "itemSequence",
  sourceDatasets,
  products: [...productOutputs.values()],
  matching,
};
const productsWithAnyDur = output.products.filter((product) =>
  Object.values(product.dur).some((records) => records.length > 0),
);
output.matching.overall = {
  productCount: output.products.length,
  productsWithAnyDurCount: productsWithAnyDur.length,
  productsWithoutDur: productsWithAnyDur.length === output.products.length
    ? []
    : output.products
        .filter((product) => !productsWithAnyDur.includes(product))
        .map((product) => ({
          itemSequence: product.itemSequence,
          productName: product.runtimeProductName,
        })),
  typeCounts: Object.fromEntries(
    datasets.map(({ key, type }) => [
      type,
      output.products.reduce(
        (count, product) => count + product.dur[key].length,
        0,
      ),
    ]),
  ),
};

await writeFile(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");

console.log(
  JSON.stringify(
    {
      outputPath,
      productCount: output.products.length,
      productsWithAnyDurCount: output.matching.overall.productsWithAnyDurCount,
      productsWithoutDur: output.matching.overall.productsWithoutDur,
      matching: Object.fromEntries(
        Object.entries(matching)
          .filter(([key]) => key !== "overall")
          .map(([key, value]) => [key, {
          type: value.type,
          scannedRecordCount: value.scannedRecordCount,
          excludedRecordCount: value.excludedRecordCount,
          activeRecordCount: value.activeRecordCount,
          attachedRecordCount: value.attachedRecordCount,
          matchedProductCount: value.matchedProductCount,
          unmatchedProducts: value.unmatchedProducts.map((product) => product.itemSequence),
          }]),
      ),
      sample: output.products.slice(0, 10).map((product) => ({
        itemSequence: product.itemSequence,
        productName: product.runtimeProductName,
        durCounts: Object.fromEntries(
          Object.entries(product.dur).map(([key, rows]) => [key, rows.length]),
        ),
      })),
    },
    null,
    2,
  ),
);

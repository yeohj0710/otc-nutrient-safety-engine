import { createReadStream } from "node:fs";
import { access, readFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import { resolve } from "node:path";

const root = resolve(
  process.env.KR_DRUG_DATA_DIR ?? "C:\\dev\\kr-drug-data",
);
const paths = {
  permit: "permit/catalog.jsonl",
  "dur-product": "dur-product/catalog.jsonl",
  "dur-ingredient:usjnt-taboo": "dur-ingredient/usjnt-taboo.jsonl",
  "dur-ingredient:pwnm-taboo": "dur-ingredient/pwnm-taboo.jsonl",
  "dur-ingredient:cpcty-atent": "dur-ingredient/cpcty-atent.jsonl",
  "dur-ingredient:mdctn-pd-atent": "dur-ingredient/mdctn-pd-atent.jsonl",
  "dur-ingredient:odsn-atent": "dur-ingredient/odsn-atent.jsonl",
  "dur-ingredient:spcify-agrde-taboo":
    "dur-ingredient/spcify-agrde-taboo.jsonl",
  "dur-ingredient:efcy-dplct": "dur-ingredient/efcy-dplct.jsonl",
};

export function krDrugDataRoot() {
  return root;
}

export async function readMfdsManifest(dataset) {
  const manifestName = dataset.startsWith("dur-ingredient:")
    ? "dur-ingredient"
    : dataset;
  const path = resolve(root, manifestName, "manifest.json");
  await access(path);
  return JSON.parse(await readFile(path, "utf8"));
}

export async function* streamMfdsDataset(dataset) {
  const relative = paths[dataset];
  if (!relative) throw new Error(`Unknown MFDS dataset: ${dataset}`);
  const stream = createReadStream(resolve(root, relative), { encoding: "utf8" });
  const lines = createInterface({ input: stream, crlfDelay: Infinity });
  try {
    for await (const line of lines) {
      if (line.trim()) yield JSON.parse(line);
    }
  } finally {
    lines.close();
    stream.destroy();
  }
}

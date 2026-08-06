import { readMfdsManifest } from "./kr-drug-data-reader.mjs";

const datasets = [
  "permit",
  "dur-product",
  "dur-ingredient:usjnt-taboo",
  "dur-ingredient:pwnm-taboo",
  "dur-ingredient:cpcty-atent",
  "dur-ingredient:mdctn-pd-atent",
  "dur-ingredient:odsn-atent",
  "dur-ingredient:spcify-agrde-taboo",
  "dur-ingredient:efcy-dplct",
];

for (const dataset of datasets) {
  const manifest = await readMfdsManifest(dataset);
  if (
    manifest.candidateOnly !== true ||
    manifest.clinicalUseProhibited !== true
  ) {
    throw new Error(`Unsafe MFDS manifest: ${dataset}`);
  }
  const snapshots = manifest.sourceSnapshot
    ? [manifest.sourceSnapshot]
    : manifest.sourceSnapshots?.map((entry) => entry.sourceSnapshot) ?? [];
  if (
    snapshots.length === 0 ||
    snapshots.some((snapshot) => snapshot.status !== "parsed")
  ) {
    throw new Error(`Incomplete MFDS source snapshot: ${dataset}`);
  }
}

console.log(`verified ${datasets.length} local MFDS manifests`);

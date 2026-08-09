import { existsSync } from "node:fs";
import { readMfdsManifest, krDrugDataRoot } from "./kr-drug-data-reader.mjs";

// 이 검사는 수집물이 있는 기계에서만 뜻이 있다. kr-drug-data 는 로컬에만
// 있고 저장소에 담지 않으므로, Vercel 빌드 서버에는 존재하지 않는다.
// 없는 곳에서 빌드를 세우면 배포가 통째로 막힌다. 화면이 쓰는 것은 이미
// src/generated 에 커밋된 파생 데이터이지 원본이 아니다.
if (!existsSync(krDrugDataRoot())) {
  console.log(
    `kr-drug-data 가 없어 MFDS manifest 검사를 건너뜁니다 (${krDrugDataRoot()}). 커밋된 src/generated 파생 데이터로 빌드합니다.`,
  );
  process.exit(0);
}

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

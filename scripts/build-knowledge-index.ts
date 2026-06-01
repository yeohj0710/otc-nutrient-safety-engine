import path from "node:path";

import { writeKnowledgeIndex } from "@/src/lib/knowledge/normalize";

async function main() {
  const projectRoot = path.resolve(__dirname, "..");
  const knowledgeIndex = await writeKnowledgeIndex(projectRoot);

  console.log(
    `knowledge-index generated: ${knowledgeIndex.meta.safetyRuleCount} rules, ${knowledgeIndex.meta.evidenceChunkCount} evidence chunks (${knowledgeIndex.meta.verifiedAgainstSourceCount} verified, ${knowledgeIndex.meta.supportedInferenceCount} inference, ${knowledgeIndex.meta.pendingManualExtractionCount} pending)`,
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

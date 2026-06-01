import path from "node:path";
import { spawn } from "node:child_process";
import { watch } from "node:fs";

import { writeKnowledgeIndex } from "@/src/lib/knowledge/normalize";

const projectRoot = path.resolve(__dirname, "..");
const watchedRelativePaths = new Set([
  path.join("data", "knowledge_pack.json"),
  path.join("data", "source_registry.json"),
  path.join("data", "ingredients.json"),
  path.join("data", "evidence_chunks.json"),
  path.join("data", "safety_rules.json"),
]);

let pendingTimer: NodeJS.Timeout | null = null;
let rebuildInFlight = false;
let rebuildQueued = false;

async function rebuildKnowledgeIndex(reason: string) {
  if (rebuildInFlight) {
    rebuildQueued = true;
    return;
  }

  rebuildInFlight = true;

  try {
    const knowledgeIndex = await writeKnowledgeIndex(projectRoot);
    console.log(
      `[knowledge-watch] ${reason}: ${knowledgeIndex.meta.safetyRuleCount} rules, ${knowledgeIndex.meta.evidenceChunkCount} evidence chunks`,
    );
  } catch (error) {
    console.error("[knowledge-watch] failed to rebuild knowledge index");
    console.error(error);
  } finally {
    rebuildInFlight = false;

    if (rebuildQueued) {
      rebuildQueued = false;
      void rebuildKnowledgeIndex("queued update");
    }
  }
}

function scheduleRebuild(reason: string) {
  if (pendingTimer) {
    clearTimeout(pendingTimer);
  }

  pendingTimer = setTimeout(() => {
    pendingTimer = null;
    void rebuildKnowledgeIndex(reason);
  }, 150);
}

function startWatchers() {
  const dataDirectoryPath = path.join(projectRoot, "data");

  return [
    watch(dataDirectoryPath, (_eventType, filename) => {
      if (!filename) {
        scheduleRebuild("data directory changed");
        return;
      }

      const relativePath = path.join("data", filename.toString());

      if (!watchedRelativePaths.has(relativePath)) {
        return;
      }

      scheduleRebuild(`${relativePath} changed`);
    }),
  ];
}

async function main() {
  await rebuildKnowledgeIndex("initial build");

  const watchers = startWatchers();
  const nextCliPath = path.join(projectRoot, "node_modules", "next", "dist", "bin", "next");
  const nextArgs = [nextCliPath, "dev", ...process.argv.slice(2)];
  const child = spawn(process.execPath, nextArgs, {
    cwd: projectRoot,
    stdio: "inherit",
    shell: false,
  });

  const shutdown = () => {
    for (const watcher of watchers) {
      watcher.close();
    }

    if (pendingTimer) {
      clearTimeout(pendingTimer);
      pendingTimer = null;
    }

    if (!child.killed) {
      child.kill("SIGINT");
    }
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  child.on("exit", (code, signal) => {
    shutdown();

    if (signal) {
      process.kill(process.pid, signal);
      return;
    }

    process.exit(code ?? 0);
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

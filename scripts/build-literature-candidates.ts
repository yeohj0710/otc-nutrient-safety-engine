import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

type CsvRecord = Record<string, string>;

const outputDate = "260603";
const researchOutputDir =
  process.env.RESEARCH_OUTPUT_DIR ??
  "G:\\내 드라이브\\여형준님\\21 6-1\\전공심화실습(1)\\00_260603_최종연구_공유작업실\\01_생성_산출물";

function parseCsv(input: string): CsvRecord[] {
  const rows: string[][] = [];
  let current = "";
  let row: string[] = [];
  let inQuotes = false;

  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    const next = input[index + 1];

    if (char === '"' && inQuotes && next === '"') {
      current += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(current);
      current = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(current);
      if (row.some((cell) => cell.trim())) {
        rows.push(row);
      }
      row = [];
      current = "";
      continue;
    }

    current += char;
  }

  if (current || row.length > 0) {
    row.push(current);
    if (row.some((cell) => cell.trim())) {
      rows.push(row);
    }
  }

  const [headers = [], ...dataRows] = rows;

  return dataRows.map((dataRow) =>
    Object.fromEntries(
      headers.map((header, index) => [header.trim(), dataRow[index]?.trim() ?? ""]),
    ),
  );
}

function readResearchCsv(studyLabel: string, suffix: string) {
  const filePath = path.join(
    researchOutputDir,
    `${studyLabel}_${suffix}_${outputDate}.csv`,
  );

  return parseCsv(readFileSync(filePath, "utf8"));
}

function toNumber(value: string | undefined) {
  const parsed = Number(value ?? "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function getStoredByStage(rows: CsvRecord[], stage: string, targetId?: string) {
  return rows
    .filter(
      (row) =>
        row.stage === stage && (targetId === undefined || row.target_id === targetId),
    )
    .reduce((sum, row) => sum + toNumber(row.stored_records), 0);
}

function getHitByStage(rows: CsvRecord[], stage: string, targetId?: string) {
  return rows
    .filter(
      (row) =>
        row.stage === stage && (targetId === undefined || row.target_id === targetId),
    )
    .reduce((sum, row) => sum + toNumber(row.hit_count), 0);
}

function detectStudyLabel() {
  return process.cwd().includes("otc-nutrient-safety-engine") ? "권혁찬" : "여형준";
}

function detectStudyId(studyLabel: string) {
  return studyLabel === "권혁찬" ? "kwon_otc_nutrients" : "yeohj_anticoag_renal";
}

function buildDataset() {
  const studyLabel = detectStudyLabel();
  const prismaRows = readResearchCsv(studyLabel, "PRISMA_선별요약");
  const secondaryRows = readResearchCsv(studyLabel, "보조검색요약");
  const priorityRows = readResearchCsv(studyLabel, "우선검토후보");

  const summary = {
    studyId: detectStudyId(studyLabel),
    studyLabel,
    generatedAt: new Date().toISOString(),
    primarySearchRuns: prismaRows.filter((row) => row.stage === "search_run").length,
    latestPubMedHitCount: getHitByStage(prismaRows, "latest_total", "all_latest"),
    latestPubMedStoredRecords: getStoredByStage(
      prismaRows,
      "latest_total",
      "all_latest",
    ),
    cumulativePubMedCandidates: getStoredByStage(
      prismaRows,
      "cumulative_records",
      "all_runs",
    ),
    secondarySearchRuns: secondaryRows.length,
    secondaryHitTotal: secondaryRows.reduce(
      (sum, row) => sum + toNumber(row.hit_count),
      0,
    ),
    secondaryStoredRecords: secondaryRows.reduce(
      (sum, row) => sum + toNumber(row.stored_records),
      0,
    ),
    includeCandidateCount: getStoredByStage(
      prismaRows,
      "screening_decision",
      "include_candidate",
    ),
    manualReviewLowCount: getStoredByStage(
      prismaRows,
      "screening_decision",
      "manual_review_low",
    ),
    likelyExcludeCount: getStoredByStage(
      prismaRows,
      "screening_decision",
      "likely_exclude",
    ),
    duplicateExcludedCount: getStoredByStage(
      prismaRows,
      "screening_decision",
      "exclude_duplicate",
    ),
    highPriorityCount: getStoredByStage(
      prismaRows,
      "priority",
      "manual_review_high",
    ),
    mediumPriorityCount: getStoredByStage(
      prismaRows,
      "priority",
      "manual_review_medium",
    ),
    lowPriorityCount: getStoredByStage(prismaRows, "priority", "manual_review_low"),
    priorityCandidateCount: priorityRows.length,
  };

  const candidates = priorityRows.map((row, index) => ({
    id: `${summary.studyId}-candidate-${String(index + 1).padStart(4, "0")}`,
    pmid: row.pmid || null,
    year: row.year ? toNumber(row.year) : null,
    targetId: row.target_id,
    priority: row.priority,
    suggestedDecision: row.suggested_decision,
    matchedPopulationTerms: row.matched_population_terms
      ? row.matched_population_terms.split(";").map((value) => value.trim()).filter(Boolean)
      : [],
    matchedIngredientTerms: row.matched_ingredient_terms
      ? row.matched_ingredient_terms.split(";").map((value) => value.trim()).filter(Boolean)
      : [],
    matchedOutcomeTerms: row.matched_outcome_terms
      ? row.matched_outcome_terms.split(";").map((value) => value.trim()).filter(Boolean)
      : [],
    matchedStudyTerms: row.matched_study_terms
      ? row.matched_study_terms.split(";").map((value) => value.trim()).filter(Boolean)
      : [],
    reviewRole: row.review_role,
    title: row.title,
    url: row.url,
  }));

  return {
    summary,
    candidates,
  };
}

const outputPath = path.join(
  process.cwd(),
  "src",
  "generated",
  "literature-candidates.json",
);
mkdirSync(path.dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(buildDataset(), null, 2)}\n`, "utf8");
console.log(`wrote ${outputPath}`);

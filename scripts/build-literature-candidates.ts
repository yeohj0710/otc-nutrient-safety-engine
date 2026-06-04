import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

type CsvRecord = Record<string, string>;

const searchDataDir = path.join(process.cwd(), "data", "systematic_search");

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

function readSearchCsv(filename: string) {
  const filePath = path.join(searchDataDir, filename);
  return parseCsv(readFileSync(filePath, "utf8"));
}

function toNumber(value: string | undefined) {
  const parsed = Number(value ?? "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function detectStudyLabel() {
  return process.cwd().includes("otc-nutrient-safety-engine") ? "권혁찬" : "여형준";
}

function detectStudyId(studyLabel: string) {
  return studyLabel === "권혁찬" ? "kwon_otc_nutrients" : "yeohj_anticoag_renal";
}

function buildDataset() {
  const studyLabel = detectStudyLabel();
  const searchRows = readSearchCsv("search_runs.csv");
  const retrievedRows = readSearchCsv("retrieved_records.csv");
  const screeningRows = readSearchCsv("screening_log.csv");
  const secondaryRows = readSearchCsv("secondary_search_runs_20260603.csv");
  const priorityRows = readSearchCsv("screening_priority_20260603.csv").filter(
    (row) =>
      row.suggested_decision !== "likely_exclude" &&
      row.suggested_decision !== "exclude_duplicate",
  );

  const summary = {
    studyId: detectStudyId(studyLabel),
    studyLabel,
    generatedAt: new Date().toISOString(),
    primarySearchRuns: searchRows.length,
    latestPubMedHitCount: searchRows.reduce(
      (sum, row) => sum + toNumber(row.hit_count),
      0,
    ),
    latestPubMedStoredRecords: retrievedRows.length,
    cumulativePubMedCandidates: retrievedRows.length,
    secondarySearchRuns: secondaryRows.length,
    secondaryHitTotal: secondaryRows.reduce(
      (sum, row) => sum + toNumber(row.hit_count),
      0,
    ),
    secondaryStoredRecords: secondaryRows.reduce(
      (sum, row) => sum + toNumber(row.stored_records),
      0,
    ),
    includeCandidateCount: screeningRows.filter(
      (row) => row.suggested_decision === "include_candidate",
    ).length,
    manualReviewLowCount: screeningRows.filter(
      (row) => row.suggested_decision === "manual_review_low",
    ).length,
    likelyExcludeCount: screeningRows.filter(
      (row) => row.suggested_decision === "likely_exclude",
    ).length,
    duplicateExcludedCount: screeningRows.filter(
      (row) => row.suggested_decision === "exclude_duplicate",
    ).length,
    highPriorityCount: priorityRows.filter(
      (row) => row.priority === "manual_review_high",
    ).length,
    mediumPriorityCount: priorityRows.filter(
      (row) => row.priority === "manual_review_medium",
    ).length,
    lowPriorityCount: priorityRows.filter(
      (row) => row.priority === "manual_review_low",
    ).length,
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
    reviewRole:
      row.review_role || "manual review candidate for final evidence mapping",
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

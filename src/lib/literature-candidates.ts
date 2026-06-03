import literatureCandidateJson from "@/src/generated/literature-candidates.json";
import {
  literatureCandidateSchema,
  literatureContextSchema,
  literatureSearchSummarySchema,
  type EngineQuery,
  type LiteratureCandidate,
  type LiteratureContext,
} from "@/src/types/knowledge";
import { z } from "zod";

const rawSummarySchema = literatureSearchSummarySchema.omit({
  visibleRuleCount: true,
});

const literatureCandidateDatasetSchema = z.object({
  summary: rawSummarySchema,
  candidates: z.array(literatureCandidateSchema),
});

const literatureCandidateDataset = literatureCandidateDatasetSchema.parse(
  literatureCandidateJson,
);

const priorityRank: Record<string, number> = {
  manual_review_high: 12,
  manual_review_medium: 7,
  manual_review_low: 3,
};

const decisionRank: Record<string, number> = {
  include_candidate: 8,
  maybe_needs_manual_review: 5,
  manual_review_low: 2,
};
const genericSearchTerms = new Set([
  "vitamin",
  "비타민",
  "supplement",
  "dietary",
  "adult",
  "high",
  "dose",
  "risk",
  "use",
]);

function normalizeForSearch(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function splitTerms(value: string | null | undefined) {
  return normalizeForSearch(value ?? "")
    .split(" ")
    .map((term) => term.trim())
    .filter((term) => term.length >= 2);
}

function uniqueValues(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function collectQueryTerms(query: EngineQuery) {
  const profile = query.profile ?? {};
  const candidateItems = query.candidateItems ?? [];

  const ingredientTerms = uniqueValues(
    candidateItems.flatMap((item) => [
      item.name,
      item.ingredientId ?? "",
      item.form ?? "",
      item.product ?? "",
      ...(item.coingredients ?? []),
    ]),
  );
  const medicationTerms = uniqueValues(profile.medications ?? []);
  const conditionTerms = uniqueValues(profile.conditions ?? []);
  const selectedTerms = uniqueValues(profile.selectedCompounds ?? []);
  const memoTerms = splitTerms(profile.memo ?? "").slice(0, 12);

  return {
    ingredientTerms,
    medicationTerms,
    conditionTerms,
    selectedTerms,
    memoTerms,
  };
}

function candidateSearchText(candidate: LiteratureCandidate) {
  return normalizeForSearch(
    [
      candidate.title,
      candidate.targetId,
      candidate.priority,
      candidate.suggestedDecision,
      ...candidate.matchedPopulationTerms,
      ...candidate.matchedIngredientTerms,
      ...candidate.matchedOutcomeTerms,
      ...candidate.matchedStudyTerms,
    ].join(" "),
  );
}

function scoreTerms(
  searchText: string,
  terms: string[],
  score: number,
  reasonLabel: string,
) {
  let total = 0;
  const matched: string[] = [];

  for (const term of terms) {
    const normalizedPhrase = normalizeForSearch(term);
    const normalizedTerms = splitTerms(term).filter(
      (normalizedTerm) => !genericSearchTerms.has(normalizedTerm),
    );
    const phraseMatched =
      normalizedPhrase.includes(" ") && searchText.includes(normalizedPhrase);
    if (!phraseMatched && normalizedTerms.length === 0) continue;

    const tokenMatched = normalizedTerms.some((normalizedTerm) =>
      searchText.includes(normalizedTerm),
    );

    if (phraseMatched || tokenMatched) {
      total += score;
      matched.push(term);
    }
  }

  return {
    score: total,
    reason: matched.length > 0 ? `${reasonLabel}: ${matched.slice(0, 4).join(", ")}` : null,
  };
}

function scoreCandidate(candidate: LiteratureCandidate, query: EngineQuery) {
  const terms = collectQueryTerms(query);
  const searchText = candidateSearchText(candidate);
  const reasonParts: string[] = [];
  let score =
    (priorityRank[candidate.priority] ?? 0) +
    (decisionRank[candidate.suggestedDecision] ?? 0);

  const scoredGroups = [
    scoreTerms(searchText, terms.ingredientTerms, 18, "입력 성분"),
    scoreTerms(searchText, terms.selectedTerms, 12, "선택 성분"),
    scoreTerms(searchText, terms.medicationTerms, 14, "복용 약물"),
    scoreTerms(searchText, terms.conditionTerms, 10, "질환 정보"),
    scoreTerms(searchText, terms.memoTerms, 3, "메모 단어"),
  ];

  for (const group of scoredGroups) {
    score += group.score;
    if (group.reason) {
      reasonParts.push(group.reason);
    }
  }

  return {
    ...candidate,
    relevanceScore: score,
    relevanceReasons:
      reasonParts.length > 0
        ? reasonParts
        : ["검색어 직접 일치 없음, 우선검토 등급 기준으로 표시"],
  };
}

export function getLiteratureContextForQuery(
  query: EngineQuery,
  visibleRuleCount: number,
): LiteratureContext {
  const scoredCandidates = literatureCandidateDataset.candidates
    .map((candidate) => scoreCandidate(candidate, query))
    .sort((left, right) => {
      if (right.relevanceScore !== left.relevanceScore) {
        return right.relevanceScore - left.relevanceScore;
      }

      const yearDifference = (right.year ?? 0) - (left.year ?? 0);
      if (yearDifference !== 0) return yearDifference;

      return left.title.localeCompare(right.title);
    });
  const relatedCandidates = scoredCandidates.slice(0, 12);

  return literatureContextSchema.parse({
    summary: {
      ...literatureCandidateDataset.summary,
      visibleRuleCount,
    },
    relatedCandidates,
    totalCandidateCount: literatureCandidateDataset.candidates.length,
    shownCandidateCount: relatedCandidates.length,
    matchExplanation:
      relatedCandidates.some((candidate) => candidate.relevanceScore >= 25)
        ? "입력 조건과 직접 겹치는 후보문헌을 먼저 정렬했습니다."
        : "직접 일치가 적어도 우선검토 등급이 높은 후보문헌을 함께 표시했습니다.",
  });
}

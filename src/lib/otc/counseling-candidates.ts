import candidatesData from "@/src/generated/otc-counseling-candidates.json";
import {
  profileScopeApplicability,
  type FindingLiteratureMatch,
  type LiteratureApplicability,
} from "@/src/lib/otc/presentation";
import type { SafetyFinding, SelectedProduct, UserProfile } from "@/src/lib/otc/schema";

/**
 * 추가 선별 후보 문헌.
 *
 * 검토를 마친 문헌(v5.0 채택 10건)이 없는 판정에도 읽을거리를 주려고, 재수집 트랙
 * 선별 통과 문헌 가운데 규칙 유형과 성분이 맞는 논문을 에이전트가 초록을 읽고
 * 골라 둔 것이다(research/counseling/curated-candidates.json →
 * scripts/build-counseling-candidates.py → src/generated/otc-counseling-candidates.json).
 * 인용 문장은 저장한 초록에 글자 그대로 있는지 대조했다.
 *
 * 지위는 검토 문헌과 다르다. 사람 전문가 검토와 규칙 승인을 거치지 않았고,
 * 판정을 바꾸지 못하며, 화면과 상담문에서 항상 "추가 선별 후보"로 표시한다.
 */
export type CounselingCandidate = {
  pmid: string;
  recordId: string;
  title: string;
  journal: string;
  year: string;
  publicationTypes: string;
  url: string;
  ruleTypes: string[];
  backgroundForRuleTypes: string[];
  ingredientIds: string[];
  relatedIngredients: { ingredientId: string; noteKo: string }[];
  relation: "candidate" | "candidate_background";
  priority: number;
  quotes: { quote: string; locator: string }[];
  studyDesignKo: string;
  populationKo: string;
  exposureKo: string;
  outcomeKo: string;
  applicabilityKo: string;
  appliesTo: { profileConditions: string[]; medicationTerms: string[] };
  authorizationAlignment: "consistent" | "conflict";
  authorizationNoteKo: string;
  /** 대조에 쓴 저장 초록의 해시. 초록이 바뀌면 검사가 잡는다. */
  abstractSha256: string;
};

export type CandidateStatus =
  | "scope_match"
  | "missing_information"
  | "population_difference"
  | "background";

export type CandidateMatch = {
  paper: CounselingCandidate;
  status: CandidateStatus;
  applicability: LiteratureApplicability | null;
  /** 성분이 같지 않고 관련 성분(이성질체 등)으로만 이어졌을 때의 설명. */
  ingredientNoteKo: string;
  matchedIngredientIds: string[];
};

type CandidateFile = {
  reviewStatus: string;
  reviewNoteKo: string;
  reviewedAt: string;
  humanExpertReviewed: boolean;
  supportsRuleRelease: boolean;
  changesAuthorizationDecision: boolean;
  entries: CounselingCandidate[];
};

const file = candidatesData as unknown as CandidateFile;

export const counselingCandidateReview = {
  reviewStatus: file.reviewStatus,
  reviewNoteKo: file.reviewNoteKo,
  reviewedAt: file.reviewedAt,
  humanExpertReviewed: file.humanExpertReviewed,
  supportsRuleRelease: file.supportsRuleRelease,
  changesAuthorizationDecision: file.changesAuthorizationDecision,
  count: file.entries.length,
};

export const counselingCandidates: readonly CounselingCandidate[] = file.entries;

export function candidateStatusLabel(status: CandidateStatus): string {
  switch (status) {
    case "scope_match":
      return "추가 선별 후보, 입력 조건과 연구 대상이 겹침";
    case "missing_information":
      return "추가 선별 후보, 입력 정보 부족";
    case "population_difference":
      return "추가 선별 후보, 연구 대상과 차이";
    default:
      return "추가 선별 후보, 배경 자료";
  }
}

const statusRank: Record<CandidateStatus, number> = {
  scope_match: 0,
  missing_information: 1,
  population_difference: 2,
  background: 3,
};

function findingIngredientIds(finding: SafetyFinding, selected: readonly SelectedProduct[]) {
  if (finding.ingredientIds.length) return new Set(finding.ingredientIds);
  const productIds = new Set(finding.productIds);
  return new Set(
    selected
      .filter(({ product }) => productIds.has(product.productId))
      .flatMap(({ product }) => product.ingredients.map((ingredient) => ingredient.ingredientId)),
  );
}

/**
 * 판정 한 건에 붙일 추가 선별 후보. 규칙 유형과 성분이 모두 맞아야 하고,
 * 환자 조건은 대조 결과(겹침, 입력 부족, 대상 차이)를 함께 돌려준다.
 * 허가 복용 조건(administration_constraint) 판정도 같은 규칙 유형으로 찾는다.
 */
export function candidateLiteratureForFinding(
  finding: SafetyFinding,
  selected: readonly SelectedProduct[],
  profile?: UserProfile,
): CandidateMatch[] {
  const ingredientIds = findingIngredientIds(finding, selected);
  const matches: CandidateMatch[] = [];
  for (const paper of counselingCandidates) {
    if (!paper.ruleTypes.includes(finding.ruleType)) continue;
    const matchedIngredientIds = paper.ingredientIds.filter((id) => ingredientIds.has(id));
    const related = paper.relatedIngredients.filter((item) => ingredientIds.has(item.ingredientId));
    if (!matchedIngredientIds.length && !related.length) continue;

    const backgroundOnly =
      paper.relation === "candidate_background" ||
      paper.backgroundForRuleTypes.includes(finding.ruleType) ||
      matchedIngredientIds.length === 0;
    const applicability = profileScopeApplicability(paper.appliesTo, profile);
    const status: CandidateStatus = backgroundOnly
      ? "background"
      : applicability.status === "match"
        ? "scope_match"
        : applicability.status;
    matches.push({
      paper,
      status,
      applicability: applicability.status === "match" ? null : applicability,
      ingredientNoteKo: related.map((item) => item.noteKo).join(" "),
      matchedIngredientIds,
    });
  }
  return matches.sort(
    (left, right) =>
      statusRank[left.status] - statusRank[right.status] ||
      left.paper.priority - right.paper.priority ||
      Number(right.paper.year) - Number(left.paper.year) ||
      left.paper.pmid.localeCompare(right.paper.pmid),
  );
}

export type FindingLiteratureCoverage = {
  status: "direct" | "reviewed_conditional" | "reviewed_background" | "candidate_only" | "none";
  headlineKo: string;
  detailKo: string;
  counts: {
    direct: number;
    missingInformation: number;
    populationDifference: number;
    background: number;
    candidates: number;
  };
};

/**
 * 판정 한 건의 문헌 상태를 한 문장으로. "관련 문헌 없음", "입력 정보 부족",
 * "연구 대상과 차이"를 구분해 화면과 상담문이 같은 말을 쓰게 한다.
 */
export function describeFindingLiterature(
  reviewed: { direct: FindingLiteratureMatch[]; background: FindingLiteratureMatch[] },
  candidates: CandidateMatch[],
  screeningPoolCount = 0,
): FindingLiteratureCoverage {
  const missing = reviewed.background.filter(
    (match) => match.applicability?.status === "missing_information",
  );
  const different = reviewed.background.filter(
    (match) => match.applicability?.status === "population_difference",
  );
  const plainBackground = reviewed.background.length - missing.length - different.length;
  const counts = {
    direct: reviewed.direct.length,
    missingInformation: missing.length,
    populationDifference: different.length,
    background: plainBackground,
    candidates: candidates.length,
  };
  const candidateNote = candidates.length
    ? ` 성분과 주제가 맞는 추가 선별 후보 ${candidates.length}편을 함께 붙였습니다. 후보는 에이전트가 초록을 읽고 고른 것이며 사람 전문가 검토와 규칙 승인은 거치지 않았습니다.`
    : "";

  if (reviewed.direct.length) {
    return {
      status: "direct",
      headlineKo: `검토 문헌 ${reviewed.direct.length}편이 현재 판정과 직접 일치합니다.`,
      detailKo: `연구 대상과 성분 조건이 입력과 맞아 직접 근거로 표시합니다. 판정 자체는 허가원문으로 하며 문헌은 설명용입니다.${candidateNote}`,
      counts,
    };
  }
  if (missing.length || different.length) {
    const parts: string[] = [];
    if (missing.length) {
      const fields = [...new Set(missing.flatMap((match) => match.applicability?.missing ?? []))];
      parts.push(`입력 정보 부족 ${missing.length}편(${fields.join(", ") || "환자 조건"} 미입력)`);
    }
    if (different.length) {
      const fields = [...new Set(different.flatMap((match) => match.applicability?.different ?? []))];
      parts.push(`연구 대상과 차이 ${different.length}편(${fields.join(", ") || "환자 조건"})`);
    }
    return {
      status: "reviewed_conditional",
      headlineKo: `검토 문헌은 있지만 직접 근거로 쓰지 않습니다: ${parts.join(", ")}.`,
      detailKo: `${missing.length ? "빠진 항목을 입력하면 연구 대상과 다시 대조합니다. " : ""}${different.length ? "입력한 조건이 연구 대상과 달라 결과를 개인에게 옮길 수 없고, 비교용 배경 자료로만 보여줍니다. " : ""}${candidateNote}`.trim(),
      counts,
    };
  }
  if (plainBackground) {
    return {
      status: "reviewed_background",
      headlineKo: `검토 문헌 ${plainBackground}편은 같은 규칙의 배경 자료입니다.`,
      detailKo: `현재 제품이나 성분 조건을 직접 검증한 연구가 아니라 주제 배경을 설명합니다.${candidateNote}`,
      counts,
    };
  }
  if (candidates.length) {
    return {
      status: "candidate_only",
      headlineKo: `검증 근거 0편, 성분과 주제가 맞는 추가 선별 후보 ${candidates.length}편을 연결했습니다.`,
      detailKo:
        "후보는 재수집 트랙 선별 통과 문헌 가운데 에이전트가 초록을 읽고 고른 것입니다. 인용 문장이 초록에 있는지는 대조했지만, 사람 전문가 검토와 규칙 승인은 거치지 않았으므로 판정 근거로 쓰지 않습니다.",
      counts,
    };
  }
  return {
    status: "none",
    headlineKo: "검증 근거 0편, 이 판정에 연결한 문헌이 없습니다.",
    detailKo: screeningPoolCount
      ? `선별 통과 문헌 ${screeningPoolCount.toLocaleString("ko-KR")}편은 인용 대조와 내용 검토를 거치지 않아 상담 설명에 쓰지 않습니다. 판정은 식약처 허가원문의 조건으로만 합니다.`
      : "이 성분과 주제에 맞는 검토 문헌과 선별 후보가 없습니다. 판정은 식약처 허가원문의 조건으로만 합니다.",
    counts,
  };
}

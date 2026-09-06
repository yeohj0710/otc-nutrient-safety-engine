import literature from "@/src/generated/otc-supporting-literature.json";
import {
  candidateLiteratureForFinding,
  describeFindingLiterature,
  type CandidateMatch,
  type FindingLiteratureCoverage,
} from "@/src/lib/otc/counseling-candidates";
import {
  buildFindingContext,
  splitSupportingLiteratureForFinding,
  type FindingLiteratureMatch,
  type SupportingLiterature,
} from "@/src/lib/otc/presentation";
import { rulePoolFor } from "@/src/lib/otc/rule-literature-pool";
import type { SafetyEvaluation, SafetyFinding, SelectedProduct, UserProfile } from "@/src/lib/otc/schema";

// 상담문을 쓰는 모델에 넘기는 근거 묶음이다. 판정은 엔진이 끝냈고, 여기서는
// 그 판정마다 (1) 실제 제품·복용량·환자 조건, (2) 허가원문 계산과 출처,
// (3) 문헌을 지위별로 나눠 붙인다. 문헌 지위는 셋이다.
//   reviewed_v50            검토를 마친 문헌(직접 일치 / 입력 정보 부족 / 대상 차이 / 배경)
//   agent_screened_candidate 추가 선별 후보(에이전트가 초록을 읽고 고름, 사람 검토 없음)
// 어느 쪽도 허가 판정을 바꾸지 못하며, 모델은 이 묶음 밖의 사실을 말할 수단이 없다.

export type CounselingPaperStatus =
  | "direct"
  | "missing_information"
  | "population_difference"
  | "background"
  | "candidate_scope_match"
  | "candidate_missing_information"
  | "candidate_population_difference"
  | "candidate_background";

export type CounselingPaper = {
  pmid: string;
  title: string;
  year: string;
  studyDesign: string;
  /** direct = 직접 근거, background = 검토 문헌이지만 직접 근거 아님, candidate = 추가 선별 후보. */
  relation: "direct" | "background" | "candidate";
  reviewStatus: "reviewed_v50" | "agent_screened_candidate";
  status: CounselingPaperStatus;
  statusKo: string;
  quote: string;
  locator: string;
  finding: string;
  population?: string;
  exposure?: string;
  outcome?: string;
  limitation: string;
  authorizationAlignment: "consistent" | "conflict";
  authorizationNote?: string;
  url: string;
};

const MAX_REVIEWED_PAPERS = 3;
const MAX_CANDIDATE_PAPERS = 3;
const MAX_PAPERS_PER_RULE = 4;

function statusLabel(status: CounselingPaperStatus): string {
  switch (status) {
    case "direct":
      return "검토 문헌, 현재 판정과 직접 일치";
    case "missing_information":
      return "검토 문헌, 입력 정보 부족으로 직접 근거 아님";
    case "population_difference":
      return "검토 문헌, 연구 대상과 차이가 있어 직접 근거 아님";
    case "background":
      return "검토 문헌, 같은 규칙의 배경 자료";
    case "candidate_scope_match":
      return "추가 선별 후보, 입력 조건과 연구 대상이 겹침";
    case "candidate_missing_information":
      return "추가 선별 후보, 입력 정보 부족";
    case "candidate_population_difference":
      return "추가 선별 후보, 연구 대상과 차이";
    default:
      return "추가 선별 후보, 배경 자료";
  }
}

function reviewedPaper(match: FindingLiteratureMatch, relation: "direct" | "background"): CounselingPaper {
  const status: CounselingPaperStatus =
    relation === "direct" ? "direct" : (match.applicability?.status as CounselingPaperStatus | undefined) ?? "background";
  return {
    pmid: match.paper.pmid,
    title: match.paper.title,
    year: String(match.paper.publicationYear),
    studyDesign: match.paper.studyDesign,
    relation,
    reviewStatus: "reviewed_v50",
    status,
    statusKo: statusLabel(status),
    quote: match.link.locatorQuoteEn,
    locator: match.link.locator,
    finding: match.link.keyFindingKo,
    limitation: match.link.limitationKo,
    authorizationAlignment: match.link.authorizationAlignment,
    authorizationNote: match.link.authorizationAlignment === "conflict" ? match.link.authorizationNoteKo : undefined,
    url: match.paper.url,
  };
}

function candidatePaper(match: CandidateMatch): CounselingPaper {
  const status: CounselingPaperStatus =
    match.status === "scope_match"
      ? "candidate_scope_match"
      : match.status === "missing_information"
        ? "candidate_missing_information"
        : match.status === "population_difference"
          ? "candidate_population_difference"
          : "candidate_background";
  const limitation = [
    match.paper.applicabilityKo,
    match.applicability?.detailKo ?? "",
    match.ingredientNoteKo,
    "추가 선별 후보입니다. 인용 문장이 저장한 초록에 있는지와 성분·주제를 에이전트가 확인했지만, 사람 전문가 검토와 규칙 승인은 거치지 않았고 허가 판정을 바꾸지 않습니다.",
  ]
    .filter(Boolean)
    .join(" ");
  return {
    pmid: match.paper.pmid,
    title: match.paper.title,
    year: match.paper.year,
    studyDesign: match.paper.studyDesignKo,
    relation: "candidate",
    reviewStatus: "agent_screened_candidate",
    status,
    statusKo: statusLabel(status),
    quote: match.paper.quotes.map((item) => item.quote).join(" "),
    locator: match.paper.quotes.map((item) => item.locator).join(", "),
    finding: match.paper.outcomeKo,
    population: match.paper.populationKo,
    exposure: match.paper.exposureKo,
    outcome: match.paper.outcomeKo,
    limitation,
    authorizationAlignment: match.paper.authorizationAlignment,
    authorizationNote: match.paper.authorizationAlignment === "conflict" ? match.paper.authorizationNoteKo : undefined,
    url: match.paper.url,
  };
}

export type CounselingEvidenceRow = {
  ruleId: string;
  ruleType: string;
  decisionBasis: SafetyFinding["decisionBasis"];
  title: string;
  context: ReturnType<typeof buildFindingContext>;
  calculation: {
    amount?: number;
    reference?: number;
    unit?: string;
    description: string;
    decisionBasis: SafetyFinding["decisionBasis"];
    sources: SafetyFinding["evidence"];
  };
  authorization: { quote: string; url: string; locator: string; product: string }[];
  literature: FindingLiteratureCoverage;
  papers: CounselingPaper[];
};

export function buildCounselingEvidenceRow(
  finding: SafetyFinding,
  selected: SelectedProduct[],
  profile?: UserProfile,
): CounselingEvidenceRow {
  const grouped = splitSupportingLiteratureForFinding(
    finding,
    literature as SupportingLiterature[],
    selected,
    profile,
  );
  const candidates = candidateLiteratureForFinding(finding, selected, profile);
  const coverage = describeFindingLiterature(
    grouped,
    candidates,
    finding.decisionBasis === "released_rule" ? (rulePoolFor(finding.ruleId)?.listed ?? 0) : 0,
  );
  const reviewed = [
    ...grouped.direct.map((match) => reviewedPaper(match, "direct")),
    ...grouped.background.map((match) => reviewedPaper(match, "background")),
  ].slice(0, MAX_REVIEWED_PAPERS);
  const papers = [...reviewed, ...candidates.slice(0, MAX_CANDIDATE_PAPERS).map(candidatePaper)].slice(
    0,
    MAX_PAPERS_PER_RULE,
  );
  return {
    ruleId: finding.ruleId,
    ruleType: finding.ruleType,
    decisionBasis: finding.decisionBasis,
    title: finding.titleKo,
    context: buildFindingContext(finding, selected),
    calculation: {
      amount: finding.calculatedAmount,
      reference: finding.referenceAmount,
      unit: finding.unit,
      description: finding.detailKo,
      decisionBasis: finding.decisionBasis,
      sources: finding.evidence,
    },
    authorization: (finding.ruleEvidence ?? [])
      .filter((source) => selected.some((item) => item.product.itemSequence === source.itemSequence))
      .map((source) => ({
        quote: source.excerptKo,
        url: source.url,
        locator: source.locator,
        product: source.productName,
      })),
    literature: coverage,
    papers,
  };
}

export function buildOtcCounselingContext(
  evaluation: SafetyEvaluation,
  selected: SelectedProduct[],
  profile?: UserProfile,
) {
  return {
    patient: profile ?? null,
    dailyIngredientTotals: evaluation.ingredientDailyTotals,
    productUse: selected.map((item) => ({
      name: item.product.productName,
      doseUnitLabel: item.product.doseUnitLabel,
      ingredients: item.product.ingredients,
      unitsPerDose: item.unitsPerDose,
      dosesPerDay: item.dosesPerDay,
      hoursSincePreviousDose: item.hoursSincePreviousDose,
      continuousDays: item.continuousDays,
    })),
    evidence: evaluation.findings
      .slice(0, 8)
      .map((finding) => buildCounselingEvidenceRow(finding, selected, profile)),
  };
}
export type OtcCounselingContext = ReturnType<typeof buildOtcCounselingContext>;

/** 문헌을 직접 근거처럼 쓴 문장. 검토 문헌의 배경·조건부 지위와 후보 지위를 모두 지킨다. */
const OVERREACH_ON_PATIENT =
  /(?:이\s*환자|입력한\s*환자|입력하신\s*분|국내\s*제품).{0,30}직접.{0,12}(?:검증했|확인했|입증했|증명했)/;
const LIMIT_STATED = /배경|차이|다르|제한|부족|없어|못했|직접.{0,15}(?:없|않|못)|후보/;
const CANDIDATE_STATED = /후보|선별/;
const CANDIDATE_OVERREACH = /(?:검토(?:를)?\s*(?:마친|끝낸|거친)|검증된|승인된)\s*(?:문헌|논문|근거|연구)/;

export function validateOtcDiscussion(
  discussion: { text: string; ruleId: string; pmids: string[] }[],
  context: OtcCounselingContext,
) {
  const errors: string[] = [];
  for (const item of discussion) {
    const row = context.evidence.find((source) => source.ruleId === item.ruleId);
    if (!row) {
      errors.push(`unknown_rule:${item.ruleId}`);
      continue;
    }
    if (item.pmids.some((id) => !row.papers.some((p) => p.pmid === id))) {
      errors.push("unknown_paper");
      continue;
    }
    const references = row.papers.filter((p) => item.pmids.includes(p.pmid));
    const source = JSON.stringify({
      references,
      authorization: row.authorization,
      calculation: row.calculation,
      literature: row.literature,
      patient: context.patient,
      productUse: context.productUse,
      dailyIngredientTotals: context.dailyIngredientTotals,
    });
    if (references.some((p) => p.relation !== "direct")) {
      if (!LIMIT_STATED.test(item.text)) errors.push("missing_background_limit");
      if (OVERREACH_ON_PATIENT.test(item.text)) errors.push("background_overreach");
    }
    if (references.some((p) => p.relation === "candidate")) {
      if (!CANDIDATE_STATED.test(item.text)) errors.push("missing_candidate_status");
      if (CANDIDATE_OVERREACH.test(item.text)) errors.push("candidate_overreach");
    }
    const numbers = (text: string) =>
      new Set((text.match(/\d+(?:[.,]\d+)*/g) ?? []).map((n) => String(Number(n.replace(/,/g, "")))));
    const allowed = numbers(source);
    if ([...numbers(item.text)].some((n) => !allowed.has(n))) errors.push("unsupported_number");
    const quantities = (text: string) =>
      [...text.matchAll(/(\d+(?:\.\d+)?)\s*(mcg|µg|μg|mg|g|mL|ml|IU)(?![a-zA-Z])/g)].map(
        (match) => `${Number(match[1])}|${match[2].replace(/^[µμ]g$/, "mcg").toLowerCase()}`,
      );
    const productQuantities = [
      ...context.productUse.flatMap((product) =>
        product.ingredients.map((ingredient) => `${ingredient.amountPerUnit} ${ingredient.unit}`),
      ),
      ...Object.values(context.dailyIngredientTotals ?? {}).map((total) => `${total.amount} ${total.unit}`),
    ].join("\n");
    const sourceQuantities = new Set(quantities(source + productQuantities));
    if (quantities(item.text).some((quantity) => !sourceQuantities.has(quantity))) errors.push("unsupported_unit");
    if (/안전합니다|괜찮습니다|문제없습니다|복용하세요|드세요|용량을\s*(줄|늘)/.test(item.text)) errors.push("overreach");
    if (item.text.length > 900) errors.push("too_long");
  }
  return errors;
}

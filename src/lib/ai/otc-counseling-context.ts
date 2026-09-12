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
  /** 직접 근거가 아닌 까닭만 따로. 화면 요약은 이 문장을 쓰고, 모델에는 limitation 전문을 준다. */
  reasonKo: string;
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
    reasonKo: match.applicability?.detailKo ?? (relation === "direct" ? "" : match.link.limitationKo),
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
    reasonKo: [match.applicability?.detailKo ?? "", match.paper.applicabilityKo, match.ingredientNoteKo]
      .filter(Boolean)
      .join(" "),
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
  /** 이 판정에 걸린 제품이 하루에 넣는 성분량. related=true 가 이 판정의 성분이다. */
  contributions: {
    product: string;
    ingredientId: string;
    nameKo: string;
    dailyAmount: number;
    unit: string;
    dailyAmountKo: string;
    related: boolean;
  }[];
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
  const productIds = new Set(finding.productIds);
  const ingredientIds = new Set(finding.ingredientIds);
  return {
    ruleId: finding.ruleId,
    ruleType: finding.ruleType,
    decisionBasis: finding.decisionBasis,
    title: finding.titleKo,
    context: buildFindingContext(finding, selected),
    contributions: selected
      .filter((item) => productIds.size === 0 || productIds.has(item.product.productId))
      .flatMap((item) =>
        productDailyContribution(item).map((row) => ({
          product: item.product.productName,
          ingredientId: row.ingredientId,
          nameKo: row.nameKo,
          dailyAmount: row.dailyAmount,
          unit: row.unit,
          dailyAmountKo: row.dailyAmountKo,
          related: ingredientIds.size === 0 || ingredientIds.has(row.ingredientId),
        })),
      ),
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

/** 소수점 뒤 군더더기 0을 지운다. 2.50 mg 은 2.5 mg 으로 적는다. */
function round(value: number) {
  return Number(value.toFixed(4));
}

/**
 * 제품 한 개가 하루에 넣는 성분량.
 *
 * 예전에는 합계(ingredientDailyTotals)와 1회 함량만 넘겼다. 그러면 모델이
 * "타이레놀에서 4,000 mg, 판콜에이에서 900 mg, 합쳐 4,900 mg" 이라고 쓰려면
 * 900 을 자기가 곱해야 했고, 심판은 자료에 없는 숫자라며 설명 전체를 버렸다
 * (프로덕션 unsupported_number:1:900). 사용자가 가장 알고 싶어 하는 값이므로
 * 계산해서 자료로 넘긴다. 심판의 허용 목록도 이 값으로 함께 늘어난다.
 */
function productDailyContribution(item: SelectedProduct) {
  const perDay = item.unitsPerDose * item.dosesPerDay;
  return item.product.ingredients.map((ingredient) => ({
    ingredientId: ingredient.ingredientId,
    nameKo: ingredient.nameKo,
    amountPerUnit: ingredient.amountPerUnit,
    unit: ingredient.unit,
    unitsPerDay: round(perDay),
    /** 이 제품만으로 하루에 들어가는 양. 1회 함량 × 1회 개수 × 하루 횟수. */
    dailyAmount: round(ingredient.amountPerUnit * perDay),
    /** 화면과 상담문이 같은 말을 쓰도록 계산 과정을 문장으로 남긴다. */
    dailyAmountKo: `${ingredient.nameKo} ${round(ingredient.amountPerUnit)} ${ingredient.unit}/${item.product.doseUnitLabel} × 하루 ${round(perDay)}${item.product.doseUnitLabel} = ${round(ingredient.amountPerUnit * perDay)} ${ingredient.unit}`,
  }));
}

/** 판정 한 건을 모델 없이 설명하는 줄. 기다리는 동안과 실패했을 때 같은 것을 쓴다. */
export type OtcGroundingLine = {
  findingId: string;
  ruleId: string;
  title: string;
  text: string;
};

const amountText = (value: number | undefined, unit: string | undefined) =>
  value !== undefined && unit ? `${value}${unit}` : "";

/** 문장 경계에서 자른다. 화면 한 줄이 문단이 되면 아무도 안 읽는다. */
function clip(text: string | undefined, limit: number) {
  const value = (text ?? "").replace(/\s+/g, " ").trim();
  if (value.length <= limit) return value;
  const head = value.slice(0, limit);
  const boundary = head.lastIndexOf(". ");
  const korean = head.lastIndexOf("다. ");
  const cut = Math.max(boundary, korean >= 0 ? korean + 2 : -1);
  return cut > limit * 0.5 ? head.slice(0, cut + 1) : `${head.trim()}…`;
}

/**
 * 판정 하나를 사람이 읽을 수 있는 한 줄로.
 *
 * 예전에는 제품 이름과 성분 함량과 문헌 편수만 적었다. 그래서 요약이 안 붙은
 * 화면에서는 "무슨 근거로 뭐가 걸렸는지"가 아니라 숫자만 남았다. 여기서는
 * 어느 약이 하루에 얼마를 넣는지, 허가 기준이 얼마인지, 붙은 문헌이 무엇을
 * 보고했고 이 입력과 어떻게 다른지를 이어서 적는다. 전부 서버 원자료라
 * 모델을 기다리지 않는다.
 */
export function groundingTextForRow(row: CounselingEvidenceRow): string {
  const parts: string[] = [];
  const related = row.contributions.filter((item) => item.related);
  const products = [...new Set(related.map((item) => item.product))];
  if (related.length && products.length > 1) {
    // 약이 둘 이상이면 어느 약이 얼마를 넣는지 각각 붙인다. 합계만 보면 무엇을 줄일지 모른다.
    parts.push(
      `하루 들어가는 양은 ${related.map((item) => `${item.product} ${item.dailyAmountKo}`).join(", ")}입니다.`,
    );
  } else if (related.length) {
    parts.push(`${products[0]}에서 ${related.map((item) => item.dailyAmountKo).join(", ")}이 들어갑니다.`);
  } else if (row.context.productNames.length) {
    parts.push(`${row.context.productNames.join(", ")}에 걸린 판정입니다.`);
  }
  const amount = amountText(row.calculation.amount, row.calculation.unit);
  const reference = amountText(row.calculation.reference, row.calculation.unit);
  if (amount && reference) parts.push(`계산한 값 ${amount}, 허가 기준 ${reference}입니다.`);
  else if (amount) parts.push(`계산한 값은 ${amount}입니다.`);
  parts.push(row.literature.headlineKo);
  const paper = row.papers[0];
  if (paper) {
    const finding = clip(paper.finding, 180);
    parts.push(
      `가장 가까운 자료는 ${paper.year}년 ${paper.studyDesign}(PMID ${paper.pmid})이고 ${paper.statusKo}입니다.${finding ? ` 보고한 결과: ${finding}` : ""}`,
    );
    const reason = clip(paper.reasonKo, 200);
    if (paper.relation !== "direct" && reason) parts.push(`그대로 적용하지 못하는 까닭: ${reason}`);
  }
  return parts.filter(Boolean).join(" ").replace(/\s{2,}/g, " ").trim();
}

export function buildOtcGroundingLines(rows: readonly CounselingEvidenceRow[], limit = 4): OtcGroundingLine[] {
  return rows.slice(0, limit).map((row) => ({
    findingId: `${row.ruleId}:${row.ruleType}`,
    ruleId: row.ruleId,
    title: row.title,
    text: groundingTextForRow(row),
  }));
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
      // 이 제품 한 개가 하루에 넣는 성분량. 합계와 달리 "어느 약에서 얼마" 를 말할 수 있다.
      dailyContribution: productDailyContribution(item),
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
      ...context.productUse.flatMap((product) => [
        ...product.ingredients.map((ingredient) => `${ingredient.amountPerUnit} ${ingredient.unit}`),
        // 제품 하나가 하루에 넣는 양도 자료다. 문단이 이 값을 쓰면 통과해야 한다.
        ...product.dailyContribution.map((row) => `${row.dailyAmount} ${row.unit}`),
        // 사용자가 적은 복용 단위 그대로. 시럽은 "1회 5 mL" 처럼 단위가 붙는데
        // 이 값이 허용 목록에 없어 정상 문단이 unsupported_unit 으로 떨어졌다
        // (프로덕션 OTC-RULE-008 실측).
        `${product.unitsPerDose} ${product.doseUnitLabel}`,
        `${product.unitsPerDose * product.dosesPerDay} ${product.doseUnitLabel}`,
      ]),
      ...Object.values(context.dailyIngredientTotals ?? {}).map((total) => `${total.amount} ${total.unit}`),
    ].join("\n");
    const sourceQuantities = new Set(quantities(source + productQuantities));
    if (quantities(item.text).some((quantity) => !sourceQuantities.has(quantity))) errors.push("unsupported_unit");
    if (/안전합니다|괜찮습니다|문제없습니다|복용하세요|드세요|용량을\s*(줄|늘)/.test(item.text)) errors.push("overreach");
    if (item.text.length > 900) errors.push("too_long");
  }
  return errors;
}

"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import literatureData from "@/src/generated/otc-supporting-literature.json";
import {
  rulePoolFor,
  rulePoolPapers,
} from "@/src/lib/otc/rule-literature-pool";
import { evaluateOtcSafety } from "@/src/lib/otc/engine";
import type { AiExplainResponse } from "@/src/lib/ai/schema";
import {
  buildFindingContext,
  buildProductSupportSummary,
  formatEvidenceSource,
  groupCoverageGaps,
  groupFindingsForDisplay,
  literaturePlacementLabel,
  literatureRelationLabel,
  productsForTherapeuticClass,
  ruleEvidenceForFinding,
  splitSupportingLiteratureForFinding,
  type FindingLiteratureMatch,
  type ProductSupportSummary,
  type SplitSupportingLiterature,
  type SupportingLiterature,
} from "@/src/lib/otc/presentation";
import {
  createSelectedProductDraft,
  isRequiredDoseDraftEmpty,
  parseSelectedProductDraft,
  selectedProductToDraft,
  type SelectedProductDraft,
} from "@/src/lib/otc/form-state";
import { searchOtcProducts } from "@/src/lib/otc/search";
import type {
  OtcProduct,
  ReleasedRulePolicy,
  RuleEvidenceLink,
  SafetyFinding,
  SelectedProduct,
  UserProfile,
} from "@/src/lib/otc/schema";

import styles from "./otc-product-safety.module.css";

type OfficialCandidate = {
  candidateId: string;
  productName: string;
  className: string;
  status: "authorization_pending" | "withdrawn" | "package_variant_unresolved";
};

type CatalogExistingMatch = {
  itemSequence: string;
  matchStatus: "success" | "conflict";
  officialItemName: string;
  officialManufacturer: string;
  officialDosageForm: string;
  retailDisplayLinks: string;
  sourceUrl: string;
  mfdsPromotionEvidenceComplete: false;
};

export type OtcRuntime = {
  schemaVersion: string;
  generatedAt: string;
  researchDirection: string;
  releaseReady: boolean;
  rulesReleased: number;
  releasedRuleTypes: string[];
  releasedRules?: ReleasedRulePolicy[];
  urgentReferralBindings?: Array<{ itemSequence: string; terms: string[] }>;
  ruleEvidenceByType?: Record<string, RuleEvidenceLink[]>;
  catalogCoverage?: {
    sourceSkuCount: number;
    healthKrConfirmedCount: number;
    healthKrConfirmedUniqueProductCount: number;
    runtimePromotionAllowedCount: number;
    classificationCounts: Record<string, number>;
    existingProductRematch?: {
      total: number;
      success: number;
      conflict: number;
      unlinked: number;
    };
  };
  catalogExistingMatches?: CatalogExistingMatch[];
  products: OtcProduct[];
  officialCandidates: OfficialCandidate[];
};

type BooleanProfileKey =
  | "liverDisease"
  | "kidneyDisease"
  | "giBleedingOrUlcer"
  | "hypertensionOrCardiovascularDisease"
  | "pregnant"
  | "lactating"
  | "willDrive"
  | "alcohol";

const conditionOptions: Array<{
  key: BooleanProfileKey;
  label: string;
  ruleType: string;
}> = [
  { key: "liverDisease", label: "간질환", ruleType: "hepatic_disease" },
  { key: "kidneyDisease", label: "신장질환", ruleType: "renal_disease" },
  {
    key: "giBleedingOrUlcer",
    label: "위장관 출혈·궤양",
    ruleType: "gi_bleeding_ulcer",
  },
  {
    key: "hypertensionOrCardiovascularDisease",
    label: "고혈압·심혈관질환",
    ruleType: "decongestant_hypertension",
  },
  { key: "pregnant", label: "임신 중", ruleType: "pregnancy_lactation" },
  { key: "lactating", label: "수유 중", ruleType: "pregnancy_lactation" },
  { key: "willDrive", label: "사용·복용 후 운전", ruleType: "sedation_driving" },
  { key: "alcohol", label: "매일 3잔 이상 정기 음주", ruleType: "alcohol" },
];

export const quickChecks: Array<{
  kind:
    | "duplicate_ingredient"
    | "duplicate_class"
    | "authorization_limit"
    | "minimum_interval"
    | "condition"
    | "medication"
    | "unsupported";
  label: string;
  description: string;
  productIds: readonly string[];
  profilePatch: Partial<UserProfile>;
  dosePatchByProductId?: Record<string, Partial<SelectedProduct>>;
  expectedRuleType: string | null;
  expectedCoverageGap?: boolean;
}> = [
  {
    kind: "duplicate_ingredient",
    label: "감기약 + 해열제",
    description: "아세트아미노펜 중복 확인",
    productIds: ["MFDS-196800036", "MFDS-202106092"],
    profilePatch: {},
    expectedRuleType: "duplicate_ingredient",
  },
  {
    kind: "duplicate_class",
    label: "소염진통제 2종",
    description: "NSAID 계열 중복 확인",
    productIds: ["MFDS-198601920", "MFDS-197500016"],
    profilePatch: {},
    expectedRuleType: "duplicate_pharmacologic_class",
  },
  {
    kind: "authorization_limit",
    label: "타이레놀 1회 3정",
    description: "허가상 1회 사용 상한 확인",
    productIds: ["MFDS-202106092"],
    profilePatch: { ageYears: 30 },
    dosePatchByProductId: {
      "MFDS-202106092": { unitsPerDose: 3, dosesPerDay: 1 },
    },
    expectedRuleType: "max_daily_dose",
  },
  {
    kind: "minimum_interval",
    label: "타이레놀 2시간 간격",
    description: "허가상 최소 복용 간격 확인",
    productIds: ["MFDS-202106092"],
    profilePatch: { ageYears: 30 },
    dosePatchByProductId: {
      "MFDS-202106092": {
        unitsPerDose: 1,
        dosesPerDay: 1,
        hoursSincePreviousDose: 2,
      },
    },
    expectedRuleType: "minimum_interval",
  },
  {
    kind: "condition",
    label: "어린이부루펜 + 신장질환",
    description: "선택 제품의 질환 주의 확인",
    productIds: ["MFDS-198601920"],
    profilePatch: { kidneyDisease: true, ageYears: 12 },
    expectedRuleType: "renal_disease",
  },
  {
    kind: "medication",
    label: "이부프로펜 + 와파린",
    description: "항응고제 병용 주의 확인",
    productIds: ["MFDS-198601920"],
    profilePatch: { medications: ["와파린"] },
    expectedRuleType: "anticoagulant_antiplatelet",
  },
  {
    kind: "unsupported",
    label: "소화제 2종 · 판정 미지원",
    description: "겹치는 성분을 추가 확인 조건으로 표시",
    productIds: ["MFDS-198700405", "MFDS-200300406"],
    profilePatch: {},
    expectedRuleType: null,
    expectedCoverageGap: true,
  },
];

const initialProfile: UserProfile = { medications: [], redFlagSymptoms: [] };

const catalogClassLabels: Record<string, string> = {
  analgesic_antiinflammatory: "해열·소염진통",
  anthelmintic: "구충제",
  antihistamine: "항히스타민",
  cold_respiratory: "감기·호흡기",
  gastrointestinal: "위장관",
  other_otc: "기타 OTC",
  topical_or_local: "외용·국소",
};

const severityRank = {
  urgent: 4,
  high: 3,
  caution: 2,
  information: 1,
} as const;

export const searchRuntime = (runtime: OtcRuntime, query: string) =>
  searchOtcProducts(runtime.products, runtime.officialCandidates, query);

export function buildSelectedProducts(
  runtime: OtcRuntime,
  productIds: readonly string[],
): SelectedProduct[] {
  const productsById = new Map(
    runtime.products.map((product) => [product.productId, product]),
  );
  const seen = new Set<string>();

  return productIds.flatMap((productId) => {
    const product = productsById.get(productId);
    if (!product || seen.has(productId)) return [];
    seen.add(productId);
    return [{ product, unitsPerDose: 1, dosesPerDay: 1 }];
  });
}

function formatAmount(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function candidateStatus(status: OfficialCandidate["status"]) {
  if (status === "withdrawn") return "현재 허가 취하";
  if (status === "package_variant_unresolved") return "포장 규격 확인 필요";
  return "허가 상세 확인 중";
}

export function buildQuickCheckSelection(
  runtime: OtcRuntime,
  quickCheck: (typeof quickChecks)[number],
): SelectedProduct[] {
  return buildSelectedProducts(runtime, quickCheck.productIds).map((item) => ({
    ...item,
    ...(quickCheck.dosePatchByProductId?.[item.product.productId] ?? {}),
  }));
}

function SupportTooltip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const tooltipId = useId();
  const [open, setOpen] = useState(false);
  const pointerTypeRef = useRef<string | null>(null);

  return (
    <span
      className={styles.supportTooltip}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setOpen(false);
          event.currentTarget.querySelector("button")?.focus();
        }
      }}
    >
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? tooltipId : undefined}
        onPointerDown={(event) => {
          pointerTypeRef.current = event.pointerType;
        }}
        onPointerCancel={() => {
          pointerTypeRef.current = null;
        }}
        onClick={(event) => {
          const pointerType = pointerTypeRef.current;
          if (
            event.detail === 0 ||
            pointerType === "touch" ||
            pointerType === "pen"
          ) {
            setOpen((current) => !current);
          } else {
            setOpen(true);
          }
          pointerTypeRef.current = null;
        }}
        onFocus={() => {
          if (pointerTypeRef.current === null) setOpen(true);
        }}
        onBlur={() => {
          pointerTypeRef.current = null;
          setOpen(false);
        }}
      >
        ?
      </button>
      {open && (
        <span id={tooltipId} className={styles.supportTooltipBubble} role="tooltip">
          {children}
        </span>
      )}
    </span>
  );
}

function authorizationLimitNote(product: OtcProduct): string | null {
  const constraints = product.administrationConstraints ?? [];
  if (constraints.length === 0) return null;
  if (
    constraints.some(
      (constraint) =>
        constraint.derivationMethod === "upper_envelope_from_explicit_regimens",
    )
  ) {
    return "허가 용법에 적힌 여러 사용법 중 가장 큰 값을 비교 상한으로 썼습니다. 개인에게 맞는 권장량이 아닙니다.";
  }
  return "허가사항에 적힌 사용 상한과 비교합니다. 이 값은 개인에게 맞는 권장량이 아닙니다.";
}

function ProductSupportDetails({
  summary,
  product,
  showLimitTooltip = false,
}: {
  summary: ProductSupportSummary;
  product: OtcProduct;
  showLimitTooltip?: boolean;
}) {
  const detailText = summary.detailLabels.join(" · ");
  const limitNote = authorizationLimitNote(product);
  return (
    <span
      className={styles.productSupport}
      data-limited={summary.conditionLabels.length === 0 || undefined}
      aria-label={`${summary.summaryKo}. 지원 점검 유형: ${detailText || "없음"}. 공개 규칙 연결 ${summary.releasedRuleBindingCount}건, 허가 조건 ${summary.administrationConstraintCount}건`}
    >
      <span className={styles.productSupportTitle}>{summary.summaryKo}</span>
      {detailText && (
        <small className={styles.productSupportDetails}>{detailText}</small>
      )}
      {limitNote && (
        <small className={styles.authorizationLimitNote}>
          허가 상한은 개인 권장량이 아닙니다.
          {showLimitTooltip && (
            <SupportTooltip label={`${product.productName} 허가 상한 설명`}>
              {limitNote}
            </SupportTooltip>
          )}
        </small>
      )}
    </span>
  );
}

type InputSupportStatusContext = {
  selectedCount: number;
  supportedCount: number;
  hasCurrentInput: boolean;
  hasCoverageGap: boolean;
  hasInputIssue: boolean;
};

export function inputSupportStatusMessage({
  selectedCount,
  supportedCount,
  hasCurrentInput,
  hasCoverageGap,
  hasInputIssue,
}: InputSupportStatusContext): string {
  if (selectedCount === 0) return "제품을 담으면 지원 여부를 표시합니다.";
  if (!hasCurrentInput) {
    return supportedCount === 0
      ? "입력해도 현재 선택 제품에서는 판정하지 않음"
      : `입력 시 선택 제품 ${selectedCount}개 중 ${supportedCount}개에서 판정`;
  }
  if (hasInputIssue) return "입력값을 확인해야 판정할 수 있음";
  if (hasCoverageGap) {
    return supportedCount === 0
      ? "현재 입력값은 지원 범위 밖 · 추가 확인 조건 참고"
      : `지원 행렬 ${selectedCount}개 중 ${supportedCount}개 · 현재 입력값에 지원 범위 밖 항목 있음`;
  }
  return supportedCount === 0
    ? "현재 입력값은 지원 범위 밖 · 추가 확인 조건 참고"
    : `현재 입력값을 선택 제품 ${selectedCount}개 중 ${supportedCount}개에서 판정`;
}

function InputSupportStatus({
  id,
  selectedCount,
  supportedCount,
  hasCurrentInput,
  hasCoverageGap,
  hasInputIssue,
}: {
  id: string;
} & InputSupportStatusContext) {
  const state =
    selectedCount === 0
      ? "idle"
      : supportedCount === 0 ||
          (hasCurrentInput && (hasCoverageGap || hasInputIssue))
        ? "none"
        : "supported";
  const message = inputSupportStatusMessage({
    selectedCount,
    supportedCount,
    hasCurrentInput,
    hasCoverageGap,
    hasInputIssue,
  });
  // 약을 담기 전에는 항목마다 같은 안내가 반복돼 화면만 채운다. 읽어 줄 화면
  // 낭독기에는 남기고 눈에는 보이지 않게 한다.
  return (
    <small
      id={id}
      className={state === "idle" ? "sr-only" : styles.inputSupportStatus}
      data-state={state}
    >
      {message}
    </small>
  );
}

export function LiteratureCard({
  match,
  scopeLabel,
  kind,
}: {
  match: FindingLiteratureMatch;
  scopeLabel: string;
  kind: "direct" | "background";
}) {
  const { paper, link } = match;
  return (
    <article className={styles.literatureCard}>
      <div>
        <span>
          {paper.publicationYear} · {paper.studyDesign} ·{" "}
          {literatureRelationLabel(link.evidenceRelation)}
        </span>
        <b>PMID {paper.pmid}</b>
        <span
          className={
            kind === "direct" ? styles.v50Verified : styles.v50Unverified
          }
        >
          {literaturePlacementLabel(kind)}
        </span>
        <span className={styles.literatureScopeBadge}>{scopeLabel}</span>
      </div>
      <a href={paper.url} target="_blank" rel="noreferrer">
        {paper.title}
      </a>
      <p>
        <strong>연구 결과</strong>
        {link.keyFindingKo}
      </p>
      <p>
        <strong>v5.1 분류 이유</strong>
        {link.v51Classification.classificationReasonKo}
      </p>
      <p>
        <strong>표시 범위</strong>
        {link.v51Classification.uiBoundaryKo}
      </p>
      <p>
        <strong>적용 한계</strong>
        {link.limitationKo}
      </p>
      <p className={styles.literatureLocator}>
        <strong>인용 위치</strong>
        {link.locator} · <q>{link.locatorQuoteEn}</q>
      </p>
      {link.authorizationAlignment === "conflict" && (
        <p className={styles.literatureConflict}>
          <strong>허가원문과 다른 점</strong>
          {link.authorizationNoteKo}
        </p>
      )}
    </article>
  );
}

export function FindingLiteratureGroup({
  finding,
  matches,
  profile,
  selected,
}: {
  finding: Pick<SafetyFinding, "findingId" | "titleKo" | "ruleId">;
  matches: SplitSupportingLiterature;
  profile?: UserProfile;
  selected?: readonly SelectedProduct[];
}) {
  const { direct, background } = matches;
  return (
    <article className={styles.literatureGroup}>
      <header>
        <h4>{finding.titleKo}</h4>
        <span>
          {direct.length || background.length
            ? `검증 근거 직접 일치 ${direct.length}편 · 배경 ${background.length}편`
            : "검증 근거 0편 — 아래 선별 통과 문헌만 있습니다"}
        </span>
      </header>
      {direct.length > 0 ? (
        <div className={styles.literatureList}>
          {direct.map((match) => (
            <LiteratureCard
              key={`${finding.findingId}:direct:${match.link.linkId}`}
              match={match}
              scopeLabel="현재 판정과 직접 일치"
              kind="direct"
            />
          ))}
        </div>
      ) : (
        <p className={styles.evidenceEmpty}>
          이 규칙에는 문장 인용 대조를 통과한 검증 근거가 없습니다.
        </p>
      )}
      {background.length > 0 && (
        <details className={styles.otherIngredientLiterature}>
          <summary>같은 규칙의 배경 문헌 {background.length}편</summary>
          <p>
            현재 판정의 직접 근거가 아님 · 판정 결과를 바꾸지 않는 참고 자료
          </p>
          <div className={styles.literatureList}>
            {background.map((match) => (
              <LiteratureCard
                key={`${finding.findingId}:background:${match.link.linkId}`}
                match={match}
                scopeLabel="현재 판정의 직접 근거가 아님"
                kind="background"
              />
            ))}
          </div>
        </details>
      )}
      <ScreeningPassedLiterature
        ruleId={finding.ruleId}
        profile={profile}
        selected={selected}
      />
    </article>
  );
}

const POOL_PAGE = 20;

/** `abstract:sentence:7` 을 사람이 읽는 말로. 어느 문장을 인용했는지 밝힌다. */
function locatorText(locator: string) {
  if (!locator) return null;
  if (locator === "TITLE") return "제목에서 인용";
  const match = /^abstract:sentence:(\d+)$/.exec(locator);
  return match ? `초록 ${match[1]}번째 문장` : locator;
}

/**
 * 선별 통과 문헌. 위의 검증 근거와 지위가 다르다는 사실을 화면이 직접 말한다.
 * 인용 대조를 거치지 않았고 규칙을 배포시키지 못한다.
 */
function ScreeningPassedLiterature({
  ruleId,
  profile,
  selected,
}: {
  ruleId: string;
  profile?: UserProfile;
  selected?: readonly SelectedProduct[];
}) {
  const [shown, setShown] = useState(POOL_PAGE);
  const rule = rulePoolFor(ruleId);
  const papers = useMemo(
    () => (rule ? rulePoolPapers(ruleId, 0, shown, { profile, selected }) : []),
    [rule, ruleId, shown, profile, selected],
  );
  if (!rule || rule.listed === 0) return null;

  return (
    <details className={styles.otherIngredientLiterature}>
      <summary>선별 통과 문헌 {rule.listed.toLocaleString("ko-KR")}편</summary>
      <p>
        이 규칙이 허용한 질문에서 v5.0 선별이 retain 으로 판정하고, 규칙 유형의 위해 표현이
        제목·초록에 나타난 문헌입니다. 위의 검증 근거와 달리{" "}
        <strong>문장 인용 대조를 거치지 않았고</strong> 판정 결과를 바꾸지 않습니다.
        {" "}인용문은 초록에서 규칙 유형과 가장 가까운 문장을 결정적으로 고른 것이고,
        번역하지 않은 영어 원문입니다.
        {rule.truncated > 0
          ? ` 조건에 맞는 문헌은 ${rule.rule_type_matched_total.toLocaleString("ko-KR")}편이고 그중 ${rule.listed.toLocaleString("ko-KR")}편을 싣습니다.`
          : ""}
      </p>
      <ul>
        {papers.map((paper) => (
          <li key={paper.record_id}>
            {paper.url ? (
              <a href={paper.url} target="_blank" rel="noreferrer">
                {paper.title || paper.record_id}
              </a>
            ) : (
              (paper.title || paper.record_id)
            )}
            {paper.quote ? (
              <blockquote lang="en" className={styles.poolQuote}>
                {paper.quote}
              </blockquote>
            ) : null}
            <small>
              {[
                paper.journal,
                paper.year,
                locatorText(paper.locator),
                paper.has_abstract ? null : "초록 없음",
              ]
                .filter(Boolean)
                .join(" · ")}
            </small>
          </li>
        ))}
      </ul>
      {shown < rule.listed ? (
        <button
          type="button"
          onClick={() => setShown((value) => value + POOL_PAGE)}
          className={styles.poolMoreButton}
        >
          {Math.min(POOL_PAGE, rule.listed - shown)}편 더 보기
        </button>
      ) : null}
    </details>
  );
}

export function OtcProductSafetyClient({ runtime }: { runtime: OtcRuntime }) {
  const [query, setQuery] = useState("");
  const [selectedDrafts, setSelectedDrafts] = useState<SelectedProductDraft[]>([]);
  const [profile, setProfile] = useState<UserProfile>(initialProfile);
  const [medicationText, setMedicationText] = useState("");
  const [symptomText, setSymptomText] = useState("");
  const [activeTherapeuticClass, setActiveTherapeuticClass] = useState("전체");
  const [activeQuickCheck, setActiveQuickCheck] = useState("");
  const [openFindingIds, setOpenFindingIds] = useState<Record<string, boolean>>({});

  const selected = useMemo(
    () => selectedDrafts.map(parseSelectedProductDraft),
    [selectedDrafts],
  );

  const results = useMemo(() => searchRuntime(runtime, query), [runtime, query]);
  const releasedRuleTypes = useMemo(
    () => new Set(runtime.releasedRuleTypes),
    [runtime.releasedRuleTypes],
  );
  const productSupportById = useMemo(
    () =>
      new Map(
        runtime.products.map((product) => [
          product.productId,
          buildProductSupportSummary(product, releasedRuleTypes),
        ]),
      ),
    [releasedRuleTypes, runtime.products],
  );
  const releasedRuleEvidenceById = useMemo(
    () =>
      new Map(
        (runtime.releasedRules ?? []).map((rule) => [rule.ruleId, rule.evidence]),
      ),
    [runtime.releasedRules],
  );
  const evaluation = useMemo(
    () =>
      runtime.rulesReleased > 0 && selected.length
        ? evaluateOtcSafety(
            selected,
            profile,
            { releasedRules: runtime.releasedRules ?? [] },
          )
        : null,
    [
      profile,
      runtime.releasedRules,
      runtime.rulesReleased,
      selected,
    ],
  );
  // 문장으로 약 찾기. 제품명을 모르는 사람이 상황을 그대로 적으면 지금 검색은
  // 아무것도 못 찾는다. 모델은 성분명만 고르고, 그 성분으로 제품을 찾는 것은
  // 지금까지와 같은 결정론 검색이다. 고른 성분은 화면에 그대로 보여 준다.
  const [phrase, setPhrase] = useState("");
  const [phrasePending, setPhrasePending] = useState(false);
  const [phraseTerms, setPhraseTerms] = useState<string[]>([]);
  const [phraseNote, setPhraseNote] = useState("");

  const ingredientVocabulary = useMemo(() => {
    const names = new Set<string>();
    for (const product of runtime.products) {
      for (const ingredient of product.ingredients) names.add(ingredient.nameKo);
    }
    return [...names];
  }, [runtime.products]);

  async function resolvePhrase() {
    const text = phrase.trim();
    if (!text || phrasePending) return;
    setPhrasePending(true);
    setPhraseTerms([]);
    setPhraseNote("");
    try {
      const res = await fetch("/api/otc-search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, ingredients: ingredientVocabulary }),
      });
      const body = (await res.json()) as {
        ok?: boolean;
        ingredients?: string[];
        note?: string;
        reason?: string;
      };
      if (body?.ok && body.ingredients?.length) {
        setPhraseTerms(body.ingredients);
        setPhraseNote(body.note ?? "");
        setQuery(body.ingredients[0]);
      } else {
        setPhraseNote(
          body?.reason === "no_match"
            ? "이 말과 이어지는 성분을 못 찾았어요. 제품명으로 찾아보세요."
            : "지금은 문장으로 찾기를 쓸 수 없어요. 아래에서 제품명으로 찾아보세요.",
        );
      }
    } catch {
      setPhraseNote("문장을 정리하지 못했어요. 아래에서 제품명으로 찾아보세요.");
    } finally {
      setPhrasePending(false);
    }
  }

  // 한 번에 한 단계만 펼친다. 셋을 동시에 펼쳐 두면 어디부터 봐야 하는지가
  // 화면에 안 드러난다. 끝난 단계는 한 줄 요약으로 접고 눌러서 다시 연다.
  const [openStep, setOpenStep] = useState<1 | 2>(1);
  const hasSelection = selected.length > 0;
  useEffect(() => {
    // 약을 처음 담으면 다음 단계로 넘긴다. 되돌리는 것은 사용자가 직접 한다.
    if (hasSelection) void Promise.resolve().then(() => setOpenStep(2));
  }, [hasSelection]);

  // 판정이 끝난 뒤에만 보조 설명을 부른다. 모델은 엔진이 이미 확정한 findings 만
  // 읽으므로 어떤 규칙이 걸렸는지는 이 호출로 바뀌지 않는다. 심판에 걸리거나
  // 키가 없으면 서버가 ok:false 를 주고 화면은 엔진 결과만 그대로 보여준다.
  const [aiExplain, setAiExplain] = useState<AiExplainResponse | null>(null);
  const [aiExplainPending, setAiExplainPending] = useState(false);

  useEffect(() => {
    if (!evaluation || evaluation.findings.length === 0) {
      void Promise.resolve().then(() => setAiExplain(null));
      return;
    }
    const controller = new AbortController();
    // 효과 본문에서 동기로 setState 하면 렌더가 연쇄된다. 요청 시작과 함께
    // 마이크로태스크로 미룬다(동작은 같다).
    void Promise.resolve().then(() => {
      if (controller.signal.aborted) return;
      setAiExplainPending(true);
      setAiExplain(null);
    });
    fetch("/api/otc-explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        evaluation,
        productNames: selected.map((item) => item.product.productName),
        profileSummary: [
          profile.ageYears ? `${profile.ageYears}세` : "",
          profile.pregnant ? "임신 중" : "",
          profile.medications?.length ? `병용약 ${profile.medications.join(", ")}` : "",
        ]
          .filter(Boolean)
          .join(" · ") || "프로필 정보 없음",
      }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((body: AiExplainResponse | null) => {
        if (!controller.signal.aborted) setAiExplain(body);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!controller.signal.aborted) setAiExplainPending(false);
      });
    return () => controller.abort();
  }, [evaluation, profile, selected]);

  const ingredientNames = useMemo(
    () =>
      new Map(
        runtime.products.flatMap((product) =>
          product.ingredients.map((ingredient) => [
            ingredient.ingredientId,
            ingredient.nameKo,
          ] as const),
        ),
      ),
    [runtime.products],
  );
  const orderedFindings = useMemo(
    () =>
      groupFindingsForDisplay(
        evaluation?.findings ?? [],
        ingredientNames,
      ).sort(
        (left, right) => severityRank[right.severity] - severityRank[left.severity],
      ),
    [evaluation, ingredientNames],
  );
  const productNamesById = useMemo(
    () => new Map(runtime.products.map((product) => [product.productId, product.productName])),
    [runtime.products],
  );
  const catalogMatchesByItemSequence = useMemo(
    () =>
      new Map(
        (runtime.catalogExistingMatches ?? []).map((match) => [
          match.itemSequence,
          match,
        ]),
      ),
    [runtime.catalogExistingMatches],
  );
  const groupedCoverageGaps = useMemo(
    () => groupCoverageGaps(evaluation?.coverageGaps ?? [], productNamesById),
    [evaluation?.coverageGaps, productNamesById],
  );
  const therapeuticClasses = useMemo(
    () => [
      "전체",
      ...new Set(
        runtime.products
          .map((product) => product.therapeuticClass)
          .filter((value): value is NonNullable<typeof value> => Boolean(value)),
      ),
    ],
    [runtime.products],
  );
  const shelfProducts = useMemo(
    () => productsForTherapeuticClass(runtime.products, activeTherapeuticClass),
    [activeTherapeuticClass, runtime.products],
  );
  const literatureByFinding = useMemo(
    () =>
      new Map(
        orderedFindings.map((finding) => [
          finding.findingId,
          splitSupportingLiteratureForFinding(
            finding,
            literatureData as SupportingLiterature[],
            selected,
            profile,
          ),
        ]),
      ),
    [orderedFindings, profile, selected],
  );
  const ruleEvidenceByFinding = useMemo(
    () =>
      new Map(
        orderedFindings.map((finding) => {
          const runtimeEvidence =
            finding.decisionBasis === "released_rule"
              ? releasedRuleEvidenceById.get(finding.ruleId) ?? []
              : [];
          return [
            finding.findingId,
            ruleEvidenceForFinding(finding, selected, [
              ...(finding.ruleEvidence ?? []),
              ...runtimeEvidence,
            ]),
          ];
        }),
      ),
    [orderedFindings, releasedRuleEvidenceById, selected],
  );
  const findingsWithAllDirectRuleEvidence = [
    ...ruleEvidenceByFinding.values(),
  ].filter((display) => display.productMatch === "all").length;
  const findingsWithPartialDirectRuleEvidence = [
    ...ruleEvidenceByFinding.values(),
  ].filter((display) => display.productMatch === "partial").length;
  const findingsWithRepresentativeRuleEvidence = [
    ...ruleEvidenceByFinding.values(),
  ].filter((display) => display.direct.length === 0 && display.representative.length > 0)
    .length;
  const findingsWithDirectLiterature = [...literatureByFinding.values()].filter(
    (matches) => matches.direct.length > 0,
  ).length;
  const findingsWithBackgroundLiterature = [...literatureByFinding.values()].filter(
    (matches) => matches.background.length > 0,
  ).length;
  const hasDirectLiterature = [...literatureByFinding.values()].some(
    (matches) => matches.direct.length > 0,
  );
  const hasBackgroundLiterature = [...literatureByFinding.values()].some(
    (matches) => matches.background.length > 0,
  );
  // 검증 근거가 없는 판정에도 선별 통과 문헌은 있다. 그 층까지 세지 않으면
  // 미연결 규칙에서 이 절이 통째로 사라져, 읽을거리를 주려던 목적과 반대가 된다.
  // 판정마다 따로 부른다. 한 번에 다 넘기면 개별 판정의 요지가 뭉개져서
  // "여러 제품의 용량 또는 투여 방식" 같은 문장이 나온다. 건별로 부르면 그
  // 판정이 왜 걸렸는지만 말한다. 실패하거나 심판에 걸린 건은 그냥 안 보인다.
  const [findingLines, setFindingLines] = useState<Record<string, string>>({});
  const findingKey = orderedFindings.map((f) => f.findingId).join("|");
  useEffect(() => {
    if (!orderedFindings.length) {
      void Promise.resolve().then(() => setFindingLines({}));
      return;
    }
    const controller = new AbortController();
    const names = selected.map((item) => item.product.productName);
    void Promise.resolve().then(() => setFindingLines({}));
    Promise.all(
      orderedFindings.slice(0, 8).map(async (finding) => {
        try {
          const res = await fetch("/api/otc-finding", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: controller.signal,
            body: JSON.stringify({
              ruleType: finding.ruleType,
              titleKo: finding.titleKo,
              detailKo: finding.detailKo,
              nextActionKo: finding.nextActionKo,
              amount:
                finding.calculatedAmount !== undefined && finding.unit
                  ? `${finding.calculatedAmount}${finding.unit}`
                  : "",
              reference:
                finding.referenceAmount !== undefined && finding.unit
                  ? `${finding.referenceAmount}${finding.unit}`
                  : "",
              productNames: names,
            }),
          });
          const body = (await res.json()) as { ok?: boolean; line?: string };
          if (body?.ok && body.line) return [finding.findingId, body.line] as const;
        } catch {
          // 개별 실패는 그 카드만 설명 없이 둔다.
        }
        return null;
      }),
    ).then((pairs) => {
      if (controller.signal.aborted) return;
      setFindingLines(Object.fromEntries(pairs.filter(Boolean) as (readonly [string, string])[]));
    });
    return () => controller.abort();
    // findingKey 로 같은 판정 묶음에는 다시 부르지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findingKey]);

  const hasScreeningPassedLiterature = orderedFindings.some(
    (finding) => (rulePoolFor(finding.ruleId)?.listed ?? 0) > 0,
  );
  const hasFinalLiterature =
    hasDirectLiterature || hasBackgroundLiterature || hasScreeningPassedLiterature;
  const hasRepresentativeRuleEvidence = [...ruleEvidenceByFinding.values()].some(
    (display) => display.representative.length > 0,
  );

  const selectedIds = new Set(selected.map((item) => item.product.productId));
  const selectedReleasedRuleBindingCount = selected.reduce(
    (sum, item) =>
      sum +
      (productSupportById.get(item.product.productId)
        ?.releasedRuleBindingCount ?? 0),
    0,
  );
  const selectedAdministrationConstraintCount = selected.reduce(
    (sum, item) =>
      sum +
      (productSupportById.get(item.product.productId)
        ?.administrationConstraintCount ?? 0),
    0,
  );
  const selectedSupportCount = (ruleTypes: readonly string[]) =>
    selected.filter((item) => {
      const activeCheckTypes = new Set(
        productSupportById.get(item.product.productId)?.activeCheckTypes ?? [],
      );
      return ruleTypes.some((ruleType) => activeCheckTypes.has(ruleType));
    }).length;
  const hasCoverageGapFor = (ruleTypes: readonly string[]) =>
    evaluation?.coverageGaps.some((gap) => ruleTypes.includes(gap.ruleType)) ??
    false;
  const hasInputIssueFor = (fields: readonly string[]) =>
    evaluation?.inputIssues.some((issue) => fields.includes(issue.field)) ?? false;
  const ageSupportCount = selectedSupportCount(["age_restriction"]);
  const medicationSupportCount = selectedSupportCount([
    "anticoagulant_antiplatelet",
    "sedative_medication",
  ]);
  const symptomSupportCount = selectedSupportCount(["urgent_referral"]);
  const activeConditionCount =
    conditionOptions.filter(({ key }) => profile[key]).length +
    Number(profile.ageYears !== undefined) +
    Number(profile.medications.length > 0) +
    Number(profile.redFlagSymptoms.length > 0);
  const urgentCount = orderedFindings.filter((finding) => finding.severity === "urgent").length;

  const pendingDoseDrafts = selectedDrafts.filter(isRequiredDoseDraftEmpty);
  const emptyRequiredDoseFields = new Set(
    selectedDrafts.flatMap((draft) => [
      ...(draft.unitsPerDose.trim() === ""
        ? [`${draft.product.productId}:unitsPerDose`]
        : []),
      ...(draft.dosesPerDay.trim() === ""
        ? [`${draft.product.productId}:dosesPerDay`]
        : []),
    ]),
  );
  const visibleInputIssues =
    evaluation?.inputIssues.filter(
      (issue) =>
        !issue.productId ||
        !emptyRequiredDoseFields.has(`${issue.productId}:${issue.field}`),
    ) ?? [];
  const showClearResult =
    pendingDoseDrafts.length === 0 &&
    orderedFindings.length === 0 &&
    visibleInputIssues.length === 0;
  const showResultSummary =
    orderedFindings.length > 0 || visibleInputIssues.length > 0;

  const quickCheckSummaries = useMemo(
    () =>
      new Map(
        quickChecks.map((quickCheck) => {
          const demoSelected = buildQuickCheckSelection(runtime, quickCheck);
          const demoProfile = {
            ...initialProfile,
            ...quickCheck.profilePatch,
          };
          const demoEvaluation = evaluateOtcSafety(
            demoSelected,
            demoProfile,
            { releasedRules: runtime.releasedRules ?? [] },
          );
          const demoFindings = groupFindingsForDisplay(
            demoEvaluation.findings,
            ingredientNames,
          );
          const directPmids = new Set(
            demoFindings.flatMap((finding) =>
              splitSupportingLiteratureForFinding(
                finding,
                literatureData as SupportingLiterature[],
                demoSelected,
                demoProfile,
              ).direct.map(({ paper }) => paper.pmid),
            ),
          );
          const authorizationDisplays = demoFindings.map((finding) => {
            const runtimeEvidence =
              finding.decisionBasis === "released_rule"
                ? releasedRuleEvidenceById.get(finding.ruleId) ?? []
                : [];
            return ruleEvidenceForFinding(finding, demoSelected, [
              ...(finding.ruleEvidence ?? []),
              ...runtimeEvidence,
            ]);
          });
          return [
            quickCheck.label,
            {
              findingCount: demoFindings.length,
              coverageGapCount: demoEvaluation.coverageGaps.length,
              directPaperCount: directPmids.size,
              directAuthorizationSourceCount: authorizationDisplays.reduce(
                (count, display) => count + display.direct.length,
                0,
              ),
              fullAuthorizationMatchCount: authorizationDisplays.filter(
                (display) => display.productMatch === "all",
              ).length,
              partialAuthorizationMatchCount: authorizationDisplays.filter(
                (display) => display.productMatch === "partial",
              ).length,
            },
          ] as const;
        }),
      ),
    [ingredientNames, releasedRuleEvidenceById, runtime],
  );

  const clearActiveDemo = () => setActiveQuickCheck("");

  const addProduct = (product: OtcProduct) => {
    if (selectedIds.has(product.productId)) return;
    clearActiveDemo();
    setSelectedDrafts((items) => [...items, createSelectedProductDraft(product)]);
    setQuery("");
  };

  const updateSelectedDraft = (
    index: number,
    patch: Partial<Omit<SelectedProductDraft, "product">>,
  ) => {
    clearActiveDemo();
    setSelectedDrafts((items) =>
      items.map((item, currentIndex) =>
        currentIndex === index ? { ...item, ...patch } : item,
      ),
    );
  };

  const applyQuickCheck = (quickCheck: (typeof quickChecks)[number]) => {
    const nextProfile = { ...initialProfile, ...quickCheck.profilePatch };
    setSelectedDrafts(
      buildQuickCheckSelection(runtime, quickCheck).map(selectedProductToDraft),
    );
    setProfile(nextProfile);
    setMedicationText(nextProfile.medications.join(", "));
    setSymptomText(nextProfile.redFlagSymptoms.join(", "));
    setQuery("");
    setActiveQuickCheck(quickCheck.label);
    // 예시를 눌러도 결과가 화면 밖에 그려지면 아무 일도 안 일어난 것처럼 보인다.
    // 판정이 다시 계산된 다음 프레임에 결과로 데려간다.
    // 넓은 화면에서는 결과 패널이 이미 옆에 붙어 있으므로, 안 보일 때만 움직인다.
    requestAnimationFrame(() => {
      const target = document.getElementById("safety-result");
      if (!target) return;
      const box = target.getBoundingClientRect();
      const visible =
        box.top >= 0 && box.top < window.innerHeight * 0.6 && box.bottom > 0;
      if (visible) return;
      const reduceMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      target.scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "start",
      });
    });
  };

  const resetAll = () => {
    setQuery("");
    setSelectedDrafts([]);
    setProfile(initialProfile);
    setMedicationText("");
    setSymptomText("");
    setActiveQuickCheck("");
    setActiveTherapeuticClass("전체");
    setOpenFindingIds({});
  };

  return (
    <div className={styles.workspace}>
      <section className={styles.quickStart} aria-labelledby="quick-start-heading">
        <div className={styles.quickStartCopy}>
          <span className={styles.liveDot} aria-hidden="true" />
          <div>
            <h2 id="quick-start-heading">바로 점검해보기</h2>
            <p>대표 조합을 불러온 뒤 내 복용량에 맞게 바꿀 수 있습니다.</p>
          </div>
        </div>
        <div className={styles.quickCheckList}>
          {quickChecks.map((quickCheck) => {
            const active = activeQuickCheck === quickCheck.label;
            const summary = quickCheckSummaries.get(quickCheck.label);
            return (
              <button
                key={quickCheck.label}
                type="button"
                className={styles.quickCheckButton}
                data-active={active || undefined}
                aria-pressed={active}
                onClick={() => applyQuickCheck(quickCheck)}
                aria-label={`${quickCheck.label}: ${quickCheck.description}`}
              >
                <span>
                  {quickCheck.label}
                  <em>{quickCheck.description}</em>
                  {summary && (
                    <small>
                      주의 {summary.findingCount}개 · 허가 원문{" "}
                      {summary.directAuthorizationSourceCount}건
                    </small>
                  )}
                </span>
                <b aria-hidden="true">→</b>
              </button>
            );
          })}
        </div>
      </section>

      <div className={styles.workspaceGrid}>
        <div className={styles.inputColumn}>
        <section
          className={styles.panel}
          data-collapsed={openStep !== 1 && hasSelection ? "true" : "false"}
          aria-labelledby="medicine-heading"
        >
          <header className={styles.panelHeader}>
            <span className={styles.panelIndex}>1</span>
            <div>
              <h2 id="medicine-heading">사용 중인 약 담기</h2>
              <p>제품명만 찾으면 성분과 함량을 자동으로 불러와요.</p>
            </div>
            <span className={styles.countBadge}>{selected.length}개</span>
            {hasSelection && (
              <button
                type="button"
                className={styles.stepToggle}
                aria-expanded={openStep === 1}
                onClick={() => setOpenStep(openStep === 1 ? 2 : 1)}
              >
                {openStep === 1 ? "접기" : "바꾸기"}
              </button>
            )}
          </header>
          {openStep !== 1 && hasSelection && (
            <p className={styles.stepSummary}>
              {selected.map((item) => item.product.productName).join(" · ")}
            </p>
          )}

          <div className={styles.searchArea}>
            {runtime.catalogCoverage && (
              // 카탈로그 규모·연결 현황은 연구 방법 설명이지 약을 담는 데 필요한
              // 정보가 아니다. 본문에 펼쳐 두면 1단계가 안내문부터 시작한다.
              <details className={styles.catalogScope}>
                <summary className={styles.catalogScopeSummary}>
                  점검 가능한 제품 {runtime.products.length}개 · 자료 범위 보기
                </summary>
                <p className={styles.catalogSummary}>
                  판매 SKU {runtime.catalogCoverage.sourceSkuCount}건 중 {runtime.catalogCoverage.healthKrConfirmedCount}건이 약학정보원 공식 품목 {runtime.catalogCoverage.healthKrConfirmedUniqueProductCount}개와 연결됐고, <strong>현재 {runtime.products.length}개 제품을 점검할 수 있어요.</strong>
                </p>
                <p className={styles.catalogDescription}>
                  약학정보원 연결 제품은 연구 후보입니다. 식약처 허가 원문이 확인되고 공개 안전성 규칙 또는 제품별 허가 사용·복용 조건이 연결된 제품만 점검에 사용해요.
                </p>
                {runtime.catalogCoverage.existingProductRematch && (
                  <p className={styles.catalogRematchSummary}>
                    기존 연구 제품 대조: {runtime.catalogCoverage.existingProductRematch.success}개 연결 · {runtime.catalogCoverage.existingProductRematch.conflict}개 충돌 검토 · {runtime.catalogCoverage.existingProductRematch.unlinked}개 미연결
                  </p>
                )}
                <details>
                  <summary>연구 후보 {runtime.catalogCoverage.healthKrConfirmedCount}건의 약효군 분포</summary>
                  <div>
                    {Object.entries(runtime.catalogCoverage.classificationCounts).map(
                      ([classId, count]) => (
                        <span key={classId}>{catalogClassLabels[classId] ?? classId} {count}건</span>
                      ),
                    )}
                  </div>
                </details>
              </details>
            )}
            <div className={styles.phraseBox}>
              <p className={styles.phraseLabel}>
                <span>AI</span> 문장으로 찾기
              </p>
              <p className={styles.phraseHelp}>
                제품명을 몰라도 됩니다. 어떤 약인지 그대로 적으면 관련 성분을 골라
                검색어로 넣어 드려요.
              </p>
              <div className={styles.phraseRow}>
                <input
                  value={phrase}
                  onChange={(event) => setPhrase(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void resolvePhrase();
                  }}
                  maxLength={200}
                  placeholder="예: 머리 아플 때 먹는 약"
                  aria-label="찾는 약 설명"
                  className={styles.phraseInput}
                />
                <button
                  type="button"
                  onClick={() => void resolvePhrase()}
                  disabled={phrasePending || !phrase.trim()}
                  className={styles.phraseButton}
                >
                  {phrasePending ? "찾는 중" : "성분 찾기"}
                </button>
              </div>
              {phraseTerms.length > 0 && (
                <p className={styles.phraseResult}>
                  <span>고른 성분</span>
                  {phraseTerms.map((term) => (
                    <button
                      key={term}
                      type="button"
                      className={styles.phraseTerm}
                      onClick={() => setQuery(term)}
                    >
                      {term}
                    </button>
                  ))}
                </p>
              )}
              {phraseNote && <p className={styles.phraseNote}>{phraseNote}</p>}
            </div>
            <label className={styles.searchBox}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m21 21-4.35-4.35m1.35-5.15A6.5 6.5 0 1 1 5 11.5a6.5 6.5 0 0 1 13 0Z" />
              </svg>
              <span className="sr-only">일반의약품 제품명·성분명·약효군 검색</span>
              <input
                name="otc-product-search"
                type="search"
                value={query}
                onChange={(event) => {
                  clearActiveDemo();
                  setQuery(event.target.value);
                }}
                placeholder="예: 타이레놀, 아세트아미노펜, 감기약…"
                autoComplete="off"
              />
              {query && (
                <button type="button" onClick={() => setQuery("")} aria-label="검색어 지우기">
                  ×
                </button>
              )}
            </label>

            {query.trim() ? (
              <>
              <p className="sr-only" role="status" aria-live="polite">
                선택 가능한 제품 {results.verified.length}개, 연구 후보 {results.candidates.length}개
              </p>
              <div className={styles.searchResults}>
                {results.verified.map((product) => (
                  <button
                    key={product.productId}
                    type="button"
                    onClick={() => addProduct(product)}
                    disabled={selectedIds.has(product.productId)}
                  >
                    <span>
                      <strong>{product.productName}</strong>
                      <small>
                        {product.ingredients
                          .slice(0, 3)
                          .map((ingredient) => ingredient.nameKo)
                          .join(" · ")}
                        {product.ingredients.length > 3
                          ? ` 외 ${product.ingredients.length - 3}개`
                          : ""}
                      </small>
                    </span>
                    <b>{selectedIds.has(product.productId) ? "담김" : "+ 담기"}</b>
                  </button>
                ))}
                {results.candidates.map((candidate) => (
                  <div className={styles.pendingResult} key={candidate.candidateId}>
                    <span>
                      <strong>{candidate.productName}</strong>
                      <small>{candidate.className}</small>
                      <small className={styles.pendingExclusion}>
                        현재 점검에 사용되지 않음
                      </small>
                    </span>
                    <b>{candidateStatus(candidate.status)}</b>
                  </div>
                ))}
                {!results.verified.length && !results.candidates.length && (
                  <div className={styles.searchEmpty}>
                    <strong>연구 범위에서 찾지 못했어요.</strong>
                    <span>제품명 일부만 입력하거나 포장의 정확한 이름을 확인해 주세요.</span>
                  </div>
                )}
              </div>
              </>
            ) : (
              <div className={styles.productShelf} aria-label="식약처 허가 확인 제품">
                <div className={styles.productShelfHeader}>
                  <span>허가 확인 제품 전체</span>
                  <b>{shelfProducts.length}개</b>
                </div>
                <label className={styles.classSelect}>
                  <span>약효군</span>
                  <select
                    name="therapeutic-class"
                    value={activeTherapeuticClass}
                    onChange={(event) => setActiveTherapeuticClass(event.target.value)}
                  >
                    {therapeuticClasses.map((therapeuticClass) => (
                      <option key={therapeuticClass} value={therapeuticClass}>
                        {therapeuticClass}
                      </option>
                    ))}
                  </select>
                </label>
                <div className={styles.productShelfGrid}>
                  {shelfProducts.map((product) => (
                    <button
                      key={product.productId}
                      type="button"
                      onClick={() => addProduct(product)}
                      disabled={selectedIds.has(product.productId)}
                    >
                      <span>{product.productName.replace(/\([^)]*\)/g, "")}</span>
                      <small>
                        {product.ingredients
                          .slice(0, 2)
                          .map((ingredient) => ingredient.nameKo)
                          .join(" · ")}
                        {product.ingredients.length > 2
                          ? ` 외 ${product.ingredients.length - 2}개`
                          : ""}
                      </small>
                      <b>{selectedIds.has(product.productId) ? "담김" : "+ 담기"}</b>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className={styles.selectedSection}>
            <div className={styles.sectionTitleRow}>
              <h3>선택한 약</h3>
              {selected.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    clearActiveDemo();
                    setSelectedDrafts([]);
                  }}
                >
                  담은 약 모두 비우기
                </button>
              )}
            </div>
            {selected.length === 0 ? (
              <div className={styles.emptySelection}>
                <span aria-hidden="true">+</span>
                <p>함께 사용하거나 복용하는 약을 1개 이상 담아주세요.</p>
              </div>
            ) : (
              <div className={styles.selectedList}>
                {selectedDrafts.map((item, index) => (
                  <article key={item.product.productId} className={styles.selectedCard}>
                    <div className={styles.selectedCardHeader}>
                      <div>
                        <strong>{item.product.productName}</strong>
                        <small>
                          {item.product.ingredients
                            .map(
                              (ingredient) =>
                                `${ingredient.nameKo} ${formatAmount(ingredient.amountPerUnit)}${ingredient.unit}`,
                            )
                            .join(" · ")}
                        </small>
                        {productSupportById.get(item.product.productId) && (
                          <ProductSupportDetails
                            summary={productSupportById.get(item.product.productId)!}
                            product={item.product}
                            showLimitTooltip
                          />
                        )}
                        {catalogMatchesByItemSequence.get(item.product.itemSequence) && (() => {
                          const match = catalogMatchesByItemSequence.get(item.product.itemSequence)!;
                          return (
                            <div className={styles.catalogMatchLine}>
                              <span data-status={match.matchStatus}>
                                {match.matchStatus === "success" ? "약학정보원 품목 연결" : "연결 충돌 검토"}
                              </span>
                              <small>
                                {match.officialItemName} · {match.officialManufacturer} · {match.officialDosageForm}
                              </small>
                              <a href={match.sourceUrl} target="_blank" rel="noreferrer">
                                약학정보원 원문
                              </a>
                            </div>
                          );
                        })()}
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          clearActiveDemo();
                          setSelectedDrafts((items) =>
                            items.filter((_, currentIndex) => currentIndex !== index),
                          );
                        }}
                        aria-label={`${item.product.productName} 빼기`}
                      >
                        ×
                      </button>
                    </div>
                    <div className={styles.doseGrid}>
                      <label>
                        <span>한 번에</span>
                        <span className={styles.inputWithUnit}>
                          <input
                            name={`${item.product.productId}-units-per-dose`}
                            type="number"
                            min="0.1"
                            step="0.1"
                            inputMode="decimal"
                            autoComplete="off"
                            value={item.unitsPerDose}
                            aria-invalid={Boolean(
                              visibleInputIssues.some(
                                (issue) =>
                                  issue.productId === item.product.productId &&
                                  issue.field === "unitsPerDose",
                              ),
                            )}
                            aria-describedby={`${item.product.productId}-dose-help`}
                            onChange={(event) =>
                              updateSelectedDraft(index, {
                                unitsPerDose: event.target.value,
                              })
                            }
                          />
                          <b>{item.product.doseUnitLabel}</b>
                        </span>
                      </label>
                      <label>
                        <span>하루</span>
                        <span className={styles.inputWithUnit}>
                          <input
                            name={`${item.product.productId}-doses-per-day`}
                            type="number"
                            min="1"
                            step="1"
                            inputMode="numeric"
                            autoComplete="off"
                            value={item.dosesPerDay}
                            aria-invalid={Boolean(
                              visibleInputIssues.some(
                                (issue) =>
                                  issue.productId === item.product.productId &&
                                  issue.field === "dosesPerDay",
                              ),
                            )}
                            aria-describedby={`${item.product.productId}-dose-help`}
                            onChange={(event) =>
                              updateSelectedDraft(index, {
                                dosesPerDay: event.target.value,
                              })
                            }
                          />
                          <b>회</b>
                        </span>
                      </label>
                      <label>
                        <span>지난 사용·복용 후</span>
                        <span className={styles.inputWithUnit}>
                          <input
                            name={`${item.product.productId}-hours-since-dose`}
                            type="number"
                            min="0"
                            step="0.5"
                            inputMode="decimal"
                            autoComplete="off"
                            value={item.hoursSincePreviousDose}
                            placeholder="예: 4…"
                            onChange={(event) =>
                              updateSelectedDraft(index, {
                                hoursSincePreviousDose: event.target.value,
                              })
                            }
                          />
                          <b>시간</b>
                        </span>
                      </label>
                      <label>
                        <span>연속 사용·복용</span>
                        <span className={styles.inputWithUnit}>
                          <input
                            name={`${item.product.productId}-continuous-days`}
                            type="number"
                            min="1"
                            step="1"
                            inputMode="numeric"
                            autoComplete="off"
                            value={item.continuousDays}
                            placeholder="예: 3…"
                            onChange={(event) =>
                              updateSelectedDraft(index, {
                                continuousDays: event.target.value,
                              })
                            }
                          />
                          <b>일</b>
                        </span>
                      </label>
                    </div>
                    <p
                      id={`${item.product.productId}-dose-help`}
                      className={styles.doseHelp}
                    >
                      {isRequiredDoseDraftEmpty(item)
                        ? "한 번 사용량과 하루 횟수를 입력하면 용량 계산을 시작합니다."
                        : "입력한 사용량으로 성분별 하루 총량과 허가상 상한을 비교합니다."}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        <section
          className={styles.panel}
          data-collapsed={openStep !== 2 ? "true" : "false"}
          aria-labelledby="profile-heading"
        >
          <header className={styles.panelHeader}>
            <span className={styles.panelIndex}>2</span>
            <div>
              <h2 id="profile-heading">내 조건 더하기</h2>
              <p>해당 항목만 골라주세요. 입력 내용은 저장하지 않아요.</p>
            </div>
            <span className={styles.countBadge}>{activeConditionCount}개</span>
            <button
              type="button"
              className={styles.stepToggle}
              aria-expanded={openStep === 2}
              onClick={() => setOpenStep(openStep === 2 ? 1 : 2)}
            >
              {openStep === 2 ? "접기" : "입력하기"}
            </button>
          </header>
          {openStep !== 2 && (
            <p className={styles.stepSummary}>
              {activeConditionCount > 0
                ? `조건 ${activeConditionCount}개를 반영했습니다.`
                : "해당하는 조건이 있으면 눌러서 입력하세요."}
            </p>
          )}

          <div className={styles.profileBody}>
            <p className={styles.profileScopeNotice}>
              제품별 공개 안전성 규칙이나 허가 사용·복용 조건이 연결된 입력만
              판정에 사용합니다.
            </p>
            <label className={styles.fieldLabel}>
              <span>
                나이 <small>선택</small>
                <InputSupportStatus
                  id="age-years-support"
                  selectedCount={selected.length}
                  supportedCount={ageSupportCount}
                  hasCurrentInput={profile.ageYears !== undefined}
                  hasCoverageGap={hasCoverageGapFor(["age_restriction"])}
                  hasInputIssue={hasInputIssueFor(["ageYears"])}
                />
              </span>
              <span className={styles.inputWithUnit}>
                <input
                  name="age-years"
                  type="number"
                  min="0"
                  max="120"
                  inputMode="numeric"
                  autoComplete="off"
                  aria-describedby="age-years-support"
                  value={profile.ageYears ?? ""}
                  placeholder="예: 35…"
                  onChange={(event) =>
                    {
                      clearActiveDemo();
                      setProfile((value) => ({
                        ...value,
                        ageYears: event.target.value
                          ? Number(event.target.value)
                          : undefined,
                      }));
                    }
                  }
                />
                <b>세</b>
              </span>
            </label>

            <fieldset className={styles.conditionFieldset}>
              <legend>해당되는 상태</legend>
              <div className={styles.conditionGrid}>
                {conditionOptions.map(({ key, label, ruleType }) => {
                  const supportId = `${key}-support`;
                  return (
                    <label key={key} data-checked={Boolean(profile[key])}>
                      <input
                        type="checkbox"
                        name={`profile-${key}`}
                        checked={Boolean(profile[key])}
                        aria-describedby={supportId}
                        onChange={(event) =>
                          {
                            clearActiveDemo();
                            setProfile((value) => ({
                              ...value,
                              [key]: event.target.checked,
                              ...(key === "pregnant" && !event.target.checked
                                ? { pregnancyTrimester: undefined }
                                : {}),
                            }));
                          }
                        }
                      />
                      <span aria-hidden="true">✓</span>
                      <span className={styles.conditionCopy}>
                        <strong>{label}</strong>
                        <InputSupportStatus
                          id={supportId}
                          selectedCount={selected.length}
                          supportedCount={selectedSupportCount([ruleType])}
                          hasCurrentInput={Boolean(profile[key])}
                          hasCoverageGap={hasCoverageGapFor([ruleType])}
                          hasInputIssue={false}
                        />
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            {profile.pregnant && (
              <label
                className={`${styles.fieldLabel} ${styles.pregnancyTrimesterField}`}
              >
                <span>
                  임신 시기 <small>선택</small>
                  <InputSupportStatus
                    id="pregnancy-trimester-support"
                    selectedCount={selected.length}
                    supportedCount={selectedSupportCount([
                      "pregnancy_lactation",
                    ])}
                    hasCurrentInput
                    hasCoverageGap={hasCoverageGapFor([
                      "pregnancy_lactation",
                    ])}
                    hasInputIssue={hasInputIssueFor(["pregnancyTrimester"])}
                  />
                </span>
                <select
                  name="pregnancy-trimester"
                  value={profile.pregnancyTrimester ?? ""}
                  aria-describedby="pregnancy-trimester-support pregnancy-trimester-scope"
                  onChange={(event) => {
                    clearActiveDemo();
                    setProfile((value) => ({
                      ...value,
                      pregnancyTrimester: event.target.value
                        ? (Number(event.target.value) as 1 | 2 | 3)
                        : undefined,
                    }));
                  }}
                >
                  <option value="">모름</option>
                  <option value="1">1기</option>
                  <option value="2">2기</option>
                  <option value="3">3기</option>
                </select>
                <small id="pregnancy-trimester-scope">
                  현재 어린이부루펜의 임신 3기만 판정합니다. 모름·1기·2기는
                  추가 확인 조건으로 남깁니다.
                </small>
              </label>
            )}

            <label className={styles.fieldLabel}>
              <span>
                함께 사용·복용 중인 다른 약 <small>선택</small>
                <InputSupportStatus
                  id="other-medications-support"
                  selectedCount={selected.length}
                  supportedCount={medicationSupportCount}
                  hasCurrentInput={profile.medications.length > 0}
                  hasCoverageGap={hasCoverageGapFor([
                    "anticoagulant_antiplatelet",
                    "sedative_medication",
                    "medication_interaction",
                  ])}
                  hasInputIssue={false}
                />
              </span>
              <textarea
                name="other-medications"
                value={medicationText}
                rows={2}
                autoComplete="off"
                aria-describedby="other-medications-support other-medications-scope"
                onChange={(event) => {
                  clearActiveDemo();
                  setMedicationText(event.target.value);
                  setProfile((value) => ({
                    ...value,
                    medications: event.target.value
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  }));
                }}
                placeholder="예: 와파린, 수면제… (쉼표로 구분)"
              />
              <small id="other-medications-scope">
                현재 항응고제는 와파린·쿠마린 표현만 판정합니다.
                아픽사반·아스피린과 다른 약은 판정하지 않고 추가 확인 조건으로
                남깁니다. 진정·수면제는 연결된 제품 규칙의 용어만 분류합니다.
              </small>
            </label>

            <label className={`${styles.fieldLabel} ${styles.alertField}`}>
              <span>
                지금 나타난 심한 증상 <small>선택</small>
                <InputSupportStatus
                  id="red-flag-symptoms-support"
                  selectedCount={selected.length}
                  supportedCount={symptomSupportCount}
                  hasCurrentInput={profile.redFlagSymptoms.length > 0}
                  hasCoverageGap={hasCoverageGapFor(["urgent_referral"])}
                  hasInputIssue={false}
                />
              </span>
              <textarea
                name="red-flag-symptoms"
                value={symptomText}
                rows={2}
                autoComplete="off"
                aria-describedby="red-flag-symptoms-support red-flag-symptoms-scope"
                onChange={(event) => {
                  clearActiveDemo();
                  setSymptomText(event.target.value);
                  setProfile((value) => ({
                    ...value,
                    redFlagSymptoms: event.target.value
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  }));
                }}
                placeholder="예: 호흡곤란, 얼굴 부기…"
              />
              <small id="red-flag-symptoms-scope">
                입력한 표현이 선택 제품의 허가상 긴급 증상과 일치할 때만
                알려드려요.
              </small>
            </label>
          </div>
        </section>
        </div>

        <aside
          id="safety-result"
          className={`${styles.panel} ${styles.resultPanel}`}
          aria-labelledby="result-heading"
        >
          <header className={styles.panelHeader}>
            <span className={styles.panelIndex}>3</span>
            <div>
              <h2 id="result-heading">점검 결과</h2>
              <p>입력을 바꾸면 바로 다시 계산해요.</p>
            </div>
            {selected.length > 0 && (
              <button type="button" className={styles.resetButton} onClick={resetAll}>초기화</button>
            )}
          </header>

          <div className={styles.resultBody}>
            {runtime.rulesReleased === 0 && selected.length > 0 ? (
              <div className={styles.resultEmpty}>
                <span>!</span>
                <strong>현재 위험 판정을 제공하지 않아요.</strong>
                <p>연결된 공개 규칙이 없어 제품의 허가 성분과 함량만 보여드립니다.</p>
              </div>
            ) : !evaluation ? (
              <div className={styles.resultEmpty}>
                <span>+</span>
                <strong>약을 담으면 결과를 확인할 수 있어요.</strong>
                <p>제품별로 연결된 사용량·간격·질환·병용약 조건만 판정합니다.</p>
              </div>
            ) : (
              <>
                <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
                  점검 결과: 주의 {orderedFindings.length}개, 확인하지 못한 범위{" "}
                  {groupedCoverageGaps.length}종류
                </p>

                {(aiExplainPending || aiExplain?.ok) && (
                  <section className={styles.aiExplainPanel} aria-labelledby="ai-explain-title">
                    <p className={styles.aiExplainBadge}>
                      <span>AI 요약</span>
                      {aiExplainPending && <span> · 쓰는 중…</span>}
                    </p>
                    {aiExplain?.ok && (
                      <>
                        <h3 id="ai-explain-title" className={styles.aiExplainTitle}>
                          {aiExplain.explanation.summaryTitle}
                        </h3>
                        <p className={styles.aiExplainBody}>
                          {aiExplain.explanation.summaryParagraph}
                        </p>
                        {aiExplain.explanation.topAlerts.length > 0 && (
                          <ul className={styles.aiExplainList}>
                            {aiExplain.explanation.topAlerts.map((alert) => (
                              <li key={`${alert.title}-${alert.severity}`}>
                                <strong>[{alert.severity}] {alert.title}</strong> {alert.reason}
                              </li>
                            ))}
                          </ul>
                        )}
                        <p className={styles.aiExplainNote}>
                          판정은 아래 엔진 결과가 정본입니다. 이 요약은 그 결과를 읽기 쉽게 옮긴
                          것이고, 복용 시작·중단·용량은 판단하지 않습니다.
                        </p>
                      </>
                    )}
                  </section>
                )}

                {pendingDoseDrafts.length > 0 && (
                  <div className={styles.dosePendingNotice}>
                    <span aria-hidden="true">1·2</span>
                    <div>
                      <strong>복용량을 확인하면 용량 계산을 시작합니다.</strong>
                      <p>
                        {pendingDoseDrafts
                          .map((draft) => draft.product.productName)
                          .join(", ")}
                      </p>
                    </div>
                  </div>
                )}

                {visibleInputIssues.length > 0 && (
                  <div className={styles.inputNotice} role="alert">
                    <span aria-hidden="true">!</span>
                    <div>
                      <strong>입력값을 확인하세요.</strong>
                      <p>잘못된 값과 연결된 계산만 결과에서 제외했습니다.</p>
                      <ul>
                        {visibleInputIssues.map((issue) => (
                          <li key={issue.issueId}>{issue.messageKo}</li>
                        ))}
                      </ul>
                      <b>표시된 입력칸을 고친 뒤 결과를 다시 확인하세요.</b>
                    </div>
                  </div>
                )}

                <section
                  className={styles.resultScope}
                  aria-label="이번 선택에서 확인한 범위"
                >
                  <div>
                    <strong>{selected.length}</strong>
                    <span>선택 제품</span>
                  </div>
                  <div>
                    <strong>{selectedReleasedRuleBindingCount}</strong>
                    <span>제품별 공개 규칙 연결</span>
                  </div>
                  <div>
                    <strong>{selectedAdministrationConstraintCount}</strong>
                    <span>허가 사용·복용 조건</span>
                  </div>
                </section>

                <section
                  className={styles.resultSection}
                  aria-labelledby="result-actions-heading"
                >
                  <header className={styles.resultSectionHeading}>
                    <span>1</span>
                    <div>
                      <h3 id="result-actions-heading">주의 항목과 지금 할 일</h3>
                      <p>가장 높은 주의부터 이유와 다음 행동을 확인하세요.</p>
                    </div>
                  </header>

                  {showClearResult ? (
                    <div className={styles.clearResult}>
                      <span aria-hidden="true">✓</span>
                      <div>
                        <strong>연결된 기준에서는 위험 신호를 찾지 못했어요.</strong>
                        <p>
                          {evaluation.coverageGaps.length > 0
                            ? "아래 확인하지 못한 범위가 남아 있습니다. 포장과 허가사항도 함께 확인하세요."
                            : "안전하다는 보장은 아닙니다. 포장과 허가사항을 따르고 증상이 계속되면 전문가와 상담하세요."}
                        </p>
                      </div>
                    </div>
                  ) : showResultSummary ? (
                    <>
                      <div
                        className={styles.resultSummary}
                        data-urgent={urgentCount > 0}
                      >
                        <div className={styles.summaryTitle}>
                          <span aria-hidden="true">{urgentCount > 0 ? "!" : "i"}</span>
                          <div>
                            <strong>{orderedFindings.length}개 주의 항목</strong>
                            <p>
                              {urgentCount > 0
                                ? "즉시 확인이 필요한 항목이 " + urgentCount + "개 있습니다."
                                : "첫 항목부터 판정 이유와 지금 할 일을 확인하세요."}
                            </p>
                          </div>
                        </div>
                        <small className={styles.summaryEvidence}>
                          현재 제품 규칙 원문 전체 일치{" "}
                          {findingsWithAllDirectRuleEvidence}개 · 일부 일치{" "}
                          {findingsWithPartialDirectRuleEvidence}개 · 대표 제품 원문만{" "}
                          {findingsWithRepresentativeRuleEvidence}개 · 직접 일치 문헌{" "}
                          {findingsWithDirectLiterature}/{orderedFindings.length} · 배경 문헌{" "}
                          {findingsWithBackgroundLiterature}/{orderedFindings.length}
                        </small>
                      </div>

                      <div className={styles.findings}>
                        {orderedFindings.map((finding, index) => {
                          const findingContext = buildFindingContext(finding, selected);
                          return (
                            <article
                              key={finding.findingId}
                              data-severity={finding.severity}
                            >
                              <details
                                className={styles.findingDisclosure}
                                open={
                                  openFindingIds[finding.findingId] ??
                                  (index === 0 || finding.severity === "urgent")
                                }
                                onToggle={(event) => {
                                  const open = event.currentTarget.open;
                                  setOpenFindingIds((current) =>
                                    current[finding.findingId] === open
                                      ? current
                                      : { ...current, [finding.findingId]: open },
                                  );
                                }}
                              >
                                <summary>
                                  <span className={styles.findingNumber}>
                                    {index + 1}
                                  </span>
                                  <span className={styles.findingSummaryCopy}>
                                    <small>
                                      {finding.severity === "urgent"
                                        ? "즉시 확인"
                                        : finding.severity === "high"
                                          ? "높은 주의"
                                          : "주의"}
                                    </small>
                                    <h4>{finding.titleKo}</h4>
                                    <span>{finding.detailKo}</span>
                                  </span>
                                  <span
                                    className={styles.findingChevron}
                                    aria-hidden="true"
                                  />
                                </summary>
                                <div className={styles.findingContent}>
                                  {findingLines[finding.findingId] && (
                                    <p className={styles.findingPlain}>
                                      <span>쉬운 설명</span>
                                      {findingLines[finding.findingId]}
                                    </p>
                                  )}
                                  <div className={styles.nextAction}>
                                    <span>지금 할 일</span>
                                    <strong>{finding.nextActionKo}</strong>
                                  </div>
                                  <div className={styles.findingRationale}>
                                    <span>판정 이유</span>
                                    <p>{finding.detailKo}</p>
                                    <dl>
                                      <div>
                                        <dt>판정 제품</dt>
                                        <dd>
                                          {findingContext.productNames.join(", ")}
                                        </dd>
                                      </div>
                                      {findingContext.ingredientFacts.length > 0 && (
                                        <div>
                                          <dt>포함 성분·함량</dt>
                                          <dd>
                                            {findingContext.ingredientFacts.join(", ")}
                                          </dd>
                                        </div>
                                      )}
                                    </dl>
                                  </div>
                                  {finding.members.length > 1 && (
                                    <div className={styles.groupedMemberSummary}>
                                      <strong>묶인 성분별 계산</strong>
                                      <ul>
                                        {finding.members.map((member) => (
                                          <li key={member.findingId}>
                                            <span>
                                              {member.ingredientIds
                                                .map(
                                                  (ingredientId) =>
                                                    ingredientNames.get(ingredientId) ??
                                                    ingredientId,
                                                )
                                                .join(", ")}
                                            </span>
                                            <b>
                                              {member.calculatedAmount === undefined
                                                ? "계산값 없음"
                                                : formatAmount(
                                                    member.calculatedAmount,
                                                  ) +
                                                  " " +
                                                  (member.unit ?? "")}
                                            </b>
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              </details>
                            </article>
                          );
                        })}
                      </div>
                    </>
                  ) : null}
                </section>

                <section
                  className={styles.resultSection}
                  aria-labelledby="direct-authorization-heading"
                  aria-label="판정에 사용한 식약처 허가 근거"
                >
                  <header className={styles.resultSectionHeading}>
                    <span>2</span>
                    <div>
                      <h3 id="direct-authorization-heading">
                        현재 제품의 식약처 허가 원문
                      </h3>
                      <p>
                        현재 선택 제품과 직접 일치한 규칙 원문과 제품·성분·계산
                        원문만 모았습니다.
                      </p>
                    </div>
                  </header>

                  {orderedFindings.length === 0 ? (
                    <div className={styles.directProductSources}>
                      {selected.map(({ product }) => (
                        <a
                          className={styles.officialEvidenceLink}
                          key={product.productId}
                          href={product.evidence.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <strong>{product.productName}</strong>
                          <span>{product.evidence.locator}</span>
                        </a>
                      ))}
                    </div>
                  ) : (
                    <div className={styles.evidenceGroups}>
                      {orderedFindings.map((finding) => {
                        const display = ruleEvidenceByFinding.get(
                          finding.findingId,
                        );
                        return (
                          <article
                            className={styles.evidenceGroup}
                            key={"direct:" + finding.findingId}
                          >
                            <header>
                              <h4>{finding.titleKo}</h4>
                              <span>
                                현재 제품 {display?.matchedProductCount ?? 0}/
                                {display?.findingProductCount ?? finding.productIds.length}개
                                직접 일치 · 규칙 원문 {display?.direct.length ?? 0}건 ·
                                제품·계산 원문 {finding.evidence.length}건
                              </span>
                            </header>
                            {display && display.direct.length > 0 ? (
                              <div>
                                <strong>판정 규칙 근거</strong>
                                {display.direct.map((source) => (
                                  <a
                                    className={styles.officialEvidenceLink}
                                    key={[
                                      source.ruleId,
                                      source.itemSequence,
                                      source.locator,
                                    ].join(":")}
                                    href={source.url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    <strong>{source.productName}</strong>
                                    <span>{source.locator}</span>
                                    <q>{source.excerptKo}</q>
                                  </a>
                                ))}
                              </div>
                            ) : (
                              <p className={styles.evidenceEmpty}>
                                현재 제품과 직접 일치한 규칙 원문은 없습니다. 대표
                                제품 원문은 마지막 구역에서 따로 표시합니다.
                              </p>
                            )}
                            {display?.productMatch === "partial" && (
                              <p className={styles.evidenceEmpty}>
                                일부 선택 제품에는 이 규칙의 직접 허가원문이 연결되지
                                않았습니다. 위 숫자에서 직접 일치 제품 수를 확인하세요.
                              </p>
                            )}
                            {finding.evidence.length > 0 && (
                              <div>
                                <strong>제품·성분·계산 원문</strong>
                                {finding.evidence.map((source) => (
                                  <a
                                    className={styles.officialEvidenceLink}
                                    key={[
                                      finding.findingId,
                                      source.sourceId,
                                      source.locator,
                                    ].join(":")}
                                    href={source.url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    <strong>
                                      {formatEvidenceSource(source.sourceId)}
                                    </strong>
                                    <span>{source.locator}</span>
                                  </a>
                                ))}
                              </div>
                            )}
                            {finding.ruleType === "max_daily_dose" && (
                              <p className={styles.authorizationLimitCallout}>
                                허가상 사용 상한은 개인에게 맞는 권장량이 아닙니다.
                              </p>
                            )}
                          </article>
                        );
                      })}
                    </div>
                  )}
                </section>

                <section
                  className={styles.resultSection}
                  aria-labelledby="coverage-heading"
                >
                  <header className={styles.resultSectionHeading}>
                    <span>3</span>
                    <div>
                      <h3 id="coverage-heading">확인하지 못한 범위</h3>
                      <p>
                        입력했지만 현재 제품 규칙에 연결되지 않은 조건을 숨기지
                        않습니다.
                      </p>
                    </div>
                  </header>
                  {evaluation.coverageGaps.length > 0 ? (
                    <div className={styles.coverageDetails}>
                      <p>
                        {groupedCoverageGaps.length}종류 ·{" "}
                        {evaluation.coverageGaps.length}개 제품 조건
                      </p>
                      <ul>
                        {groupedCoverageGaps.map((gap) => (
                          <li key={gap.groupId}>
                            <strong>{gap.titleKo}</strong>
                            <span>{gap.productNames.join(", ")}</span>
                            {gap.profileDetailMessages.map((message) => (
                              <small key={message}>{message}</small>
                            ))}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className={styles.sectionClear}>
                      입력한 조건 중 현재 지원 범위 밖으로 분류된 항목은 없습니다.
                    </p>
                  )}
                </section>

                <section
                  className={styles.resultSection}
                  aria-labelledby="calculation-heading"
                >
                  <header className={styles.resultSectionHeading}>
                    <span>4</span>
                    <div>
                      <h3 id="calculation-heading">성분별 계산 상세</h3>
                      <p>
                        사용자가 확인한 사용량만 계산합니다. 빈 복용량은 0으로
                        바꾸지 않습니다.
                      </p>
                    </div>
                  </header>
                  {Object.keys(evaluation.ingredientDailyTotals).length > 0 ? (
                    <div className={styles.totalDetails}>
                      {Object.entries(evaluation.ingredientDailyTotals).map(
                        ([ingredientId, total]) => (
                          <p key={ingredientId}>
                            <span>
                              {ingredientNames.get(ingredientId) ?? ingredientId}
                            </span>
                            <strong>
                              {formatAmount(total.amount)} {total.unit}/일
                            </strong>
                          </p>
                        ),
                      )}
                    </div>
                  ) : (
                    <p className={styles.sectionClear}>
                      한 번 사용량과 하루 횟수를 입력하면 성분별 계산값을
                      표시합니다.
                    </p>
                  )}
                  <p className={styles.authorizationLimitCallout}>
                    비교 상한은 허가사항에서 확인한 최대값이며 개인 적정용량이나
                    복용 권고가 아닙니다.
                  </p>
                </section>

                <section
                  className={styles.resultSection}
                  aria-labelledby="v5-literature-heading"
                  aria-label="참고 문헌 · 판정 근거 아님"
                >
                  <header className={styles.resultSectionHeading}>
                    <span>5</span>
                    <div>
                      <h3 id="v5-literature-heading">
                        v5.0 채택 PubMed 문헌
                      </h3>
                      <p>
                        현재 판정과 직접 일치한 문헌과 배경 문헌을 한 판정 안에서
                        구분합니다.
                      </p>
                    </div>
                  </header>
                  <p className={styles.literatureDisclaimer}>
                    참고 문헌은 판정 근거가 아니며 허가원문 판정을 바꾸지
                    않습니다.
                  </p>
                  <strong className={styles.srSectionLabel}>참고 문헌</strong>

                  {hasFinalLiterature ? (
                    <div className={styles.literatureGroups}>
                      {orderedFindings.map((finding) => {
                        const direct =
                          literatureByFinding.get(finding.findingId)?.direct ?? [];
                        const background =
                          literatureByFinding.get(finding.findingId)?.background ?? [];
                        const pooled = rulePoolFor(finding.ruleId)?.listed ?? 0;
                        if (!direct.length && !background.length && !pooled)
                          return null;
                        return (
                          <FindingLiteratureGroup
                            key={"direct-literature:" + finding.findingId}
                            finding={finding}
                            matches={{ direct, background }}
                            profile={profile}
                            selected={selected}
                          />
                        );
                      })}
                    </div>
                  ) : (
                    <p className={styles.sectionClear}>
                      이번 결과와 연결된 v5.0 최종 문헌은 없습니다.
                    </p>
                  )}
                </section>

                <section
                  className={styles.resultSection}
                  aria-labelledby="background-evidence-heading"
                >
                  <header className={styles.resultSectionHeading}>
                    <span>6</span>
                    <div>
                      <h3 id="background-evidence-heading">
                        대표 제품 허가 원문
                      </h3>
                      <p>
                        규칙을 승인할 때 사용한 다른 제품의 허가 원문을 현재 제품
                        직접 원문과 구분해 표시합니다.
                      </p>
                    </div>
                  </header>

                  {hasRepresentativeRuleEvidence && (
                    <div className={styles.evidenceGroups}>
                      {orderedFindings.map((finding) => {
                        const display = ruleEvidenceByFinding.get(
                          finding.findingId,
                        );
                        if (!display || display.representative.length === 0) {
                          return null;
                        }
                        return (
                          <article
                            className={styles.evidenceGroup}
                            key={"representative:" + finding.findingId}
                          >
                            <header>
                              <h4>{finding.titleKo}</h4>
                              <span>대표 제품 원문 {display.representative.length}건</span>
                            </header>
                            <p className={styles.evidenceEmpty}>
                              아래 원문은 규칙을 승인한 대표 제품 자료입니다. 현재
                              선택 제품의 직접 원문이 아닙니다.
                            </p>
                            {display.representative.map((source) => (
                              <a
                                className={styles.officialEvidenceLink}
                                key={[
                                  "representative",
                                  source.ruleId,
                                  source.itemSequence,
                                  source.locator,
                                ].join(":")}
                                href={source.url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <strong>{source.productName}</strong>
                                <span>{source.locator}</span>
                                <q>{source.excerptKo}</q>
                              </a>
                            ))}
                          </article>
                        );
                      })}
                    </div>
                  )}

                  {!hasRepresentativeRuleEvidence && (
                    <p className={styles.sectionClear}>
                      이번 결과에 현재 제품과 다른 대표 제품 원문은 없습니다.
                    </p>
                  )}
                </section>
              </>
            )}
          </div>

          <footer className={styles.resultFooter}>
            <span>
              이번 선택: 제품별 공개 규칙 연결{" "}
              {selectedReleasedRuleBindingCount}건 · 허가 사용·복용 조건{" "}
              {selectedAdministrationConstraintCount}건
            </span>
            <span>연구용 시제품 · 임상 사용 승인 아님</span>
          </footer>
        </aside>
      </div>

      {selected.length > 0 && (
        <a className={styles.mobileResultLink} href="#safety-result">
          <span>선택 {selected.length}개</span>
          <strong>
            {pendingDoseDrafts.length > 0
              ? `복용량 입력 ${pendingDoseDrafts.length}개 남음`
              : visibleInputIssues.length > 0
                ? `입력 오류 ${visibleInputIssues.length}개 보기`
                : orderedFindings.length > 0
                  ? `주의 ${orderedFindings.length}개 보기`
                  : evaluation && evaluation.coverageGaps.length > 0
                    ? `추가 확인 ${groupedCoverageGaps.length}종류 보기`
                    : "점검 결과 보기"}
          </strong>
        </a>
      )}
    </div>
  );
}

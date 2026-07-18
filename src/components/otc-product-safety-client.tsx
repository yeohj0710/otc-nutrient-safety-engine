"use client";

import { useEffect, useMemo, useState } from "react";

import literatureData from "@/src/generated/otc-supporting-literature.json";
import { evaluateOtcSafety } from "@/src/lib/otc/engine";
import {
  buildFindingContext,
  formatEvidenceSource,
  groupCoverageGaps,
  literatureRelationLabel,
  productsForTherapeuticClass,
  ruleEvidenceForFinding,
  supportingLiteratureForFinding,
  type SupportingLiterature,
} from "@/src/lib/otc/presentation";
import { searchOtcProducts } from "@/src/lib/otc/search";
import type {
  OtcProduct,
  RuleEvidenceLink,
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

const conditionOptions: Array<{ key: BooleanProfileKey; label: string }> = [
  { key: "liverDisease", label: "간질환" },
  { key: "kidneyDisease", label: "신장질환" },
  { key: "giBleedingOrUlcer", label: "위장관 출혈·궤양" },
  { key: "hypertensionOrCardiovascularDisease", label: "고혈압·심혈관질환" },
  { key: "pregnant", label: "임신 중" },
  { key: "lactating", label: "수유 중" },
  { key: "willDrive", label: "복용 후 운전" },
  { key: "alcohol", label: "매일 3잔 이상 정기 음주" },
];

export const quickChecks: Array<{
  label: string;
  description: string;
  productIds: readonly string[];
  profilePatch: Partial<UserProfile>;
  expectedRuleType: string;
}> = [
  {
    label: "감기약 + 해열제",
    description: "아세트아미노펜 중복 확인",
    productIds: ["MFDS-196800036", "MFDS-202106092"],
    profilePatch: {},
    expectedRuleType: "duplicate_ingredient",
  },
  {
    label: "소염진통제 2종",
    description: "NSAID 계열 중복 확인",
    productIds: ["MFDS-201110646", "MFDS-197500016"],
    profilePatch: {},
    expectedRuleType: "duplicate_pharmacologic_class",
  },
  {
    label: "감기약 + 알레르기약",
    description: "항히스타민 중복 확인",
    productIds: ["MFDS-196800036", "MFDS-200610765"],
    profilePatch: {},
    expectedRuleType: "duplicate_pharmacologic_class",
  },
  {
    label: "소화제 2종",
    description: "시메티콘 등 중복 성분 확인",
    productIds: ["MFDS-198700405", "MFDS-200300406"],
    profilePatch: {},
    expectedRuleType: "duplicate_ingredient",
  },
  {
    label: "감기약 복용 후 운전",
    description: "졸림·운전 주의 확인",
    productIds: ["MFDS-196800036"],
    profilePatch: { willDrive: true },
    expectedRuleType: "sedation_driving",
  },
  {
    label: "이부프로펜 + 와파린",
    description: "항응고제 병용 주의 확인",
    productIds: ["MFDS-198601920"],
    profilePatch: { medications: ["와파린"] },
    expectedRuleType: "anticoagulant_antiplatelet",
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

export function OtcProductSafetyClient({ runtime }: { runtime: OtcRuntime }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<SelectedProduct[]>([]);
  const [profile, setProfile] = useState<UserProfile>(initialProfile);
  const [medicationText, setMedicationText] = useState("");
  const [symptomText, setSymptomText] = useState("");
  const [activeTherapeuticClass, setActiveTherapeuticClass] = useState("전체");
  const [isEvaluating, setIsEvaluating] = useState(false);

  const results = useMemo(() => searchRuntime(runtime, query), [runtime, query]);
  const releasedRuleTypes = useMemo(
    () => new Set(runtime.releasedRuleTypes),
    [runtime.releasedRuleTypes],
  );
  const evaluation = useMemo(
    () =>
      runtime.rulesReleased > 0 && selected.length
        ? evaluateOtcSafety(
            selected,
            profile,
            releasedRuleTypes,
            runtime.urgentReferralBindings ?? [],
            runtime.ruleEvidenceByType,
          )
        : null,
    [
      profile,
      releasedRuleTypes,
      runtime.rulesReleased,
      runtime.ruleEvidenceByType,
      runtime.urgentReferralBindings,
      selected,
    ],
  );
  useEffect(() => {
    if (!evaluation) {
      const clearStatus = window.setTimeout(() => setIsEvaluating(false), 0);
      return () => window.clearTimeout(clearStatus);
    }

    const showStatus = window.setTimeout(() => setIsEvaluating(true), 0);
    const hideStatus = window.setTimeout(() => setIsEvaluating(false), 460);
    return () => {
      window.clearTimeout(showStatus);
      window.clearTimeout(hideStatus);
    };
  }, [evaluation]);
  const orderedFindings = useMemo(
    () =>
      [...(evaluation?.findings ?? [])].sort(
        (left, right) => severityRank[right.severity] - severityRank[left.severity],
      ),
    [evaluation],
  );
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
          supportingLiteratureForFinding(
            finding,
            literatureData as SupportingLiterature[],
            profile,
          ),
        ]),
      ),
    [orderedFindings, profile],
  );
  const findingsWithRuleEvidence = orderedFindings.filter(
    (finding) => (finding.ruleEvidence?.length ?? 0) > 0,
  ).length;
  const findingsWithLiterature = [...literatureByFinding.values()].filter(
    (papers) => papers.length > 0,
  ).length;

  const selectedIds = new Set(selected.map((item) => item.product.productId));
  const activeConditionCount = conditionOptions.filter(({ key }) => profile[key]).length;
  const urgentCount = orderedFindings.filter((finding) => finding.severity === "urgent").length;

  const addProduct = (product: OtcProduct) => {
    if (selectedIds.has(product.productId)) return;
    setSelected((items) => [
      ...items,
      { product, unitsPerDose: 1, dosesPerDay: 1 },
    ]);
    setQuery("");
  };

  const updateSelected = (index: number, patch: Partial<SelectedProduct>) => {
    setSelected((items) =>
      items.map((item, currentIndex) =>
        currentIndex === index ? { ...item, ...patch } : item,
      ),
    );
  };

  const applyQuickCheck = (quickCheck: (typeof quickChecks)[number]) => {
    const nextProfile = { ...initialProfile, ...quickCheck.profilePatch };
    setSelected(buildSelectedProducts(runtime, quickCheck.productIds));
    setProfile(nextProfile);
    setMedicationText(nextProfile.medications.join(", "));
    setSymptomText(nextProfile.redFlagSymptoms.join(", "));
    setQuery("");
  };

  const resetAll = () => {
    setQuery("");
    setSelected([]);
    setProfile(initialProfile);
    setMedicationText("");
    setSymptomText("");
  };

  return (
    <div className={styles.workspace}>
      <div className={styles.quickStart} aria-label="빠른 점검 예시">
        <div className={styles.quickStartCopy}>
          <span className={styles.liveDot} aria-hidden="true" />
          <div>
            <strong>바로 점검해보기</strong>
            <p>대표 조합을 불러온 뒤 내 복용량에 맞게 바꿀 수 있어요.</p>
          </div>
        </div>
        <div className={styles.quickCheckList}>
          {quickChecks.map((quickCheck) => (
            <button
              key={quickCheck.label}
              type="button"
              className={styles.quickCheckButton}
              onClick={() => applyQuickCheck(quickCheck)}
              aria-label={`${quickCheck.label}: ${quickCheck.description}`}
              title={quickCheck.description}
            >
              <span>{quickCheck.label}</span>
              <b aria-hidden="true">→</b>
            </button>
          ))}
        </div>
      </div>

      <div className={styles.workspaceGrid}>
        <div className={styles.inputColumn}>
        <section className={styles.panel} aria-labelledby="medicine-heading">
          <header className={styles.panelHeader}>
            <span className={styles.panelIndex}>1</span>
            <div>
              <h2 id="medicine-heading">사용 중인 약 담기</h2>
              <p>제품명만 찾으면 성분과 함량을 자동으로 불러와요.</p>
            </div>
            <span className={styles.countBadge}>{selected.length}개</span>
          </header>

          <div className={styles.searchArea}>
            {runtime.catalogCoverage && (
              <div className={styles.catalogScope}>
                <p className={styles.catalogSummary}>
                  판매 SKU {runtime.catalogCoverage.sourceSkuCount}건 중 {runtime.catalogCoverage.healthKrConfirmedCount}건이 약학정보원 공식 품목 {runtime.catalogCoverage.healthKrConfirmedUniqueProductCount}개와 연결됐고, <strong>현재 {runtime.products.length}개 제품을 점검할 수 있어요.</strong>
                </p>
                <p className={styles.catalogDescription}>
                  약학정보원 연결 제품은 연구 후보입니다. 식약처 허가 원문과 안전성 규칙까지 연결된 제품만 점검에 사용해요.
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
              </div>
            )}
            <label className={styles.searchBox}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m21 21-4.35-4.35m1.35-5.15A6.5 6.5 0 1 1 5 11.5a6.5 6.5 0 0 1 13 0Z" />
              </svg>
              <span className="sr-only">일반의약품 제품명 검색</span>
              <input
                name="otc-product-search"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="제품명을 검색하세요…"
                autoComplete="off"
              />
              {query && (
                <button type="button" onClick={() => setQuery("")} aria-label="검색어 지우기">
                  ×
                </button>
              )}
            </label>

            {query.trim() ? (
              <div className={styles.searchResults} aria-live="polite">
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
                <button type="button" onClick={() => setSelected([])}>약만 모두 빼기</button>
              )}
            </div>
            {selected.length === 0 ? (
              <div className={styles.emptySelection}>
                <span aria-hidden="true">+</span>
                <p>함께 사용하거나 복용하는 약을 1개 이상 담아주세요.</p>
              </div>
            ) : (
              <div className={styles.selectedList}>
                {selected.map((item, index) => (
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
                        onClick={() =>
                          setSelected((items) =>
                            items.filter((_, currentIndex) => currentIndex !== index),
                          )
                        }
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
                            value={item.unitsPerDose}
                            onChange={(event) =>
                              updateSelected(index, {
                                unitsPerDose: Number(event.target.value),
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
                            value={item.dosesPerDay}
                            onChange={(event) =>
                              updateSelected(index, {
                                dosesPerDay: Number(event.target.value),
                              })
                            }
                          />
                          <b>회</b>
                        </span>
                      </label>
                      <label>
                        <span>지난 복용 후</span>
                        <span className={styles.inputWithUnit}>
                          <input
                            name={`${item.product.productId}-hours-since-dose`}
                            type="number"
                            min="0"
                            step="0.5"
                            value={item.hoursSincePreviousDose ?? ""}
                            placeholder="선택…"
                            onChange={(event) =>
                              updateSelected(index, {
                                hoursSincePreviousDose: event.target.value
                                  ? Number(event.target.value)
                                  : undefined,
                              })
                            }
                          />
                          <b>시간</b>
                        </span>
                      </label>
                      <label>
                        <span>연속 복용</span>
                        <span className={styles.inputWithUnit}>
                          <input
                            name={`${item.product.productId}-continuous-days`}
                            type="number"
                            min="1"
                            step="1"
                            value={item.continuousDays ?? ""}
                            placeholder="선택…"
                            onChange={(event) =>
                              updateSelected(index, {
                                continuousDays: event.target.value
                                  ? Number(event.target.value)
                                  : undefined,
                              })
                            }
                          />
                          <b>일</b>
                        </span>
                      </label>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className={styles.panel} aria-labelledby="profile-heading">
          <header className={styles.panelHeader}>
            <span className={styles.panelIndex}>2</span>
            <div>
              <h2 id="profile-heading">내 조건 더하기</h2>
              <p>해당 항목만 골라주세요. 입력 내용은 저장하지 않아요.</p>
            </div>
            <span className={styles.countBadge}>{activeConditionCount}개</span>
          </header>

          <div className={styles.profileBody}>
            <label className={styles.fieldLabel}>
              <span>나이 <small>선택</small></span>
              <span className={styles.inputWithUnit}>
                <input
                  name="age-years"
                  type="number"
                  min="0"
                  max="120"
                  value={profile.ageYears ?? ""}
                  placeholder="예: 35…"
                  onChange={(event) =>
                    setProfile((value) => ({
                      ...value,
                      ageYears: event.target.value
                        ? Number(event.target.value)
                        : undefined,
                    }))
                  }
                />
                <b>세</b>
              </span>
            </label>

            <fieldset className={styles.conditionFieldset}>
              <legend>해당되는 상태</legend>
              <div className={styles.conditionGrid}>
                {conditionOptions.map(({ key, label }) => (
                  <label key={key} data-checked={Boolean(profile[key])}>
                    <input
                      type="checkbox"
                      checked={Boolean(profile[key])}
                      onChange={(event) =>
                        setProfile((value) => ({
                          ...value,
                          [key]: event.target.checked,
                        }))
                      }
                    />
                    <span aria-hidden="true">✓</span>
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>

            <label className={styles.fieldLabel}>
              <span>복용 중인 다른 약 <small>선택</small></span>
              <textarea
                name="other-medications"
                value={medicationText}
                rows={2}
                onChange={(event) => {
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
            </label>

            <label className={`${styles.fieldLabel} ${styles.alertField}`}>
              <span>지금 나타난 심한 증상 <small>선택</small></span>
              <textarea
                name="red-flag-symptoms"
                value={symptomText}
                rows={2}
                onChange={(event) => {
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
              <small>입력한 표현이 해당 제품의 허가상 긴급 증상과 일치할 때만 알려드려요.</small>
            </label>
          </div>
        </section>
        </div>

        <aside
          id="safety-result"
          className={`${styles.panel} ${styles.resultPanel}`}
          aria-labelledby="result-heading"
          aria-busy={isEvaluating}
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

          {isEvaluating && evaluation && (
            <div className={styles.calculationStatus} role="status" aria-live="polite">
              <span className={styles.calculationSpinner} aria-hidden="true" />
              <strong>성분과 복용 조건을 계산 중…</strong>
            </div>
          )}

          <div className={styles.resultBody}>
            {runtime.rulesReleased === 0 && selected.length > 0 ? (
              <div className={styles.resultEmpty}>
                <span>!</span>
                <strong>현재 위험 판정을 제공하지 않아요.</strong>
                <p>제품의 허가 성분과 함량만 확인할 수 있습니다.</p>
              </div>
            ) : !evaluation ? (
              <div className={styles.resultEmpty}>
                <span>+</span>
                <strong>약을 담으면 결과가 시작돼요.</strong>
                <p>한 제품만 담아도 용량·연령·질환 관련 조건을 확인할 수 있어요.</p>
              </div>
            ) : (
              <>
                {evaluation.inputIssues.length > 0 && (
                  <div className={styles.inputNotice} role="alert">
                    <span aria-hidden="true">!</span>
                    <div>
                      <strong>입력값을 확인하세요.</strong>
                      <p>잘못된 값은 안전성 계산에서 제외했습니다.</p>
                      <ul>
                        {evaluation.inputIssues.map((issue) => (
                          <li key={issue.issueId}>{issue.messageKo}</li>
                        ))}
                      </ul>
                      <b>입력값을 고친 뒤 다시 확인하세요.</b>
                    </div>
                  </div>
                )}

                {orderedFindings.length === 0 &&
                  evaluation.inputIssues.length === 0 && (
                    <div className={styles.clearResult}>
                      <span aria-hidden="true">✓</span>
                      <div>
                        <strong>연결된 기준에서는 위험 신호를 찾지 못했어요.</strong>
                        <p>
                          {evaluation.coverageGaps.length > 0
                            ? "아래 추가 확인 조건은 판정 범위 밖입니다. 포장과 허가사항도 함께 확인하세요."
                            : "안전하다는 보장은 아닙니다. 포장과 허가사항을 따르고 증상이 계속되면 전문가와 상담하세요."}
                        </p>
                      </div>
                    </div>
                  )}

                {orderedFindings.length > 0 && (
                  <>
                    <div className={styles.resultSummary} data-urgent={urgentCount > 0} role="status" aria-live="polite" aria-atomic="true">
                      <div className={styles.summaryTitle}>
                        <span aria-hidden="true">{urgentCount > 0 ? "!" : "i"}</span>
                        <div>
                          <strong>{orderedFindings.length}개 주의 항목</strong>
                          <p>
                            {urgentCount > 0
                              ? `이 중 ${urgentCount}개는 즉시 확인이 필요해요.`
                              : "첫 항목부터 판정 이유와 근거를 확인하세요."}
                          </p>
                        </div>
                      </div>
                      <small className={styles.summaryEvidence}>
                        식약처 규칙 근거 {findingsWithRuleEvidence}/{orderedFindings.length} · 직접 연결 학술문헌 {findingsWithLiterature}/{orderedFindings.length}
                      </small>
                    </div>
                    <div className={styles.findings}>
                      {orderedFindings.map((finding, index) => {
                        const supportingPapers = literatureByFinding.get(finding.findingId) ?? [];
                        const ruleEvidence = finding.ruleEvidence ?? [];
                        const ruleEvidenceDisplay = ruleEvidenceForFinding(
                          finding,
                          selected,
                          ruleEvidence,
                        );
                        const primaryRuleEvidence = ruleEvidenceDisplay.evidence;
                        const primaryPaper = supportingPapers[0];
                        const findingContext = buildFindingContext(finding, selected);
                        return (
                          <article key={finding.findingId} data-severity={finding.severity}>
                            <details
                              className={styles.findingDisclosure}
                              open={index === 0 || finding.severity === "urgent"}
                            >
                              <summary>
                                <span className={styles.findingNumber}>{index + 1}</span>
                                <span className={styles.findingSummaryCopy}>
                                  <small>{finding.severity === "urgent" ? "즉시 확인" : finding.severity === "high" ? "높은 주의" : "주의"}</small>
                                  <h3>{finding.titleKo}</h3>
                                  <span>{finding.detailKo}</span>
                                </span>
                                <span className={styles.findingChevron} aria-hidden="true" />
                              </summary>
                              <div className={styles.findingContent}>
                            {finding.severity === "urgent" && (
                              <div className={styles.nextAction}>
                                <span>지금 할 일</span>
                                <strong>{finding.nextActionKo}</strong>
                              </div>
                            )}
                            <div className={styles.findingRationale}>
                              <span>판정 이유</span>
                              <p>{finding.detailKo}</p>
                              <dl>
                                <div>
                                  <dt>판정 제품</dt>
                                  <dd>{findingContext.productNames.join(", ")}</dd>
                                </div>
                                {findingContext.ingredientFacts.length > 0 && (
                                  <div>
                                    <dt>포함 성분·함량</dt>
                                    <dd>{findingContext.ingredientFacts.join(", ")}</dd>
                                  </div>
                                )}
                              </dl>
                            </div>
                            {primaryRuleEvidence && (
                              <section className={styles.officialEvidencePreview} aria-label="판정에 사용한 식약처 허가 근거">
                                <header>
                                  <strong>
                                    {ruleEvidenceDisplay.productMatch === "all"
                                      ? "이 제품의 식약처 허가 원문"
                                      : "규칙을 승인한 대표 허가 원문"}
                                  </strong>
                                  <span>
                                    {ruleEvidenceDisplay.productMatch === "all"
                                      ? "선택 제품과 직접 일치"
                                      : ruleEvidenceDisplay.productMatch === "partial"
                                        ? "선택 제품 중 일부와 일치 · 나머지 제품과 구분"
                                        : "대표 제품 근거 · 현재 제품과 구분"}
                                  </span>
                                </header>
                                <blockquote>{primaryRuleEvidence.excerptKo}</blockquote>
                                <a href={primaryRuleEvidence.url} target="_blank" rel="noreferrer">
                                  {primaryRuleEvidence.productName} · {primaryRuleEvidence.locator}
                                </a>
                              </section>
                            )}
                            {primaryPaper ? (
                              <section className={styles.literaturePreview} aria-label="이해를 돕는 직접 연결 학술문헌">
                                <header>
                                  <strong>{literatureRelationLabel(primaryPaper.evidenceRelation)}</strong>
                                  <span>보조 근거 · 판정에는 미사용</span>
                                </header>
                                <a href={primaryPaper.url} target="_blank" rel="noreferrer">
                                  {primaryPaper.title} (PMID {primaryPaper.pmid})
                                </a>
                                <p><strong>연구 결과</strong>{primaryPaper.keyFindingKo}</p>
                                <p><strong>이 판정에 연결한 이유</strong>{primaryPaper.selectionReasonKo}</p>
                                <p><strong>적용 한계</strong>{primaryPaper.limitationKo}</p>
                                {supportingPapers.length > 1 && (
                                  <small>아래 전체 근거에서 관련 논문 {supportingPapers.length}편을 모두 볼 수 있습니다.</small>
                                )}
                              </section>
                            ) : (
                              <div className={styles.literatureEmpty}>
                                <strong>직접 연결된 학술문헌은 아직 없습니다.</strong>
                                <p>이 판정은 식약처 허가 및 제품·계산 원문을 사용했습니다. 맞지 않는 논문을 억지로 연결하지 않았습니다.</p>
                              </div>
                            )}
                            {finding.severity !== "urgent" && (
                              <div className={styles.nextAction}>
                                <span>지금 할 일</span>
                                <strong>{finding.nextActionKo}</strong>
                              </div>
                            )}
                            <details className={styles.evidenceDetails}>
                              <summary>
                                근거와 문헌 자세히 보기 · {ruleEvidence.length + finding.evidence.length}개 근거
                                {supportingPapers.length > 0 ? ` · 논문 ${supportingPapers.length}편` : ""}
                              </summary>
                              <div className={styles.evidencePanel}>
                                {ruleEvidence.length > 0 && (
                                  <section>
                                    <div className={styles.evidenceSectionTitle}>
                                      <strong>판정 규칙 근거</strong>
                                      <span>전문가 검토 후 release된 허가 원문</span>
                                    </div>
                                    {ruleEvidence.map((source) => (
                                      <a
                                        className={styles.officialEvidenceLink}
                                        key={`rule-${source.sourceId}-${source.locator}`}
                                        href={source.url}
                                        target="_blank"
                                        rel="noreferrer"
                                      >
                                        <strong>{formatEvidenceSource(source.sourceId)}</strong>
                                        <span>{source.locator}</span>
                                        <q>{source.excerptKo}</q>
                                      </a>
                                    ))}
                                  </section>
                                )}
                                <section>
                                  <div className={styles.evidenceSectionTitle}>
                                    <strong>제품·계산 원문</strong>
                                    <span>성분·함량·용법 확인에 사용</span>
                                  </div>
                                  {finding.evidence.map((source) => (
                                    <a
                                      className={styles.officialEvidenceLink}
                                      key={`${source.sourceId}-${source.locator}`}
                                      href={source.url}
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      <strong>{formatEvidenceSource(source.sourceId)}</strong>
                                      <span>{source.locator}</span>
                                    </a>
                                  ))}
                                </section>
                                {supportingPapers.length > 0 && (
                                  <section>
                                    <div className={styles.evidenceSectionTitle}>
                                      <strong>관련 학술문헌</strong>
                                      <span>이해를 돕는 보조 근거 · 판정에는 미사용</span>
                                    </div>
                                    <div className={styles.literatureList}>
                                      {supportingPapers.map((paper) => (
                                        <div className={styles.literatureCard} key={paper.pmid}>
                                          <div>
                                            <span>{paper.publicationYear} · {paper.studyDesign} · {literatureRelationLabel(paper.evidenceRelation)}</span>
                                            <b>PMID {paper.pmid}</b>
                                          </div>
                                          <a href={paper.url} target="_blank" rel="noreferrer">
                                            {paper.title}
                                          </a>
                                          <p><strong>핵심 결과</strong>{paper.keyFindingKo}</p>
                                          <p><strong>연결 이유</strong>{paper.selectionReasonKo}</p>
                                          <p><strong>적용 한계</strong>{paper.limitationKo}</p>
                                        </div>
                                      ))}
                                    </div>
                                  </section>
                                )}
                              </div>
                            </details>
                              </div>
                            </details>
                          </article>
                        );
                      })}
                    </div>
                  </>
                )}

                {evaluation.coverageGaps.length > 0 && (
                  <details className={styles.coverageDetails}>
                    <summary>
                      <span>추가로 확인할 조건</span>
                      <b>{groupedCoverageGaps.length}종류 · {evaluation.coverageGaps.length}개 제품 조건</b>
                    </summary>
                    <div>
                      <p>식약처 허가 기준이 현재 판정 규칙에 연결되지 않은 조건만 모았습니다.</p>
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
                  </details>
                )}
              </>
            )}

            {evaluation && Object.keys(evaluation.ingredientDailyTotals).length > 0 && (
              <details className={styles.totalDetails}>
                <summary>성분별 하루 입력량</summary>
                <div>
                  {Object.entries(evaluation.ingredientDailyTotals).map(
                    ([ingredientId, total]) => (
                      <p key={ingredientId}>
                        <span>{ingredientNames.get(ingredientId) ?? ingredientId}</span>
                        <strong>{formatAmount(total.amount)} {total.unit}</strong>
                      </p>
                    ),
                  )}
                </div>
              </details>
            )}
          </div>

          <footer className={styles.resultFooter}>
            <span>결정론적 규칙 {runtime.rulesReleased}개 사용</span>
            <span>블라인드 독립평가 미완료</span>
          </footer>
        </aside>
      </div>

      {selected.length > 0 && (
        <a className={styles.mobileResultLink} href="#safety-result">
          <span>선택 {selected.length}개</span>
          <strong>
            {evaluation && evaluation.inputIssues.length > 0
              ? `입력 오류 ${evaluation.inputIssues.length}개 보기`
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

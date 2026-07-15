"use client";

import { useMemo, useState } from "react";

import { evaluateOtcSafety } from "@/src/lib/otc/engine";
import { searchOtcProducts } from "@/src/lib/otc/search";
import type {
  OtcProduct,
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

export type OtcRuntime = {
  schemaVersion: string;
  generatedAt: string;
  researchDirection: string;
  releaseReady: boolean;
  rulesReleased: number;
  releasedRuleTypes: string[];
  urgentReferralBindings?: Array<{ itemSequence: string; terms: string[] }>;
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
  { key: "alcohol", label: "음주 예정" },
];

const quickChecks = [
  {
    label: "감기약 + 해열제",
    description: "아세트아미노펜 중복 확인",
    productIds: ["MFDS-196800036", "MFDS-202106092"],
  },
  {
    label: "소염진통제 2종",
    description: "NSAID 계열 중복 확인",
    productIds: ["MFDS-201110646", "MFDS-197500016"],
  },
  {
    label: "감기약 + 알레르기약",
    description: "항히스타민 중복 확인",
    productIds: ["MFDS-196800036", "MFDS-200610765"],
  },
] as const;

const initialProfile: UserProfile = { medications: [], redFlagSymptoms: [] };

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
          )
        : null,
    [
      profile,
      releasedRuleTypes,
      runtime.rulesReleased,
      runtime.urgentReferralBindings,
      selected,
    ],
  );
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

  const applyQuickCheck = (productIds: readonly string[]) => {
    setSelected(buildSelectedProducts(runtime, productIds));
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
              onClick={() => applyQuickCheck(quickCheck.productIds)}
            >
              <span>{quickCheck.label}</span>
              <small>{quickCheck.description}</small>
            </button>
          ))}
        </div>
      </div>

      <div className={styles.workspaceGrid}>
        <section className={styles.panel} aria-labelledby="medicine-heading">
          <header className={styles.panelHeader}>
            <span className={styles.panelIndex}>1</span>
            <div>
              <h2 id="medicine-heading">먹는 약 담기</h2>
              <p>제품명만 찾으면 성분과 함량을 자동으로 불러와요.</p>
            </div>
            <span className={styles.countBadge}>{selected.length}개</span>
          </header>

          <div className={styles.searchArea}>
            <label className={styles.searchBox}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m21 21-4.35-4.35m1.35-5.15A6.5 6.5 0 1 1 5 11.5a6.5 6.5 0 0 1 13 0Z" />
              </svg>
              <span className="sr-only">일반의약품 제품명 검색</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="제품명을 검색하세요"
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
              <div className={styles.productShelf} aria-label="바로 선택할 수 있는 제품">
                <span>바로 선택</span>
                <div>
                  {runtime.products.slice(0, 6).map((product) => (
                    <button
                      key={product.productId}
                      type="button"
                      onClick={() => addProduct(product)}
                      disabled={selectedIds.has(product.productId)}
                    >
                      {product.productName.replace(/\([^)]*\)/g, "")}
                      {selectedIds.has(product.productId) && <b>✓</b>}
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
                <p>함께 먹는 약을 1개 이상 담아주세요.</p>
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
                            type="number"
                            min="0"
                            step="0.5"
                            value={item.hoursSincePreviousDose ?? ""}
                            placeholder="선택"
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
                            type="number"
                            min="1"
                            step="1"
                            value={item.continuousDays ?? ""}
                            placeholder="선택"
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
                  type="number"
                  min="0"
                  max="120"
                  value={profile.ageYears ?? ""}
                  placeholder="예: 35"
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
                placeholder="예: 와파린, 수면제 (쉼표로 구분)"
              />
            </label>

            <label className={`${styles.fieldLabel} ${styles.alertField}`}>
              <span>지금 나타난 심한 증상 <small>선택</small></span>
              <textarea
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
                placeholder="예: 호흡곤란, 얼굴 부기"
              />
              <small>입력한 표현이 해당 제품의 허가상 긴급 증상과 일치할 때만 알려드려요.</small>
            </label>
          </div>
        </section>

        <aside id="safety-result" className={`${styles.panel} ${styles.resultPanel}`} aria-labelledby="result-heading" aria-live="polite">
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

                {evaluation.coverageGaps.length > 0 && (
                  <div className={styles.coverageNotice}>
                    <span aria-hidden="true">?</span>
                    <div>
                      <strong>일부 조건은 확인하지 못했어요.</strong>
                      <p>기준이 연결된 항목만 판정했습니다. 미확인 항목은 제품 포장이나 전문가에게 확인하세요.</p>
                      <ul>
                        {evaluation.coverageGaps.map((gap) => (
                          <li key={gap.gapId}>
                            <b>{gap.titleKo}</b>
                            <span>{gap.detailKo}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {orderedFindings.length === 0 &&
                  evaluation.inputIssues.length === 0 &&
                  evaluation.coverageGaps.length === 0 && (
                    <div className={styles.clearResult}>
                      <span aria-hidden="true">✓</span>
                      <div>
                        <strong>입력한 조건에서 정의된 위험 신호를 찾지 못했어요.</strong>
                        <p>안전하다는 보장은 아닙니다. 포장과 허가사항을 따르고 증상이 계속되면 전문가와 상담하세요.</p>
                      </div>
                    </div>
                  )}

                {orderedFindings.length > 0 && (
                  <>
                    <div className={styles.resultSummary} data-urgent={urgentCount > 0}>
                      <span>{urgentCount > 0 ? "먼저 확인" : "주의 확인"}</span>
                      <strong>{orderedFindings.length}개 항목이 있어요</strong>
                      <p>
                        {urgentCount > 0
                          ? `이 중 ${urgentCount}개는 즉시 확인이 필요한 항목입니다.`
                          : "아래 행동 안내와 근거를 차례로 확인하세요."}
                      </p>
                    </div>
                    <div className={styles.findings}>
                      {orderedFindings.map((finding, index) => (
                        <article key={finding.findingId} data-severity={finding.severity}>
                          <div className={styles.findingMeta}>
                            <span>{finding.severity === "urgent" ? "즉시 확인" : finding.severity === "high" ? "높은 주의" : "주의"}</span>
                            <b>{index + 1}</b>
                          </div>
                          <h3>{finding.titleKo}</h3>
                          <p>{finding.detailKo}</p>
                          <div className={styles.nextAction}>
                            <span>지금 할 일</span>
                            <strong>{finding.nextActionKo}</strong>
                          </div>
                          <details>
                            <summary>근거 원문 위치 보기</summary>
                            <div>
                              {finding.evidence.map((source) => (
                                <a
                                  key={`${source.sourceId}-${source.locator}`}
                                  href={source.url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  <span>{source.sourceId}</span>
                                  {source.locator}
                                </a>
                              ))}
                            </div>
                          </details>
                        </article>
                      ))}
                    </div>
                  </>
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
                  ? `미확인 ${evaluation.coverageGaps.length}개 보기`
                  : "점검 결과 보기"}
          </strong>
        </a>
      )}
    </div>
  );
}

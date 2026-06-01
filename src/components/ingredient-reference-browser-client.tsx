"use client";

import { useDeferredValue, useMemo, useState } from "react";

type IngredientReferenceLink = {
  label: string;
  url: string;
} | null;

type IngredientReferenceItem = {
  sourceId: string;
  title: string;
  trustSummary: string;
  year: number | null;
  jurisdiction: string | null;
  journalOrPublisher: string | null;
  primaryLink: IngredientReferenceLink;
  representativeLabel: string;
  representativeText: string | null;
  contextSummary: string | null;
  contextExcerpt: string | null;
  summaryExcerpt: string | null;
  translation: string | null;
  locatorText: string | null;
  originalFragment: string | null;
};

type IngredientReferenceBrowseItem = {
  id: string;
  nameKo: string;
  nameEn: string | null;
  category: string | null;
  aliases: string[];
  sourceCount: number;
  evidenceChunkCount: number;
  ruleCount: number;
  verifiedExcerptCount: number;
  references: IngredientReferenceItem[];
};

const controlClassName =
  "min-h-11 w-full rounded-[1rem] border border-border-subtle bg-white px-4 py-3 text-sm text-foreground outline-none transition duration-200 placeholder:text-muted hover:border-stone-300 focus:border-accent";

function formatLabel(value: string | null) {
  if (!value) return null;
  return value.replace(/_/g, " ");
}

function getReferenceSummary(reference: IngredientReferenceItem) {
  return (
    reference.summaryExcerpt ??
    reference.translation ??
    reference.representativeText ??
    "이 출처와 연결된 핵심 근거 요약이 아직 정리되지 않았습니다."
  );
}

export function IngredientReferenceBrowserClient({
  ingredients,
}: {
  ingredients: IngredientReferenceBrowseItem[];
}) {
  const [search, setSearch] = useState("");
  const [expandedIngredientId, setExpandedIngredientId] = useState<
    string | null
  >(null);
  const deferredSearch = useDeferredValue(search);

  const filteredIngredients = useMemo(() => {
    const normalized = deferredSearch.trim().toLowerCase();

    if (!normalized) {
      return ingredients;
    }

    return ingredients.filter((ingredient) =>
      [
        ingredient.nameKo,
        ingredient.nameEn ?? "",
        ingredient.category ?? "",
        ...ingredient.aliases,
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [deferredSearch, ingredients]);

  const hasExpandedIngredient = filteredIngredients.some(
    (ingredient) => ingredient.id === expandedIngredientId,
  );

  return (
    <div className="space-y-5">
      <section className="surface-card rounded-[1.8rem] px-5 py-5 md:px-6">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-foreground">영양소 검색</p>
            <span className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-sm text-foreground">
              {filteredIngredients.length}개 영양소
            </span>
          </div>

          <label className="space-y-2">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="예: 마그네슘, omega-3, saint john's wort"
              className={controlClassName}
            />
          </label>

          {hasExpandedIngredient ? (
            <p className="text-xs leading-5 text-muted">
              다른 영양소를 누르면 그 카드 안에서 바로 레퍼런스가 바뀝니다.
            </p>
          ) : null}
        </div>
      </section>

      {filteredIngredients.length === 0 ? (
        <section className="surface-card rounded-[1.8rem] px-6 py-10 text-center">
          <p className="text-lg font-semibold text-foreground">
            검색 조건에 맞는 영양소가 없습니다
          </p>
          <p className="mt-3 text-sm leading-6 text-muted">
            한글명, 영문명, 별칭 중 하나로 다시 찾아보세요.
          </p>
        </section>
      ) : (
        <div className="space-y-3">
          {filteredIngredients.map((ingredient) => {
            const isExpanded = ingredient.id === expandedIngredientId;

            return (
              <article
                key={ingredient.id}
                className="surface-card overflow-hidden rounded-[1.5rem] px-5 py-4 transition duration-200 hover:border-stone-300 hover:bg-white/92"
              >
                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        {ingredient.category ? (
                          <span className="rounded-full bg-accent-soft px-3 py-1 text-accent-strong">
                            {formatLabel(ingredient.category) ??
                              ingredient.category}
                          </span>
                        ) : null}
                        <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
                          출처 {ingredient.sourceCount}
                        </span>
                        <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
                          근거 {ingredient.evidenceChunkCount}
                        </span>
                        <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
                          검증 원문 {ingredient.verifiedExcerptCount}
                        </span>
                      </div>

                      <h3 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-foreground">
                        {ingredient.nameKo}
                      </h3>
                      {ingredient.nameEn ? (
                        <p className="mt-1 text-sm text-muted">
                          {ingredient.nameEn}
                        </p>
                      ) : null}
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        setExpandedIngredientId((current) =>
                          current === ingredient.id ? null : ingredient.id,
                        )
                      }
                      aria-expanded={isExpanded}
                      data-open={isExpanded}
                      className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white transition-[transform,background-color,box-shadow] duration-300 [transition-timing-function:var(--ease-soft)] hover:-translate-y-0.5 hover:bg-accent-strong hover:shadow-[0_10px_20px_rgba(37,70,60,0.16)]"
                    >
                      <span>{isExpanded ? "접기" : "레퍼런스 보기"}</span>
                      <svg
                        aria-hidden="true"
                        viewBox="0 0 20 20"
                        className="collapsible-chevron h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="m5 7.5 5 5 5-5" />
                      </svg>
                    </button>
                  </div>

                  <div className="collapsible-panel" data-open={isExpanded}>
                    <div className="collapsible-panel-inner">
                      <div className="collapsible-panel-body border-t border-border-subtle pt-4">
                        {ingredient.references.length === 0 ? (
                          <div className="rounded-[1.1rem] border border-dashed border-border-subtle bg-stone-50 px-4 py-5">
                            <p className="text-sm text-muted">
                              아직 정리된 레퍼런스가 없습니다.
                            </p>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {ingredient.references.map((reference) => {
                              const referenceSummary =
                                getReferenceSummary(reference);
                              const showRepresentativeText =
                                reference.representativeText &&
                                reference.representativeText !==
                                  referenceSummary;
                              const showTranslation =
                                reference.translation &&
                                reference.translation !== referenceSummary &&
                                reference.translation !==
                                  reference.representativeText;
                              const showContextExcerpt =
                                reference.contextExcerpt &&
                                reference.contextExcerpt !== referenceSummary &&
                                reference.contextExcerpt !==
                                  reference.representativeText &&
                                reference.contextExcerpt !==
                                  reference.translation;

                              return (
                                <section
                                  key={`${ingredient.id}-${reference.sourceId}`}
                                  className="rounded-[1.25rem] border border-border-subtle bg-white px-4 py-4"
                                >
                                  <div className="flex flex-col gap-4">
                                    <div className="flex flex-wrap items-center gap-2 text-[11px]">
                                      <span className="rounded-full bg-accent-soft px-2.5 py-1 text-accent-strong">
                                        {reference.trustSummary}
                                      </span>
                                      {reference.year ? (
                                        <span className="rounded-full border border-border-subtle bg-white px-2.5 py-1 text-muted">
                                          {reference.year}
                                        </span>
                                      ) : null}
                                      {reference.jurisdiction ? (
                                        <span className="rounded-full border border-border-subtle bg-white px-2.5 py-1 text-muted">
                                          {reference.jurisdiction}
                                        </span>
                                      ) : null}
                                      {reference.locatorText ? (
                                        <span className="rounded-full border border-border-subtle bg-white px-2.5 py-1 text-muted">
                                          {reference.locatorText}
                                        </span>
                                      ) : null}
                                    </div>

                                    <div>
                                      {reference.primaryLink ? (
                                        <a
                                          href={reference.primaryLink.url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="block text-base font-semibold leading-7 text-foreground underline decoration-border-subtle underline-offset-4 transition hover:text-stone-700"
                                        >
                                          {reference.title}
                                        </a>
                                      ) : (
                                        <h4 className="text-base font-semibold leading-7 text-foreground">
                                          {reference.title}
                                        </h4>
                                      )}
                                      {reference.journalOrPublisher ? (
                                        <p className="mt-1 text-sm text-muted">
                                          {reference.journalOrPublisher}
                                        </p>
                                      ) : null}
                                    </div>

                                    <div className="rounded-[1rem] border border-border-subtle bg-stone-50/75 px-4 py-4">
                                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                                        이 자료에서 중요한 내용
                                      </p>
                                      <p className="mt-2 text-sm leading-7 text-foreground">
                                        {referenceSummary}
                                      </p>
                                      {reference.locatorText ? (
                                        <p className="mt-3 text-xs leading-5 text-muted">
                                          확인 위치: {reference.locatorText}
                                        </p>
                                      ) : null}

                                      {showRepresentativeText ? (
                                        <div className="mt-3 border-t border-border-subtle pt-3">
                                          <p className="text-xs font-semibold text-muted">
                                            {reference.representativeLabel}
                                          </p>
                                          <p className="mt-1 text-sm leading-6 text-foreground">
                                            {reference.representativeText}
                                          </p>
                                        </div>
                                      ) : null}

                                      {showTranslation ? (
                                        <div className="mt-3 border-t border-border-subtle pt-3">
                                          <p className="text-xs font-semibold text-muted">
                                            한국어 번역
                                          </p>
                                          <p className="mt-1 text-sm leading-6 text-muted">
                                            {reference.translation}
                                          </p>
                                        </div>
                                      ) : null}

                                      {showContextExcerpt ? (
                                        <div className="mt-3 border-t border-border-subtle pt-3">
                                          <p className="text-xs font-semibold text-muted">
                                            앞뒤 문맥
                                          </p>
                                          <p className="mt-1 text-sm leading-6 text-muted">
                                            {reference.contextExcerpt}
                                          </p>
                                        </div>
                                      ) : null}

                                      {reference.originalFragment ? (
                                        <div className="mt-3 border-t border-border-subtle pt-3">
                                          <p className="text-xs font-semibold text-muted">
                                            레퍼런스 원문 해당 부분
                                          </p>
                                          <p className="mt-1 text-xs leading-6 text-muted">
                                            &ldquo;{reference.originalFragment}
                                            &rdquo;
                                          </p>
                                        </div>
                                      ) : null}
                                    </div>

                                    <div className="flex flex-wrap gap-2">
                                      {reference.primaryLink ? (
                                        <a
                                          href={reference.primaryLink.url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-xs font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300"
                                        >
                                          {reference.primaryLink.label}
                                        </a>
                                      ) : null}
                                    </div>
                                  </div>
                                </section>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

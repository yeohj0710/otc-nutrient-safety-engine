import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  getIngredientReferenceDetail,
  getKnowledgeIndex,
} from "@/src/lib/knowledge";
import {
  getEvidenceContextExcerpt,
  getEvidencePrimaryExcerpt,
  getEvidenceRepresentativeExcerpt,
  getEvidenceRepresentativeExcerptLabel,
  getEvidenceSummaryExcerpt,
  getEvidenceTranslationExcerpt,
  getSourceReferenceLinks,
  getSourceTrustSummary,
  hasOriginalEvidenceExcerpt,
  isShortOriginalEvidenceExcerpt,
  pickRepresentativeEvidenceChunk,
  sortEvidenceChunksByPriority,
  sortSourcesByPriority,
} from "@/src/lib/references";
import { siteName } from "@/src/lib/site";

function formatLabel(value: string | null | undefined) {
  if (!value) return null;
  return value.replace(/_/g, " ");
}

function getPreferredPrimaryLink(links: Array<{ label: string; url: string }>) {
  return (
    links.find((link) => link.label === "DOI") ??
    links.find((link) => link.label === "PDF 원문") ??
    links.find((link) => link.label === "원문/기관 페이지") ??
    links.find((link) => link.label === "PubMed") ??
    links[0] ??
    null
  );
}

export async function generateMetadata(props: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await props.params;
  const detail = getIngredientReferenceDetail(id);

  if (!detail) {
    return {
      title: `영양소를 찾을 수 없음 | ${siteName}`,
      robots: {
        index: false,
        follow: false,
      },
    };
  }

  return {
    title: `${detail.ingredient.nameKo} 레퍼런스`,
    description: `${detail.ingredient.nameKo}와 연결된 논문, 공공 자료, 근거 문장과 외부 링크를 한 페이지에서 확인합니다.`,
    robots: {
      index: false,
      follow: false,
    },
  };
}

export default async function IngredientReferenceDetailPage(props: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await props.params;
  const detail = getIngredientReferenceDetail(id);

  if (!detail) {
    notFound();
  }

  const sourceLookup = new Map(
    detail.linkedSources.map((source) => [source.id, source]),
  );
  const sortedSources = sortSourcesByPriority(detail.linkedSources);
  const sortedChunks = sortEvidenceChunksByPriority(
    detail.linkedEvidenceChunks,
    sourceLookup,
  );

  const sourceCards = sortedSources.map((source) => {
    const externalLinks = getSourceReferenceLinks(source);
    const primaryLink = getPreferredPrimaryLink(externalLinks);
    const sourceChunks = sortedChunks.filter(
      (chunk) => chunk.sourceId === source.id,
    );
    const primaryChunk =
      pickRepresentativeEvidenceChunk(sourceChunks) ?? sourceChunks[0] ?? null;
    const primaryExcerpt = primaryChunk
      ? getEvidenceRepresentativeExcerpt(primaryChunk)
      : null;
    const primaryExcerptLabel = primaryChunk
      ? getEvidenceRepresentativeExcerptLabel(primaryChunk)
      : "근거 문장";
    const translation = primaryChunk
      ? getEvidenceTranslationExcerpt(primaryChunk)
      : null;
    const contextExcerpt = primaryChunk
      ? getEvidenceContextExcerpt(primaryChunk)
      : null;
    const summaryExcerpt = primaryChunk
      ? getEvidenceSummaryExcerpt(primaryChunk)
      : null;
    const hasFullOriginalLine = primaryChunk
      ? hasOriginalEvidenceExcerpt(primaryChunk) &&
        !isShortOriginalEvidenceExcerpt(primaryChunk)
      : false;
    const originalFragment =
      primaryChunk &&
      hasOriginalEvidenceExcerpt(primaryChunk) &&
      isShortOriginalEvidenceExcerpt(primaryChunk)
        ? getEvidencePrimaryExcerpt(primaryChunk)
        : null;

    return {
      source,
      primaryLink,
      primaryExcerpt,
      primaryExcerptLabel,
      translation,
      contextExcerpt,
      summaryExcerpt,
      hasFullOriginalLine,
      originalFragment,
    };
  });

  return (
    <main className="app-page min-h-screen px-4 pb-20 pt-6 md:px-5 lg:px-6">
      <div className="page-shell-narrow space-y-6">
        <section className="surface-card-strong rounded-[2rem] px-6 py-6">
          <p className="eyebrow">Ingredient Reference Detail</p>
          <h1 className="mt-4 text-[clamp(1.62rem,2.8vw,2.18rem)] font-semibold tracking-[-0.03em] text-foreground">
            {detail.ingredient.nameKo}
          </h1>
          {detail.ingredient.nameEn ? (
            <p className="mt-2 text-sm text-muted">
              {detail.ingredient.nameEn}
            </p>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
            {detail.ingredient.category ? (
              <span className="rounded-full bg-accent-soft px-3 py-1 text-accent-strong">
                {formatLabel(detail.ingredient.category) ??
                  detail.ingredient.category}
              </span>
            ) : null}
            <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
              출처 {detail.counts.sources}
            </span>
            <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
              근거 {detail.counts.evidenceChunks}
            </span>
            <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
              검증 원문 {detail.counts.verifiedExcerpts}
            </span>
          </div>

          <p className="mt-4 max-w-[52ch] text-sm leading-7 text-muted">
            이 영양소와 연결된 레퍼런스를 한 번에 검토할 수 있도록 정리했습니다.
            제목을 누르면 실제 논문이나 기관 원문으로 바로 이동합니다.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/ingredients"
              className="inline-flex min-h-11 items-center justify-center rounded-full bg-accent px-5 py-[0.62rem] text-[0.84rem] font-medium text-white transition duration-200 hover:-translate-y-0.5 hover:bg-accent-strong"
            >
              영양소 목록으로
            </Link>
            <Link
              href="/sources"
              className="inline-flex min-h-11 items-center justify-center rounded-full border border-border-subtle bg-white px-5 py-[0.62rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300"
            >
              전체 출처 보기
            </Link>
          </div>
        </section>

        <section className="surface-card rounded-[1.8rem] px-5 py-5 md:px-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">
                연결된 레퍼런스
              </p>
              <p className="mt-1 text-sm leading-6 text-muted">
                제목, 대표 근거, 외부 링크만 먼저 보여드립니다.
              </p>
            </div>
            <span className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-sm text-foreground">
              {sourceCards.length}건
            </span>
          </div>

          {sourceCards.length === 0 ? (
            <div className="mt-5 rounded-[1.4rem] border border-dashed border-border-subtle bg-stone-50 px-5 py-8 text-center">
              <p className="text-sm text-muted">
                아직 연결된 레퍼런스가 없습니다.
              </p>
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              {sourceCards.map(
                ({
                  source,
                  primaryLink,
                  primaryExcerpt,
                  primaryExcerptLabel,
                  translation,
                  contextExcerpt,
                  summaryExcerpt,
                  hasFullOriginalLine,
                  originalFragment,
                }) => (
                  <article
                    key={source.id}
                    className="rounded-[1.5rem] border border-border-subtle bg-white px-5 py-5"
                  >
                    <div className="flex flex-col gap-4">
                      <div className="flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="rounded-full bg-accent-soft px-3 py-1 text-accent-strong">
                          {getSourceTrustSummary(source)}
                        </span>
                        {source.year ? (
                          <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
                            {source.year}
                          </span>
                        ) : null}
                        {source.jurisdiction ? (
                          <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
                            {source.jurisdiction}
                          </span>
                        ) : null}
                      </div>

                      <div>
                        {primaryLink ? (
                          <a
                            href={primaryLink.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block text-[0.98rem] font-semibold leading-7 text-foreground underline decoration-border-subtle underline-offset-4 transition hover:text-stone-700"
                          >
                            {source.title}
                          </a>
                        ) : (
                          <h2 className="text-[0.98rem] font-semibold leading-7 text-foreground">
                            {source.title}
                          </h2>
                        )}

                        <div className="mt-3 flex flex-wrap gap-2">
                          {primaryLink ? (
                            <a
                              href={primaryLink.url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-xs font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300"
                            >
                              {primaryLink.label}
                            </a>
                          ) : null}
                          <Link
                            href={`/sources/${source.id}`}
                            className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-xs font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300"
                          >
                            내부 상세
                          </Link>
                        </div>
                      </div>

                      <div className="rounded-[1.1rem] border border-border-subtle bg-stone-50/70 px-4 py-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                          {primaryExcerptLabel}
                        </p>
                        {primaryExcerpt ? (
                          hasFullOriginalLine ? (
                            <blockquote className="mt-2 text-sm leading-7 text-foreground">
                              &ldquo;{primaryExcerpt}&rdquo;
                            </blockquote>
                          ) : (
                            <p className="mt-2 text-sm leading-7 text-foreground">
                              {primaryExcerpt}
                            </p>
                          )
                        ) : (
                          <p className="mt-2 text-sm leading-6 text-muted">
                            아직 대표로 보여줄 근거 문장이 연결되지 않았습니다.
                          </p>
                        )}
                        {translation && translation !== primaryExcerpt ? (
                          <div className="mt-3 border-t border-border-subtle pt-3">
                            <p className="text-xs font-semibold text-muted">
                              한국어 번역
                            </p>
                            <p className="mt-1 text-sm leading-6 text-muted">
                              {translation}
                            </p>
                          </div>
                        ) : null}
                        {contextExcerpt ? (
                          <div className="mt-3 border-t border-border-subtle pt-3">
                            <p className="text-xs font-semibold text-muted">
                              앞뒤 문맥
                            </p>
                            <p className="mt-1 text-sm leading-6 text-muted">
                              {contextExcerpt}
                            </p>
                          </div>
                        ) : null}
                        {summaryExcerpt ? (
                          <div className="mt-3 border-t border-border-subtle pt-3">
                            <p className="text-xs font-semibold text-muted">
                              핵심 해석
                            </p>
                            <p className="mt-1 text-sm leading-6 text-muted">
                              {summaryExcerpt}
                            </p>
                          </div>
                        ) : null}
                        {originalFragment ? (
                          <div className="mt-3 border-t border-border-subtle pt-3">
                            <p className="text-xs font-semibold text-muted">
                              레퍼런스 원문 해당 부분
                            </p>
                            <p className="mt-1 text-xs leading-6 text-muted">
                              &ldquo;{originalFragment}&rdquo;
                            </p>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </article>
                ),
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

export async function generateStaticParams() {
  return getKnowledgeIndex().ingredients.map((ingredient) => ({
    id: ingredient.id,
  }));
}

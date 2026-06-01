import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getKnowledgeIndex, getSourceDetail } from "@/src/lib/knowledge";
import {
  getEvidenceCaptureLabel,
  getEvidenceCheckHint,
  getEvidenceClaimLabel,
  getEvidenceContextExcerpt,
  getEvidenceExcerptLabel,
  getEvidenceLocatorText,
  getEvidenceNote,
  getEvidencePrimaryExcerpt,
  getEvidenceSearchKeywords,
  getEvidenceSummaryExcerpt,
  getEvidenceTranslationExcerpt,
  getEvidenceVerificationLabel,
  getEvidenceVerificationSummary,
  getSourceReferenceLinks,
  getSourceTrustSummary,
  hasOriginalEvidenceExcerpt,
  sortEvidenceChunksByPriority,
} from "@/src/lib/references";
import { siteName } from "@/src/lib/site";

function formatLabel(value: string | null | undefined) {
  if (!value) return null;
  return value.replace(/_/g, " ");
}

function sortRulesByPriority<
  T extends {
    severity: string;
    priority: number;
    nutrientOrIngredient: string;
  },
>(rules: T[]) {
  const severityScore: Record<string, number> = {
    contraindicated: 4,
    avoid: 3,
    warn: 2,
    monitor: 1,
  };

  return [...rules].sort((left, right) => {
    const severityDifference =
      (severityScore[right.severity] ?? 0) -
      (severityScore[left.severity] ?? 0);

    if (severityDifference !== 0) {
      return severityDifference;
    }

    const priorityDifference = left.priority - right.priority;
    if (priorityDifference !== 0) {
      return priorityDifference;
    }

    return left.nutrientOrIngredient.localeCompare(
      right.nutrientOrIngredient,
      "ko",
    );
  });
}

export async function generateMetadata(props: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await props.params;
  const detail = getSourceDetail(id);

  if (!detail) {
    return {
      title: `출처를 찾을 수 없음 | ${siteName}`,
      robots: {
        index: false,
        follow: false,
      },
    };
  }

  return {
    title: `${detail.source.title} | 출처 상세`,
    description:
      "원문 링크, 근거 발췌, 연결된 규칙을 한 페이지에서 확인할 수 있는 출처 상세 화면입니다.",
    robots: {
      index: false,
      follow: false,
    },
  };
}

export default async function SourceDetailPage(props: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await props.params;
  const detail = getSourceDetail(id);

  if (!detail) {
    notFound();
  }

  const referenceLinks = getSourceReferenceLinks(detail.source);
  const sourceLookup = new Map([[detail.source.id, detail.source]]);
  const sortedEvidenceChunks = sortEvidenceChunksByPriority(
    detail.evidenceChunks,
    sourceLookup,
  );
  const sortedRules = sortRulesByPriority(detail.linkedRules);
  const verifiedChunkCount = sortedEvidenceChunks.filter(
    (chunk) => chunk.verificationStatus === "verified_against_source",
  ).length;
  const supportedInferenceCount = sortedEvidenceChunks.filter(
    (chunk) => chunk.verificationStatus === "supported_inference",
  ).length;
  const pendingChunkCount = sortedEvidenceChunks.filter(
    (chunk) => chunk.verificationStatus === "pending_manual_extraction",
  ).length;

  return (
    <main className="app-page min-h-screen px-4 py-8 md:px-5 lg:px-6">
      <div className="page-shell-narrow space-y-5">
        <section className="surface-card-strong rounded-[2rem] px-6 py-6">
          <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <p className="eyebrow">Source Detail</p>
              <h1 className="mt-4 font-display text-[clamp(1.68rem,2.85vw,2.5rem)] leading-[1.05] tracking-[-0.04em] text-foreground">
                {detail.source.title}
              </h1>
              <p className="mt-3 text-sm text-muted">{detail.source.id}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-900">
                  {getSourceTrustSummary(detail.source)}
                </span>
                {detail.source.year ? (
                  <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">
                    {detail.source.year}
                  </span>
                ) : null}
                {detail.source.jurisdiction ? (
                  <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">
                    {detail.source.jurisdiction}
                  </span>
                ) : null}
                {detail.source.evidenceLevel ? (
                  <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">
                    {formatLabel(detail.source.evidenceLevel) ??
                      detail.source.evidenceLevel}
                  </span>
                ) : null}
                <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">
                  {formatLabel(detail.source.sourceType) ??
                    detail.source.sourceType}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 md:justify-end">
              <Link
                href="/sources"
                className="inline-flex min-h-11 shrink-0 items-center justify-center whitespace-nowrap rounded-full border border-border-subtle bg-white/82 px-5 py-[0.58rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300 hover:bg-white"
              >
                출처 목록
              </Link>
              <Link
                href="/"
                className="inline-flex min-h-11 shrink-0 items-center justify-center whitespace-nowrap rounded-full border border-border-subtle bg-white/82 px-5 py-[0.58rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300 hover:bg-white"
              >
                메인 안내
              </Link>
            </div>
          </div>

          <div className="mt-6 grid gap-3 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <div className="rounded-[1.5rem] border border-border-subtle bg-white/76 p-4">
              <p className="text-sm font-semibold text-stone-900">
                원문 먼저 확인해 보세요
              </p>
              <p className="mt-2 text-sm leading-6 text-stone-600">
                가능한 경우 원문 링크를 먼저 보여드립니다. 바로 아래 버튼으로
                PubMed, DOI, 기관 원문 페이지를 열어 직접 확인하실 수 있습니다.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {referenceLinks.length > 0 ? (
                  referenceLinks.map((link) => (
                    <a
                      key={`${link.label}-${link.url}`}
                      href={link.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-full border border-stone-200 bg-white px-4 py-[0.58rem] text-[0.84rem] font-medium text-stone-700 transition hover:-translate-y-0.5 hover:border-stone-300 hover:text-stone-950"
                    >
                      {link.label}
                    </a>
                  ))
                ) : (
                  <span className="text-sm text-stone-500">
                    연결된 원문 링크 정보가 아직 없습니다.
                  </span>
                )}
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-border-subtle bg-white/76 p-4">
              <dl className="grid gap-3 text-sm">
                <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3">
                  <dt className="text-stone-500">발행기관</dt>
                  <dd className="font-medium text-stone-900">
                    {detail.source.journalOrPublisher ??
                      "발행기관 정보가 없습니다."}
                  </dd>
                </div>
                <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3">
                  <dt className="text-stone-500">업데이트</dt>
                  <dd className="text-stone-800">
                    {detail.source.updatedAt ?? "등록 정보 없음"}
                  </dd>
                </div>
                <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3">
                  <dt className="text-stone-500">연결 규칙</dt>
                  <dd className="text-stone-800">{sortedRules.length}건</dd>
                </div>
                <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3">
                  <dt className="text-stone-500">근거 발췌</dt>
                  <dd className="text-stone-800">
                    {sortedEvidenceChunks.length}건
                  </dd>
                </div>
                <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3">
                  <dt className="text-stone-500">원문 상태</dt>
                  <dd className="text-stone-800">
                    확인 {verifiedChunkCount} / 해석 {supportedInferenceCount} /
                    대기 {pendingChunkCount}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        </section>

        <section className="rounded-[2rem] border border-stone-200 bg-white p-6 shadow-[0_16px_34px_rgba(28,25,23,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-[1.18rem] font-semibold text-stone-950">
                원문 발췌와 확인 포인트
              </h2>
              <p className="mt-1 text-sm leading-6 text-stone-600">
                요약보다 원문 발췌를 우선 보여드립니다. 원문 그대로의 문장이
                없는 항목은 등록된 발췌와 직접 확인 위치를 함께 안내합니다.
              </p>
            </div>
            <span className="rounded-full bg-stone-100 px-3 py-1 text-sm text-stone-700">
              {sortedEvidenceChunks.length}건
            </span>
          </div>

          {sortedEvidenceChunks.length === 0 ? (
            <div className="mt-5 rounded-[1.5rem] border border-dashed border-stone-300 bg-stone-50 px-5 py-8 text-center">
              <p className="text-sm text-stone-600">
                아직 연결된 근거 발췌가 없습니다.
              </p>
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              {sortedEvidenceChunks.map((chunk) => {
                const primaryExcerpt = getEvidencePrimaryExcerpt(chunk);
                const translationExcerpt = getEvidenceTranslationExcerpt(chunk);
                const contextExcerpt = getEvidenceContextExcerpt(chunk);
                const summaryExcerpt = getEvidenceSummaryExcerpt(chunk);
                const searchKeywords = getEvidenceSearchKeywords(chunk);
                const claimLabel = getEvidenceClaimLabel(chunk);
                const locatorText = getEvidenceLocatorText(chunk);
                const evidenceNote = getEvidenceNote(chunk);
                const verificationLabel = getEvidenceVerificationLabel(chunk);
                const captureLabel = getEvidenceCaptureLabel(chunk);
                const verificationSummary =
                  getEvidenceVerificationSummary(chunk);

                return (
                  <article
                    key={chunk.id}
                    className="rounded-[1.6rem] border border-stone-200 bg-stone-50/70 p-5"
                  >
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap gap-2 text-[11px]">
                          {verificationLabel ? (
                            <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-900">
                              {verificationLabel}
                            </span>
                          ) : null}
                          {captureLabel ? (
                            <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-stone-700">
                              {captureLabel}
                            </span>
                          ) : null}
                          <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-stone-700">
                            {getEvidenceExcerptLabel(chunk)}
                          </span>
                          {claimLabel ? (
                            <span className="rounded-full bg-stone-900 px-3 py-1 text-white">
                              {claimLabel}
                            </span>
                          ) : null}
                          {locatorText ? (
                            <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">
                              {locatorText}
                            </span>
                          ) : null}
                          {chunk.usedInRuleIds.length > 0 ? (
                            <span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">
                              linked rules {chunk.usedInRuleIds.length}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-3 text-sm font-semibold text-stone-900">
                          {chunk.id}
                        </p>
                      </div>

                      {referenceLinks.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {referenceLinks.map((link) => (
                            <a
                              key={`${chunk.id}-${link.label}-${link.url}`}
                              href={link.url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-stone-700 transition hover:-translate-y-0.5 hover:border-stone-300 hover:text-stone-950"
                            >
                              {link.label}
                            </a>
                          ))}
                        </div>
                      ) : null}
                    </div>

                    <div className="mt-4 rounded-[1.35rem] border border-stone-200 bg-white p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-500">
                        {getEvidenceExcerptLabel(chunk)}
                      </p>
                      <blockquote className="mt-3 text-[0.97rem] leading-7 text-stone-950 md:text-[1rem]">
                        {primaryExcerpt ?? "등록된 발췌 문장이 아직 없습니다."}
                      </blockquote>

                      {translationExcerpt &&
                      translationExcerpt !== primaryExcerpt ? (
                        <div className="mt-4 rounded-xl bg-stone-50 px-4 py-3">
                          <p className="text-xs font-semibold text-stone-500">
                            한국어 번역
                          </p>
                          <p className="mt-2 text-sm leading-6 text-stone-700">
                            {translationExcerpt}
                          </p>
                        </div>
                      ) : null}

                      {contextExcerpt ? (
                        <div className="mt-4 rounded-xl bg-stone-50 px-4 py-3">
                          <p className="text-xs font-semibold text-stone-500">
                            앞뒤 문맥
                          </p>
                          <p className="mt-2 text-sm leading-6 text-stone-700">
                            {contextExcerpt}
                          </p>
                        </div>
                      ) : null}

                      {summaryExcerpt ? (
                        <div className="mt-4 rounded-xl bg-stone-50 px-4 py-3">
                          <p className="text-xs font-semibold text-stone-500">
                            핵심 해석
                          </p>
                          <p className="mt-2 text-sm leading-6 text-stone-700">
                            {summaryExcerpt}
                          </p>
                        </div>
                      ) : null}

                      <div className="mt-4 rounded-xl bg-stone-50 px-4 py-3">
                        <p className="text-xs font-semibold text-stone-500">
                          검증 상태
                        </p>
                        <p className="mt-2 text-sm leading-6 text-stone-700">
                          {verificationSummary}
                        </p>
                      </div>

                      {evidenceNote ? (
                        <div className="mt-4 rounded-xl bg-stone-50 px-4 py-3">
                          <p className="text-xs font-semibold text-stone-500">
                            메모
                          </p>
                          <p className="mt-2 text-sm leading-6 text-stone-700">
                            {evidenceNote}
                          </p>
                        </div>
                      ) : null}

                      {!hasOriginalEvidenceExcerpt(chunk) ? (
                        <p className="mt-4 text-xs leading-5 text-stone-500">
                          현재 이 항목은 원문 그대로의 문장 대신, 출처를
                          바탕으로 등록된 발췌가 저장되어 있습니다. 아래 위치
                          안내와 원문 링크를 함께 확인해 주세요.
                        </p>
                      ) : null}
                    </div>

                    <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                      <div className="rounded-[1.2rem] border border-stone-200 bg-white p-4">
                        <p className="text-sm font-semibold text-stone-900">
                          어디를 보면 되나요?
                        </p>
                        <p className="mt-2 text-sm leading-6 text-stone-700">
                          {getEvidenceCheckHint(chunk, detail.source)}
                        </p>
                      </div>

                      <div className="rounded-[1.2rem] border border-stone-200 bg-white p-4">
                        <p className="text-sm font-semibold text-stone-900">
                          직접 찾을 때 도움이 되는 키워드
                        </p>
                        {searchKeywords.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {searchKeywords.map((keyword) => (
                              <span
                                key={`${chunk.id}-${keyword}`}
                                className="rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-700"
                              >
                                {keyword}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="mt-2 text-sm text-stone-500">
                            아직 추천 키워드가 등록되지 않았습니다.
                          </p>
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="rounded-[2rem] border border-stone-200 bg-white p-6 shadow-[0_16px_34px_rgba(28,25,23,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-[1.18rem] font-semibold text-stone-950">
                이 출처와 연결된 규칙
              </h2>
              <p className="mt-1 text-sm leading-6 text-stone-600">
                이 자료가 실제 어떤 안전성 안내에 연결돼 있는지 함께 볼 수
                있습니다.
              </p>
            </div>
            <span className="rounded-full bg-stone-100 px-3 py-1 text-sm text-stone-700">
              {sortedRules.length}건
            </span>
          </div>

          {sortedRules.length === 0 ? (
            <div className="mt-5 rounded-[1.5rem] border border-dashed border-stone-300 bg-stone-50 px-5 py-8 text-center">
              <p className="text-sm text-stone-600">
                연결된 규칙이 아직 없습니다.
              </p>
            </div>
          ) : (
            <div className="mt-5 grid gap-3">
              {sortedRules.map((rule) => (
                <article
                  key={rule.id}
                  className="rounded-[1.4rem] border border-stone-200 bg-stone-50/60 p-4"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <p className="text-[1rem] font-semibold text-stone-950">
                        {rule.nutrientOrIngredient}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-stone-700">
                        {rule.action || rule.messageShort}
                      </p>
                      <p className="mt-2 text-xs text-stone-500">{rule.id}</p>
                    </div>

                    <Link
                      href={`/rules/${rule.id}`}
                      className="rounded-full border border-stone-200 bg-white px-4 py-[0.58rem] text-[0.84rem] font-medium text-stone-700 transition hover:-translate-y-0.5 hover:border-stone-300 hover:text-stone-950"
                    >
                      규칙 상세
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

export async function generateStaticParams() {
  return getKnowledgeIndex().sources.map((source) => ({ id: source.id }));
}

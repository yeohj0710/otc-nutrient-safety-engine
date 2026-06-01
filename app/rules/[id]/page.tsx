import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { RuleCard } from "@/src/components/rule-card";
import { getKnowledgeIndex, getRuleDetail } from "@/src/lib/knowledge";
import {
  getEvidenceCaptureLabel,
  getEvidenceContextExcerpt,
  getEvidenceExcerptLabel,
  getEvidenceLocatorText,
  getEvidenceNote,
  getEvidencePrimaryExcerpt,
  getEvidenceSummaryExcerpt,
  getEvidenceTranslationExcerpt,
  getEvidenceVerificationLabel,
  getEvidenceVerificationSummary,
  getSourceReferenceLinks,
  hasOriginalEvidenceExcerpt,
} from "@/src/lib/references";
import { siteName } from "@/src/lib/site";

export async function generateMetadata(props: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await props.params;
  const detail = getRuleDetail(id);

  if (!detail) {
    return {
      title: `규칙을 찾을 수 없음 | ${siteName}`,
      robots: {
        index: false,
        follow: false,
      },
    };
  }

  return {
    title: `${detail.rule.nutrientOrIngredient} 안전 안내`,
    description: detail.rule.action || detail.rule.messageShort,
    alternates: {
      canonical: `/rules/${detail.rule.id}`,
    },
    openGraph: {
      title: `${detail.rule.nutrientOrIngredient} 안전 안내`,
      description: detail.rule.action || detail.rule.messageShort,
      url: `/rules/${detail.rule.id}`,
    },
  };
}

export default async function RuleDetailPage(props: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await props.params;
  const detail = getRuleDetail(id);

  if (!detail) {
    notFound();
  }

  const sourceLookup = new Map(
    detail.supportingSources.map((source) => [source.id, source]),
  );
  const mockMatch = {
    ruleId: detail.rule.id,
    classification: "possibly_relevant" as const,
    matched: false,
    matchScore: 0.6,
    matchedBecause: [
      "규칙 상세 페이지에서 근거와 조건을 직접 검토할 수 있습니다.",
    ],
    notEvaluatedBecauseMissing: [],
    needsMoreInfo: [],
    resolvedSeverity: detail.rule.severity,
    resolvedMessage: detail.rule.messageShort,
    supportingSources: detail.supportingSources,
    supportingEvidenceChunks: detail.supportingEvidenceChunks,
    rule: detail.rule,
    ingredient: detail.ingredient,
    evaluation: {
      selectedIngredient: true,
      conditionResults: [],
      missingFields: [],
      excludedReasons: [],
    },
  };

  return (
    <main className="app-page min-h-screen px-4 py-8 md:px-6 lg:px-6">
      <div className="page-shell-narrow space-y-6">
        <div className="surface-card-strong flex flex-col gap-5 rounded-[2rem] px-6 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="eyebrow">Rule Detail</p>
            <h1 className="mt-4 font-display text-[clamp(1.68rem,2.9vw,2.45rem)] leading-[1.05] tracking-[-0.04em] text-foreground">
              {detail.rule.nutrientOrIngredient}
            </h1>
            <p className="mt-3 text-sm text-muted">{detail.rule.id}</p>
          </div>
          <Link
            href="/"
            className="inline-flex min-h-11 items-center justify-center rounded-full border border-border-subtle bg-white/82 px-4 py-[0.58rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300 hover:bg-white"
          >
            메인 탐색으로 돌아가기
          </Link>
        </div>

        <RuleCard match={mockMatch} defaultExpandedEvidence />

        <section className="surface-card rounded-[2rem] p-6">
          <h2 className="font-display text-[1.18rem] tracking-[-0.03em] text-foreground">
            규칙 조건
          </h2>
          {detail.rule.conditions.length === 0 ? (
            <p className="mt-4 text-sm text-stone-600">
              명시적 조건이 없는 일반 참고 규칙입니다.
            </p>
          ) : (
            <ul className="mt-4 space-y-3 text-sm text-stone-700">
              {detail.rule.conditions.map((condition) => (
                <li
                  key={condition.id}
                  className="rounded-2xl bg-stone-50 px-4 py-3"
                >
                  <span className="font-medium text-stone-900">
                    {condition.labelKo ?? condition.field}
                  </span>
                  <span className="ml-2">
                    {JSON.stringify(condition.value)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="surface-card rounded-[2rem] p-6">
          <h2 className="font-display text-[1.18rem] tracking-[-0.03em] text-foreground">
            규칙 결과
          </h2>
          <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2">
            <div>
              <dt className="font-semibold text-stone-900">짧은 안내</dt>
              <dd className="mt-1 text-stone-700">
                {detail.rule.messageShort}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-stone-900">권장 조치</dt>
              <dd className="mt-1 text-stone-700">{detail.rule.action}</dd>
            </div>
            <div className="md:col-span-2">
              <dt className="font-semibold text-stone-900">상세 설명</dt>
              <dd className="mt-1 text-stone-700">{detail.rule.messageLong}</dd>
            </div>
          </dl>
        </section>

        <section className="surface-card rounded-[2rem] p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-[1.18rem] tracking-[-0.03em] text-foreground">
              지원 출처
            </h2>
            <span className="rounded-full border border-border-subtle bg-white/82 px-3 py-1 text-sm text-muted">
              {detail.supportingSources.length}건
            </span>
          </div>
          {detail.supportingSources.length === 0 ? (
            <p className="mt-4 text-sm text-stone-600">
              연결된 출처가 없습니다.
            </p>
          ) : (
            <div className="mt-4 grid gap-3">
              {detail.supportingSources.map((source) => (
                <article
                  key={source.id}
                  className="rounded-2xl border border-border-subtle bg-white/72 p-4"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="font-semibold text-stone-950">
                        {source.title}
                      </p>
                      <p className="mt-1 text-sm text-stone-700">
                        {source.journalOrPublisher ?? "발행 정보 없음"}
                      </p>
                      <p className="mt-2 text-xs text-stone-500">{source.id}</p>
                    </div>
                    <Link
                      href={`/sources/${source.id}`}
                      className="rounded-full border border-border-subtle px-4 py-2 text-sm text-foreground"
                    >
                      출처 상세
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="surface-card rounded-[2rem] p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-[1.18rem] tracking-[-0.03em] text-foreground">
              지원 근거
            </h2>
            <span className="rounded-full border border-border-subtle bg-white/82 px-3 py-1 text-sm text-muted">
              {detail.supportingEvidenceChunks.length}건
            </span>
          </div>
          {detail.supportingEvidenceChunks.length === 0 ? (
            <p className="mt-4 text-sm text-stone-600">
              연결된 근거가 없습니다.
            </p>
          ) : (
            <div className="mt-4 space-y-3">
              {detail.supportingEvidenceChunks.map((chunk) => {
                const source = sourceLookup.get(chunk.sourceId) ?? null;
                const sourceLinks = source
                  ? getSourceReferenceLinks(source)
                  : [];
                const primaryExcerpt = getEvidencePrimaryExcerpt(chunk);
                const translationExcerpt = getEvidenceTranslationExcerpt(chunk);
                const contextExcerpt = getEvidenceContextExcerpt(chunk);
                const summaryExcerpt = getEvidenceSummaryExcerpt(chunk);
                const evidenceNote = getEvidenceNote(chunk);
                const verificationLabel = getEvidenceVerificationLabel(chunk);
                const captureLabel = getEvidenceCaptureLabel(chunk);
                const locatorText = getEvidenceLocatorText(chunk);

                return (
                  <article
                    key={chunk.id}
                    className="rounded-2xl border border-stone-200 p-4"
                  >
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div>
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
                          {locatorText ? (
                            <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-stone-700">
                              {locatorText}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-3 font-semibold text-stone-950">
                          {chunk.id}
                        </p>
                        {source ? (
                          <p className="mt-1 text-sm text-stone-600">
                            {source.title}
                          </p>
                        ) : null}
                      </div>

                      {sourceLinks.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {sourceLinks.map((link) => (
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

                    <div className="mt-3 rounded-2xl bg-stone-50 px-4 py-3">
                      <p className="text-xs font-semibold text-stone-500">
                        {getEvidenceExcerptLabel(chunk)}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-stone-700">
                        {primaryExcerpt
                          ? hasOriginalEvidenceExcerpt(chunk)
                            ? `"${primaryExcerpt}"`
                            : primaryExcerpt
                          : "발췌 내용이 아직 없습니다."}
                      </p>
                      {translationExcerpt &&
                      translationExcerpt !== primaryExcerpt ? (
                        <div className="mt-3">
                          <p className="text-xs font-semibold text-stone-500">
                            한국어 번역
                          </p>
                          <p className="mt-1 text-sm leading-6 text-stone-600">
                            {translationExcerpt}
                          </p>
                        </div>
                      ) : null}
                      {contextExcerpt ? (
                        <div className="mt-3">
                          <p className="text-xs font-semibold text-stone-500">
                            앞뒤 문맥
                          </p>
                          <p className="mt-1 text-sm leading-6 text-stone-600">
                            {contextExcerpt}
                          </p>
                        </div>
                      ) : null}
                      {summaryExcerpt ? (
                        <div className="mt-3">
                          <p className="text-xs font-semibold text-stone-500">
                            핵심 해석
                          </p>
                          <p className="mt-1 text-sm leading-6 text-stone-600">
                            {summaryExcerpt}
                          </p>
                        </div>
                      ) : null}
                    </div>

                    <p className="mt-3 text-sm leading-6 text-stone-700">
                      {getEvidenceVerificationSummary(chunk)}
                    </p>
                    {evidenceNote ? (
                      <p className="mt-2 text-sm leading-6 text-stone-600">
                        {evidenceNote}
                      </p>
                    ) : null}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

export async function generateStaticParams() {
  return getKnowledgeIndex().safetyRules.map((rule) => ({ id: rule.id }));
}

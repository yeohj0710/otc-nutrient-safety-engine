"use client";

import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";

type SourceBrowseItem = {
  id: string;
  title: string;
  sourceType: string;
  year: number | null;
  jurisdiction: string | null;
  evidenceLevel: string | null;
  journalOrPublisher: string | null;
  linkedRuleCount: number;
  linkedChunkCount: number;
};

const controlClassName =
  "min-h-11 w-full rounded-[1rem] border border-border-subtle bg-white px-4 py-3 text-sm text-foreground outline-none transition duration-200 placeholder:text-muted hover:border-stone-300 focus:border-accent";

function formatLabel(value: string | null) {
  if (!value) return null;
  return value.replace(/_/g, " ");
}

function formatCount(value: number) {
  return value.toLocaleString("ko-KR");
}

function getSearchScore(source: SourceBrowseItem, normalizedSearch: string) {
  if (!normalizedSearch) return 0;

  const title = source.title.toLowerCase();
  const id = source.id.toLowerCase();
  const publisher = (source.journalOrPublisher ?? "").toLowerCase();
  const sourceType = source.sourceType.toLowerCase();

  let score = 0;

  if (title.includes(normalizedSearch)) score += 5;
  if (id.includes(normalizedSearch)) score += 4;
  if (publisher.includes(normalizedSearch)) score += 2;
  if (sourceType.includes(normalizedSearch)) score += 1;

  if (title.startsWith(normalizedSearch)) score += 2;
  if (id.startsWith(normalizedSearch)) score += 1;

  return score;
}

export function SourceBrowserClient({
  sources,
  jurisdictions,
  evidenceLevels,
}: {
  sources: SourceBrowseItem[];
  jurisdictions: string[];
  evidenceLevels: string[];
}) {
  const [search, setSearch] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [evidenceLevel, setEvidenceLevel] = useState("");
  const deferredSearch = useDeferredValue(search);

  const normalizedSearch = deferredSearch.trim().toLowerCase();

  const filteredSources = useMemo(() => {
    return sources
      .filter((source) => {
        if (jurisdiction && source.jurisdiction !== jurisdiction) {
          return false;
        }

        if (evidenceLevel && source.evidenceLevel !== evidenceLevel) {
          return false;
        }

        if (!normalizedSearch) {
          return true;
        }

        return [
          source.title,
          source.id,
          source.sourceType,
          source.journalOrPublisher ?? "",
          source.evidenceLevel ?? "",
          source.jurisdiction ?? "",
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalizedSearch);
      })
      .sort((left, right) => {
        const scoreDifference =
          getSearchScore(right, normalizedSearch) -
          getSearchScore(left, normalizedSearch);

        if (scoreDifference !== 0) return scoreDifference;
        if (right.linkedRuleCount !== left.linkedRuleCount) {
          return right.linkedRuleCount - left.linkedRuleCount;
        }
        if (right.linkedChunkCount !== left.linkedChunkCount) {
          return right.linkedChunkCount - left.linkedChunkCount;
        }
        if ((right.year ?? 0) !== (left.year ?? 0)) {
          return (right.year ?? 0) - (left.year ?? 0);
        }

        return left.title.localeCompare(right.title, "ko");
      });
  }, [evidenceLevel, jurisdiction, normalizedSearch, sources]);

  const hasFilters = Boolean(search || jurisdiction || evidenceLevel);

  const visibleLinkedRuleCount = useMemo(
    () =>
      filteredSources.reduce((sum, source) => sum + source.linkedRuleCount, 0),
    [filteredSources],
  );

  const visibleLinkedChunkCount = useMemo(
    () =>
      filteredSources.reduce((sum, source) => sum + source.linkedChunkCount, 0),
    [filteredSources],
  );

  return (
    <div className="flex flex-col gap-4">
      <section className="surface-card rounded-[1.15rem] px-4 py-4">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold tracking-[-0.02em] text-foreground">
                출처 검색
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                제목, 출처 ID, 발행 기관으로 바로 좁혀 보고 필요한 출처만
                확인하세요.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-sm font-medium text-foreground">
                결과 {formatCount(filteredSources.length)}건
              </span>
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setJurisdiction("");
                  setEvidenceLevel("");
                }}
                disabled={!hasFilters}
                className="inline-flex min-h-10 items-center justify-center rounded-full border border-border-subtle bg-white px-4 py-2 text-sm font-medium text-foreground transition duration-200 hover:border-stone-300 disabled:opacity-50"
              >
                필터 초기화
              </button>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1.5fr)_12rem_14rem]">
            <label className="space-y-2">
              <span className="text-sm font-semibold text-foreground">
                출처 검색어
              </span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="예: probiotic, FDA, SRC-US"
                className={controlClassName}
              />
            </label>

            <label className="space-y-2">
              <span className="text-sm font-semibold text-foreground">
                관할권
              </span>
              <select
                value={jurisdiction}
                onChange={(event) => setJurisdiction(event.target.value)}
                className={controlClassName}
              >
                <option value="">전체</option>
                {jurisdictions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-sm font-semibold text-foreground">
                근거 수준
              </span>
              <select
                value={evidenceLevel}
                onChange={(event) => setEvidenceLevel(event.target.value)}
                className={controlClassName}
              >
                <option value="">전체</option>
                {evidenceLevels.map((item) => (
                  <option key={item} value={item}>
                    {formatLabel(item) ?? item}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-[1rem] border border-border-subtle bg-white px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
                현재 보이는 출처
              </p>
              <p className="mt-2 text-lg font-semibold tracking-[-0.02em] text-foreground">
                {formatCount(filteredSources.length)}건
              </p>
            </div>

            <div className="rounded-[1rem] border border-border-subtle bg-white px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
                연결 규칙
              </p>
              <p className="mt-2 text-lg font-semibold tracking-[-0.02em] text-foreground">
                {formatCount(visibleLinkedRuleCount)}건
              </p>
            </div>

            <div className="rounded-[1rem] border border-border-subtle bg-white px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
                근거 청크
              </p>
              <p className="mt-2 text-lg font-semibold tracking-[-0.02em] text-foreground">
                {formatCount(visibleLinkedChunkCount)}건
              </p>
            </div>
          </div>
        </div>
      </section>

      {filteredSources.length === 0 ? (
        <section className="surface-card rounded-[1.15rem] px-6 py-8">
          <h3 className="text-base font-semibold tracking-[-0.02em] text-foreground">
            조건에 맞는 출처가 없습니다
          </h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
            검색어를 더 짧게 입력하거나 관할권, 근거 수준 필터를 풀면 더 많은
            출처를 확인할 수 있습니다.
          </p>
        </section>
      ) : (
        <div className="grid gap-3">
          {filteredSources.map((source) => (
            <article
              key={source.id}
              className="surface-card rounded-[1.15rem] px-4 py-4 transition duration-200 hover:border-stone-300 hover:bg-white/92"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    {source.evidenceLevel ? (
                      <span className="rounded-full bg-accent-soft px-3 py-1 text-accent-strong">
                        {formatLabel(source.evidenceLevel) ??
                          source.evidenceLevel}
                      </span>
                    ) : null}
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
                    <span className="rounded-full border border-border-subtle bg-white px-3 py-1 text-muted">
                      {formatLabel(source.sourceType) ?? source.sourceType}
                    </span>
                  </div>

                  <div className="mt-3">
                    <Link
                      href={`/sources/${source.id}`}
                      className="block text-base font-semibold leading-7 tracking-[-0.02em] text-foreground underline decoration-border-subtle underline-offset-4 transition hover:text-stone-700"
                    >
                      {source.title}
                    </Link>
                    <p className="mt-1 text-sm leading-6 text-muted">
                      {source.journalOrPublisher ??
                        "발행 기관 정보가 아직 없습니다."}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-muted">
                      출처 ID: {source.id}
                    </p>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    <div className="rounded-[0.95rem] border border-border-subtle bg-white px-3.5 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
                        연결 규칙
                      </p>
                      <p className="mt-1 text-sm font-semibold text-foreground">
                        {formatCount(source.linkedRuleCount)}건
                      </p>
                    </div>

                    <div className="rounded-[0.95rem] border border-border-subtle bg-white px-3.5 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
                        근거 청크
                      </p>
                      <p className="mt-1 text-sm font-semibold text-foreground">
                        {formatCount(source.linkedChunkCount)}건
                      </p>
                    </div>

                    <div className="rounded-[0.95rem] border border-border-subtle bg-white px-3.5 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
                        우선 확인
                      </p>
                      <p className="mt-1 text-sm text-foreground">
                        {source.linkedRuleCount > 0
                          ? "연결 규칙부터 확인"
                          : "출처 상세에서 원문 확인"}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex shrink-0 items-start">
                  <Link
                    href={`/sources/${source.id}`}
                    className="inline-flex min-h-10 items-center justify-center rounded-full border border-border-subtle bg-white px-4 py-2 text-sm font-semibold text-foreground transition duration-200 hover:border-stone-300"
                  >
                    출처 상세
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

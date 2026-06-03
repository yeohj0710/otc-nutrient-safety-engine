import Link from "next/link";
import type { Metadata } from "next";

import literatureCandidateData from "@/src/generated/literature-candidates.json";
import { RuleExplorerClient } from "@/src/components/rule-explorer-client";
import { getExplorerMetadata } from "@/src/lib/knowledge";
import { siteDescription, siteName } from "@/src/lib/site";

export const metadata: Metadata = {
  title: siteName,
  description: siteDescription,
  alternates: {
    canonical: "/",
  },
};

function formatCount(value: number) {
  return value.toLocaleString("ko-KR");
}

export default function Home() {
  const metadata = getExplorerMetadata();
  const literatureSummary = literatureCandidateData.summary;
  const scopeItems = [
    {
      label: "PubMed 검색 적중",
      value: formatCount(literatureSummary.latestPubMedHitCount),
      note: `저장 ${formatCount(literatureSummary.latestPubMedStoredRecords)}건`,
    },
    {
      label: "보조검색 적중",
      value: formatCount(literatureSummary.secondaryHitTotal),
      note: `저장 ${formatCount(literatureSummary.secondaryStoredRecords)}건`,
    },
    {
      label: "우선검토 후보문헌",
      value: formatCount(literatureSummary.priorityCandidateCount),
      note: `누적 후보 ${formatCount(literatureSummary.cumulativePubMedCandidates)}건`,
    },
    {
      label: "직접 판정 규칙",
      value: formatCount(metadata.meta.safetyRuleCount),
      note: `근거 출처 ${formatCount(metadata.meta.sourceCount)}개`,
    },
  ];

  return (
    <main className="app-page min-h-screen px-4 py-4 sm:px-6 lg:px-6">
      <div className="page-shell flex flex-col gap-4">
        <section className="surface-card rounded-[1.15rem] px-4 py-4">
          <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-6">
            <div className="min-w-0">
              <h1 className="text-[0.96rem] font-semibold tracking-[-0.02em] text-foreground">
                {siteName}
              </h1>
              <p className="mt-1 text-sm leading-6 text-muted">
                {siteDescription}
              </p>
            </div>

            <div className="flex flex-col gap-2 lg:relative lg:min-w-[13rem] lg:items-end lg:justify-center">
              <Link
                href="/sources"
                className="text-[0.84rem] font-medium text-muted underline decoration-border-subtle underline-offset-4 transition duration-200 hover:text-foreground lg:absolute lg:right-0 lg:top-0"
              >
                출처 보기
              </Link>

              <div className="lg:flex lg:min-h-[5.75rem] lg:items-center lg:justify-end">
                <Link
                  href="/ingredients"
                  className="inline-flex min-h-10 items-center justify-center rounded-full border border-border-subtle bg-white px-4 py-[0.58rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:border-stone-300"
                >
                  영양소별 레퍼런스
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="surface-card rounded-[1.15rem] px-4 py-4">
          <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,0.86fr)_minmax(0,1.14fr)] lg:items-start lg:gap-6">
            <div>
              <p className="text-[0.76rem] font-semibold uppercase text-muted">
                연구 범위
              </p>
              <h2 className="mt-1 text-[0.96rem] font-semibold text-foreground">
                검색량과 판정 결과를 나누어 봅니다
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                문헌 검색은 넓게 수행하고, 화면에는 현재 입력값에 맞는
                직접 판정 규칙과 관련 후보문헌을 함께 표시합니다.
              </p>
            </div>

            <dl className="grid grid-cols-2 border-t border-border-subtle text-sm lg:grid-cols-4 lg:border-t-0">
              {scopeItems.map((item, index) => (
                <div
                  key={item.label}
                  className={`min-w-0 border-t border-border-subtle py-3 first:border-t-0 lg:border-l lg:border-t-0 lg:px-4 lg:first:border-l-0 ${
                    index % 2 === 1 ? "pl-4" : "pr-4"
                  }`}
                >
                  <dt className="text-[0.74rem] font-medium text-muted">
                    {item.label}
                  </dt>
                  <dd className="mt-1 text-[1.12rem] font-semibold text-foreground">
                    {item.value}
                  </dd>
                  <dd className="mt-1 text-[0.76rem] leading-5 text-muted">
                    {item.note}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section id="explorer" className="scroll-mt-6">
          <RuleExplorerClient metadata={metadata} />
        </section>
      </div>
    </main>
  );
}

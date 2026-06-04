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
  const lookupRows = [
    {
      ingredient: "Vitamin D + calcium",
      threshold: "4,000 IU/day 기준",
      cue: "hypercalcemia, kidney stone",
    },
    {
      ingredient: "Vitamin B6",
      threshold: "50 mg/day 이상",
      cue: "neuropathy, long-term use",
    },
    {
      ingredient: "Mineral stack",
      threshold: "iron, zinc, magnesium",
      cue: "GI effect, absorption timing",
    },
  ];
  const scopeItems = [
    {
      label: "PubMed/MEDLINE",
      value: formatCount(literatureSummary.latestPubMedHitCount),
      note: `저장 ${formatCount(literatureSummary.latestPubMedStoredRecords)}건`,
    },
    {
      label: "보조 검색원",
      value: formatCount(literatureSummary.secondaryHitTotal),
      note: `대조 record ${formatCount(literatureSummary.secondaryStoredRecords)}건`,
    },
    {
      label: "화면 후보문헌",
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
    <main className="app-page min-h-screen px-4 py-4 sm:px-6 lg:px-8">
      <div className="mx-auto grid w-full max-w-6xl gap-4">
        <section className="surface-card rounded-[0.8rem] px-4 py-4 md:px-5">
          <div className="grid gap-5 lg:grid-cols-[minmax(20rem,0.78fr)_minmax(0,1.22fr)] lg:items-stretch">
            <div className="flex min-w-0 flex-col justify-between gap-5">
              <div>
                <p className="text-[0.72rem] font-semibold uppercase text-muted">
                  Ingredient dose lookup
                </p>
                <h1 className="mt-2 text-[1.25rem] font-semibold tracking-[-0.01em] text-foreground md:text-[1.48rem]">
                {siteName}
              </h1>
                <p className="mt-3 max-w-xl text-sm leading-6 text-muted">
                {siteDescription}
              </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href="#explorer"
                  className="inline-flex min-h-10 items-center justify-center rounded-[0.55rem] bg-slate-900 px-4 py-[0.58rem] text-[0.84rem] font-medium text-white transition duration-200 hover:bg-slate-700"
                >
                  성분·함량 조회
                </Link>
                <Link
                  href="/ingredients"
                  className="inline-flex min-h-10 items-center justify-center rounded-[0.55rem] border border-border-subtle bg-white px-4 py-[0.58rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:border-slate-300"
                >
                  성분 레퍼런스
                </Link>
              </div>
            </div>

            <div className="overflow-hidden rounded-[0.65rem] border border-border-subtle bg-white">
              <div className="grid grid-cols-[minmax(0,1fr)_8.5rem_minmax(0,1fr)] border-b border-border-subtle bg-slate-50 px-3 py-2 text-[0.72rem] font-semibold uppercase text-muted">
                <span>Ingredient</span>
                <span>Amount</span>
                <span>Signal</span>
              </div>
              {lookupRows.map((row) => (
                <div
                  key={row.ingredient}
                  className="grid grid-cols-[minmax(0,1fr)_8.5rem_minmax(0,1fr)] gap-3 border-b border-border-subtle px-3 py-3 text-sm last:border-b-0"
                >
                  <span className="min-w-0 font-semibold text-foreground">
                    {row.ingredient}
                  </span>
                  <span className="text-xs leading-5 text-muted">
                    {row.threshold}
                  </span>
                  <span className="text-xs leading-5 text-muted">{row.cue}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="surface-card rounded-[0.8rem] px-4 py-4 md:px-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
            <div>
              <p className="text-[0.76rem] font-semibold uppercase text-muted">
                성분 중심 연구 범위
              </p>
              <h2 className="mt-1 text-[1.02rem] font-semibold text-foreground">
                고함량 제품 조건과 상한섭취량 신호를 함께 봅니다
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                비타민 D·칼슘, 비타민 B6, 철·마그네슘·아연을 성분 단위로
                나누고 용량, 병용 성분, 제품형 주의 신호를 연결합니다.
              </p>
            </div>

            <dl className="grid grid-cols-2 gap-2 text-sm">
              {scopeItems.map((item, index) => (
                <div
                  key={item.label}
                  className={`min-w-0 rounded-[0.55rem] border px-3 py-3 ${
                    index === 2
                      ? "border-slate-300 bg-slate-900 text-white"
                      : "border-slate-200 bg-white"
                  }`}
                >
                  <dt
                    className={`text-[0.74rem] font-medium ${
                      index === 2 ? "text-slate-300" : "text-muted"
                    }`}
                  >
                    {item.label}
                  </dt>
                  <dd
                    className={`mt-1 text-[1.12rem] font-semibold ${
                      index === 2 ? "text-white" : "text-foreground"
                    }`}
                  >
                    {item.value}
                  </dd>
                  <dd
                    className={`mt-1 text-[0.76rem] leading-5 ${
                      index === 2 ? "text-slate-300" : "text-muted"
                    }`}
                  >
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

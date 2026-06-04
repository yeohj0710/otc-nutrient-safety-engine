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
      ingredient: "비타민 D + 칼슘",
      threshold: "4,000 IU/day 기준",
      cue: "혈중 칼슘 증가, 신장결석",
    },
    {
      ingredient: "비타민 B6",
      threshold: "50 mg/day 이상",
      cue: "신경 증상, 장기 복용",
    },
    {
      ingredient: "철·아연·마그네슘",
      threshold: "동시 섭취 확인",
      cue: "속불편, 흡수 간섭",
    },
  ];
  const ledgerItems = [
    ["검색 결과", formatCount(literatureSummary.latestPubMedHitCount), "PubMed/MEDLINE"],
    ["보조 검색", formatCount(literatureSummary.secondaryHitTotal), "검색원 전체"],
    ["먼저 볼 문헌", formatCount(literatureSummary.priorityCandidateCount), `저장 ${formatCount(literatureSummary.latestPubMedStoredRecords)}건`],
    ["함량 기준", formatCount(metadata.meta.safetyRuleCount), `출처 ${formatCount(metadata.meta.sourceCount)}개`],
  ];

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto grid w-full max-w-7xl gap-5">
        <section className="grid overflow-hidden border border-slate-800 bg-white shadow-sm lg:grid-cols-[minmax(0,1fr)_24rem]">
          <div className="bg-slate-950 px-5 py-6 text-white md:px-7">
            <p className="text-[0.72rem] font-bold uppercase tracking-[0.22em] text-amber-200">
              성분과 함량을 먼저 확인
            </p>
            <h1 className="mt-3 break-keep text-[1.7rem] font-bold leading-tight md:text-[2.15rem]">
              {siteName}
            </h1>
            <p className="mt-4 max-w-3xl text-[0.96rem] leading-7 text-slate-200">
              {siteDescription}
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link
                href="#explorer"
                className="inline-flex min-h-11 items-center justify-center bg-amber-300 px-4 py-2 text-sm font-bold text-slate-950 transition duration-200 hover:bg-amber-200"
              >
                성분·함량 조회
              </Link>
              <Link
                href="/ingredients"
                className="inline-flex min-h-11 items-center justify-center border border-white/25 px-4 py-2 text-sm font-semibold text-white transition duration-200 hover:bg-white/10"
              >
                성분 근거 자료
              </Link>
            </div>
          </div>

          <div className="border-t border-slate-800 lg:border-l lg:border-t-0">
            <div className="grid grid-cols-[minmax(0,1fr)_8.5rem_minmax(0,1fr)] bg-slate-200 px-3 py-2 text-xs font-bold text-slate-700">
              <span>성분</span>
              <span>함량 기준</span>
              <span>주의 신호</span>
            </div>
            {lookupRows.map((row) => (
              <div
                key={row.ingredient}
                className="grid grid-cols-[minmax(0,1fr)_8.5rem_minmax(0,1fr)] gap-3 border-t border-slate-200 px-3 py-4 text-sm"
              >
                <span className="min-w-0 font-bold text-slate-950">
                  {row.ingredient}
                </span>
                <span className="text-xs leading-5 text-slate-600">
                  {row.threshold}
                </span>
                <span className="text-xs leading-5 text-slate-600">
                  {row.cue}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="grid border border-slate-300 bg-white md:grid-cols-[16rem_minmax(0,1fr)]">
          <div className="border-b border-slate-300 bg-amber-100 px-4 py-4 md:border-b-0 md:border-r">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-700">
              성분 중심 연구 범위
            </p>
            <h2 className="mt-2 text-lg font-bold leading-7 text-slate-950">
              고함량 조건과 상한섭취량 신호를 한 표에서 봅니다
            </h2>
          </div>
          <dl className="grid grid-cols-2 md:grid-cols-4">
            {ledgerItems.map(([label, value, note], index) => (
              <div
                key={label}
                className={`border-b border-r border-slate-200 px-4 py-4 last:border-r-0 md:border-b-0 ${
                  index === 2 ? "bg-slate-950 text-white" : "bg-white"
                }`}
              >
                <dt
                  className={`text-xs font-bold ${
                    index === 2 ? "text-amber-200" : "text-slate-500"
                  }`}
                >
                  {label}
                </dt>
                <dd className="mt-2 text-2xl font-bold">{value}</dd>
                <dd
                  className={`mt-1 text-xs leading-5 ${
                    index === 2 ? "text-slate-300" : "text-slate-600"
                  }`}
                >
                  {note}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section id="explorer" className="scroll-mt-6">
          <RuleExplorerClient metadata={metadata} />
        </section>
      </div>
    </main>
  );
}

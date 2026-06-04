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
  const doseRows = [
    ["비타민 D + 칼슘", "4,000 IU/day 기준", "혈중 칼슘 증가, 신장결석"],
    ["비타민 B6", "50 mg/day 이상", "신경 증상, 장기 복용"],
    ["철·아연·마그네슘", "동시 섭취 확인", "속불편, 흡수 간섭"],
  ];
  const register = [
    ["PubMed", formatCount(literatureSummary.latestPubMedHitCount), "검색 결과"],
    ["보조 검색", formatCount(literatureSummary.secondaryHitTotal), "검색원 전체"],
    ["먼저 볼 문헌", formatCount(literatureSummary.priorityCandidateCount), `저장 ${formatCount(literatureSummary.latestPubMedStoredRecords)}건`],
    ["함량 기준", formatCount(metadata.meta.safetyRuleCount), `출처 ${formatCount(metadata.meta.sourceCount)}개`],
  ];

  return (
    <main className="min-h-screen bg-[#050816] px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto grid w-full max-w-7xl gap-6 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className="border border-amber-300/35 bg-black px-4 py-5">
          <p className="text-[0.68rem] font-bold uppercase tracking-[0.24em] text-amber-300">
            함량대장
          </p>
          <div className="mt-5 grid gap-3">
            {register.map(([label, value, note]) => (
              <div
                key={label}
                className="border-l-2 border-amber-300/70 bg-slate-950 px-3 py-3"
              >
                <p className="text-xs font-bold text-slate-400">{label}</p>
                <p className="mt-1 text-2xl font-black text-white">{value}</p>
                <p className="mt-1 text-xs text-slate-400">{note}</p>
              </div>
            ))}
          </div>
          <div className="mt-5 grid gap-2">
            <Link
              href="#explorer"
              className="border border-amber-300 bg-amber-300 px-3 py-2 text-center text-sm font-black text-slate-950 hover:bg-amber-200"
            >
              함량 판정
            </Link>
            <Link
              href="/ingredients"
              className="border border-slate-600 px-3 py-2 text-center text-sm font-bold text-slate-100 hover:border-amber-300"
            >
              성분 근거 자료
            </Link>
          </div>
        </aside>

        <div className="grid gap-6">
          <section className="grid border border-slate-700 bg-slate-950 shadow-[0_0_0_1px_rgba(250,204,21,0.08)] lg:grid-cols-[minmax(0,1fr)_28rem]">
            <div className="px-5 py-7 md:px-8 md:py-9">
              <p className="text-[0.72rem] font-black uppercase tracking-[0.24em] text-amber-300">
                성분과 함량을 먼저 확인
              </p>
              <h1 className="mt-4 break-keep text-[1.9rem] font-black leading-tight text-white md:text-[2.6rem]">
                {siteName}
              </h1>
              <p className="mt-5 max-w-3xl text-[0.98rem] leading-7 text-slate-300">
                {siteDescription}
              </p>
              <div className="mt-6 grid max-w-xl grid-cols-3 border border-slate-700 text-xs">
                {["성분", "함량", "주의 신호"].map((item) => (
                  <span
                    key={item}
                    className="border-r border-slate-700 px-3 py-2 font-bold text-amber-200 last:border-r-0"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="border-t border-slate-700 lg:border-l lg:border-t-0">
              <div className="grid grid-cols-[minmax(0,1fr)_9rem_minmax(0,1fr)] bg-amber-300 px-3 py-2 text-xs font-black text-slate-950">
                <span>성분</span>
                <span>함량 기준</span>
                <span>주의 신호</span>
              </div>
              {doseRows.map(([ingredient, threshold, cue]) => (
                <div
                  key={ingredient}
                  className="grid grid-cols-[minmax(0,1fr)_9rem_minmax(0,1fr)] gap-3 border-t border-slate-700 px-3 py-4 text-sm"
                >
                  <span className="min-w-0 font-black text-white">
                    {ingredient}
                  </span>
                  <span className="text-xs leading-5 text-amber-100">
                    {threshold}
                  </span>
                  <span className="text-xs leading-5 text-slate-300">
                    {cue}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section id="explorer" className="scroll-mt-6">
            <RuleExplorerClient metadata={metadata} />
          </section>
        </div>
      </div>
    </main>
  );
}

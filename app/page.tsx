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
  const highlights = [
    ["검색 결과", formatCount(literatureSummary.latestPubMedHitCount)],
    ["보조 검색", formatCount(literatureSummary.secondaryHitTotal)],
    ["먼저 볼 문헌", formatCount(literatureSummary.priorityCandidateCount)],
    ["함량 기준", formatCount(metadata.meta.safetyRuleCount)],
  ];
  const doseChecks = [
    ["비타민 D + 칼슘", "4,000 IU/day 기준", "혈중 칼슘 증가"],
    ["비타민 B6", "50 mg/day 이상", "신경 증상"],
    ["철·아연·마그네슘", "동시 섭취 확인", "흡수 간섭"],
  ];

  return (
    <main className="min-h-screen bg-[#f5f7fb] px-5 py-8 text-[#191f28] sm:px-8">
      <div className="mx-auto grid w-full max-w-6xl gap-12">
        <section className="grid gap-10 py-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-center">
          <div>
            <p className="text-[0.95rem] font-bold text-[#3182f6]">
              성분과 함량을 먼저 확인
            </p>
            <h1 className="mt-4 max-w-3xl break-keep text-[2.45rem] font-bold leading-tight md:text-[4.4rem]">
              {siteName}
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-[#4e5968]">
              {siteDescription}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="#explorer"
                className="rounded-[0.5rem] bg-[#3182f6] px-5 py-3 text-sm font-bold text-white shadow-[0_8px_20px_rgba(49,130,246,0.25)]"
              >
                함량 판정하기
              </Link>
              <Link
                href="/ingredients"
                className="rounded-[0.5rem] bg-white px-5 py-3 text-sm font-bold text-[#4e5968]"
              >
                성분 근거 자료
              </Link>
            </div>
          </div>

          <div className="rounded-[0.75rem] bg-white p-5 shadow-[0_18px_48px_rgba(2,32,71,0.08)]">
            <p className="text-sm font-bold text-[#6b7684]">오늘 볼 항목</p>
            <div className="mt-4 divide-y divide-[#edf1f7]">
              {doseChecks.map(([name, limit, signal]) => (
                <div key={name} className="py-4">
                  <div className="flex items-center justify-between gap-4">
                    <p className="font-bold">{name}</p>
                    <p className="text-sm font-semibold text-[#3182f6]">
                      {limit}
                    </p>
                  </div>
                  <p className="mt-1 text-sm text-[#8b95a1]">{signal}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-5 sm:grid-cols-4">
          {highlights.map(([label, value]) => (
            <div key={label}>
              <p className="text-sm font-semibold text-[#6b7684]">{label}</p>
              <p className="mt-2 text-3xl font-bold tracking-tight">{value}</p>
            </div>
          ))}
        </section>

        <section id="explorer" className="scroll-mt-6">
          <RuleExplorerClient metadata={metadata} />
        </section>
      </div>
    </main>
  );
}

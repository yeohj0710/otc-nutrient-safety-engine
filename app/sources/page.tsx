import type { Metadata } from "next";
import Link from "next/link";

import { SourceBrowserClient } from "@/src/components/source-browser-client";
import { getExplorerMetadata, getSourceBrowseData } from "@/src/lib/knowledge";
import { siteName } from "@/src/lib/site";

export const metadata: Metadata = {
  title: "출처 브라우저",
  description:
    "서비스에 연결된 논문, 공공 자료, 안전성 출처를 기준별로 빠르게 찾아볼 수 있습니다.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function SourcesPage() {
  const metadata = getExplorerMetadata();
  const sources = getSourceBrowseData();

  return (
    <main className="app-page min-h-screen px-4 py-4 sm:px-6 lg:px-6">
      <div className="page-shell flex flex-col gap-4">
        <section className="surface-card rounded-[1.15rem] px-4 py-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                Sources
              </p>
              <h1 className="mt-2 text-[0.96rem] font-semibold tracking-[-0.02em] text-foreground sm:text-[1.02rem]">
                출처 브라우저
              </h1>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
                규칙에 연결된 논문, 공공 문서, 참고 자료를 빠르게 좁혀 보고
                필요한 출처만 바로 열어볼 수 있습니다.
              </p>

              <div className="mt-3 flex flex-wrap gap-2">
                <span className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-xs font-medium text-foreground">
                  출처 {sources.length}
                </span>
                <span className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-xs font-medium text-foreground">
                  관할권 {metadata.jurisdictions.length}
                </span>
                <span className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-xs font-medium text-foreground">
                  근거 수준 {metadata.sourceEvidenceLevels.length}
                </span>
                <span className="rounded-full border border-border-subtle bg-white px-3 py-1.5 text-xs font-medium text-foreground">
                  {siteName} 데이터
                </span>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Link
                href="/"
                className="inline-flex min-h-10 items-center justify-center rounded-full bg-accent px-4 py-[0.58rem] text-[0.84rem] font-medium text-white transition duration-200 hover:bg-accent-strong"
              >
                메인으로 돌아가기
              </Link>
              <Link
                href="/ingredients"
                className="inline-flex min-h-10 items-center justify-center rounded-full border border-border-subtle bg-white px-4 py-[0.58rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:border-stone-300"
              >
                영양소 레퍼런스
              </Link>
            </div>
          </div>
        </section>

        <section id="sources" className="scroll-mt-6">
          <SourceBrowserClient
            sources={sources}
            jurisdictions={metadata.jurisdictions}
            evidenceLevels={metadata.sourceEvidenceLevels}
          />
        </section>
      </div>
    </main>
  );
}

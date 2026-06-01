import Link from "next/link";
import type { Metadata } from "next";

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

export default function Home() {
  const metadata = getExplorerMetadata();

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

        <section id="explorer" className="scroll-mt-6">
          <RuleExplorerClient metadata={metadata} />
        </section>
      </div>
    </main>
  );
}

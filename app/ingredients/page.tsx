import type { Metadata } from "next";
import Link from "next/link";

import { IngredientReferenceBrowserClient } from "@/src/components/ingredient-reference-browser-client";
import { getIngredientReferenceBrowseData } from "@/src/lib/knowledge";

export const metadata: Metadata = {
  title: "영양소별 레퍼런스",
  description:
    "영양소별로 연결된 논문과 공공 자료를 모아 보고, 해당 영양소의 핵심 근거 맥락과 외부 원문 링크를 바로 확인합니다.",
};

export default function IngredientReferencesPage() {
  const ingredients = getIngredientReferenceBrowseData();

  return (
    <main className="app-page min-h-screen px-4 pb-20 pt-6 md:px-5 lg:px-6">
      <div className="page-shell space-y-6">
        <section className="surface-card-strong rounded-[2rem] px-6 py-6">
          <p className="eyebrow">Reference Map</p>
          <h1 className="mt-4 text-[clamp(1.62rem,2.8vw,2.18rem)] font-semibold tracking-[-0.03em] text-foreground">
            영양소별 레퍼런스
          </h1>
          <p className="measure-copy mt-4 text-sm leading-7 text-muted">
            어떤 영양소를 이번 연구 범위에 먼저 포함할지 검토할 수 있도록,
            영양소별 레퍼런스를 한 번에 훑어보는 페이지입니다. 영양소를 펼치면
            이 자료가 왜 중요한지, 논문에서 어떤 맥락으로 쓰였는지, 원문은
            어디서 확인하면 되는지를 이 페이지 안에서 바로 볼 수 있습니다.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/"
              className="inline-flex min-h-11 items-center justify-center rounded-full bg-accent px-5 py-[0.62rem] text-[0.84rem] font-medium text-white transition duration-200 hover:-translate-y-0.5 hover:bg-accent-strong"
            >
              메인으로 돌아가기
            </Link>
            <Link
              href="/sources"
              className="inline-flex min-h-11 items-center justify-center rounded-full border border-border-subtle bg-white px-5 py-[0.62rem] text-[0.84rem] font-medium text-foreground transition duration-200 hover:-translate-y-0.5 hover:border-stone-300"
            >
              전체 출처 보기
            </Link>
          </div>
        </section>

        <IngredientReferenceBrowserClient ingredients={ingredients} />
      </div>
    </main>
  );
}

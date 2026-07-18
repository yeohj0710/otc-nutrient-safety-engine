import type { Metadata } from "next";

import runtimeData from "@/src/generated/otc-runtime.json";
import supportingLiterature from "@/src/generated/otc-supporting-literature.json";
import { OtcProductSafetyClient, type OtcRuntime } from "@/src/components/otc-product-safety-client";
import { siteDescription, siteName } from "@/src/lib/site";

export const metadata: Metadata = {
  title: siteName,
  description: siteDescription,
  alternates: {
    canonical: "/",
  },
};

export default function Home() {
  return (
    <main id="main-content" className="min-h-screen bg-[#f3f5f7] text-[#17223b]">
      <section className="px-4 pb-5 pt-8 sm:px-6 sm:pb-6 sm:pt-11">
        <div className="mx-auto max-w-[1080px]">
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div>
              <p className="inline-flex min-h-8 items-center rounded-lg bg-[#e8f5f1] px-3 text-[12px] font-extrabold text-[#17604f]">
                국내 OTC 근거 조회
              </p>
              <h1 className="mt-3 max-w-3xl break-keep text-[32px] font-extrabold leading-[1.25] tracking-[-0.035em] sm:text-[42px]">
                같이 먹는 약, 한눈에 점검하세요
              </h1>
              <p className="mt-3 max-w-3xl break-keep text-[15px] font-medium leading-[1.65] text-[#667085] sm:text-[17px]">
                제품명만 담으면 중복 성분·하루 입력량·복용 간격과 연령·질환·병용약 주의를 근거 원문까지 연결해 보여드려요.
              </p>
            </div>
            <div className="flex max-w-xl flex-wrap gap-2 lg:justify-end" aria-label="시스템 데이터 현황">
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#dce2e8] bg-white px-3.5 text-[12px] font-bold text-[#475467]">
                허가 확인 제품 {runtimeData.products.length}개
              </span>
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#dce2e8] bg-white px-3.5 text-[12px] font-bold text-[#475467]">
                판매 SKU {runtimeData.catalogCoverage.sourceSkuCount}건 선별
              </span>
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#dce2e8] bg-white px-3.5 text-[12px] font-bold text-[#475467]">
                약학정보원 연결 {runtimeData.catalogCoverage.healthKrConfirmedCount}건
              </span>
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#dce2e8] bg-white px-3.5 text-[12px] font-bold text-[#475467]">
                판정 규칙 {runtimeData.rulesReleased}개 · 보조 문헌 {supportingLiterature.length}편
              </span>
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#eed7b7] bg-[#fff8ee] px-3.5 text-[12px] font-bold text-[#87520b]">
                연구용 · 블라인드 독립평가 미완료
              </span>
            </div>
          </div>
        </div>
      </section>

      <section id="checker" className="px-3 pb-8 sm:px-6 sm:pb-12">
        <div className="mx-auto max-w-[1080px]">
          <OtcProductSafetyClient runtime={runtimeData as OtcRuntime} />
        </div>
      </section>

      <section className="border-t border-[#e1e5ea] bg-white px-4 py-7 sm:px-6">
        <div className="mx-auto grid max-w-[1080px] gap-5 sm:grid-cols-3 sm:gap-8">
          {[
            ["제품명부터 시작", "성분을 몰라도 제품을 검색해 함께 복용하는 조합을 만들 수 있어요."],
            ["판정 기준은 고정", "AI가 위험 수준이나 용량 기준을 만들지 않고 공개된 결정론적 규칙만 사용해요."],
            ["근거까지 바로 확인", "각 주의 항목에서 식약처 허가 원문과 판정에 맞는 학술문헌을 함께 볼 수 있어요."],
          ].map(([title, description], index) => (
            <div key={title} className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#20324f] text-[10px] font-extrabold text-white">
                {index + 1}
              </span>
              <div>
                <h2 className="text-[15px] font-extrabold text-[#17223b]">{title}</h2>
                <p className="mt-1 break-keep text-[13px] font-medium leading-[1.6] text-[#667085]">{description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

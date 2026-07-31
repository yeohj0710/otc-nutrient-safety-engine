import type { Metadata } from "next";

import runtimeData from "@/src/generated/otc-runtime.json";
import supportingLiterature from "@/src/generated/otc-supporting-literature.json";
import { OtcProductSafetyClient, type OtcRuntime } from "@/src/components/otc-product-safety-client";
import {
  literatureHomepageStatusSummary,
  type SupportingLiterature,
} from "@/src/lib/otc/presentation";
import { siteDescription, siteName } from "@/src/lib/site";

const productRuleBindingCount = runtimeData.products.reduce(
  (sum, product) => sum + product.supportedReleasedRuleIds.length,
  0,
);
const administrationConstraintCount = runtimeData.products.reduce(
  (sum, product) => sum + product.administrationConstraints.length,
  0,
);
const literatureStatus = literatureHomepageStatusSummary(
  supportingLiterature as SupportingLiterature[],
);
const v5LiteratureLinkCount = literatureStatus.v5Linked;
const v5LiteratureRuleCount = literatureStatus.v5RuleCount;
const v5DirectMatchLinkCount = literatureStatus.directMatch;
const v5ConditionalDirectLinkCount = literatureStatus.conditionalDirect;
const v5BackgroundOnlyLinkCount = literatureStatus.backgroundOnly;
const v5ExcludedLinkCount = literatureStatus.excluded;

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
        <div className="mx-auto max-w-[1240px]">
          <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
            <div>
              <p className="inline-flex min-h-8 items-center rounded-lg bg-[#e8f5f1] px-3 text-[12px] font-extrabold text-[#17604f]">
                국내 OTC 근거 조회
              </p>
              <h1 className="mt-3 max-w-3xl break-keep text-[32px] font-extrabold leading-[1.25] tracking-[-0.035em] sm:text-[42px]">
                함께 쓰는 약, 지원 범위부터 점검하세요
              </h1>
              <p className="mt-3 max-w-3xl break-keep text-[15px] font-medium leading-[1.65] text-[#667085] sm:text-[17px]">
                허가 확인 제품 {runtimeData.products.length}개에 연결된 공개 안전성 규칙과 제품별 허가 사용·복용 조건만 판정하는 연구용 시제품입니다. 지원하지 않는 질환·병용약 입력은 판정하지 않고 따로 알려드려요.
              </p>
            </div>
            <div className="flex max-w-xl flex-wrap gap-2 lg:justify-end" aria-label="시스템 데이터 현황">
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#dce2e8] bg-white px-3.5 text-[12px] font-bold text-[#475467]">
                허가 확인 제품 {runtimeData.products.length}개
              </span>
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#dce2e8] bg-white px-3.5 text-[12px] font-bold text-[#475467]">
                공개 안전성 규칙 {runtimeData.rulesReleased}개 · 제품별 직접 규칙 연결 {productRuleBindingCount}건
              </span>
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#dce2e8] bg-white px-3.5 text-[12px] font-bold text-[#475467]">
                허가 사용·복용 조건 {administrationConstraintCount}건
              </span>
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#dce2e8] bg-white px-3.5 text-[12px] font-bold text-[#475467]">
                v5.0 채택 {v5LiteratureRuleCount}규칙·{v5LiteratureLinkCount}건 · 직접 일치 {v5DirectMatchLinkCount}건 · 범위 일치 시 직접 {v5ConditionalDirectLinkCount}건 · 배경 전용 {v5BackgroundOnlyLinkCount}건 · 감사 전용·결과 화면 제외 {v5ExcludedLinkCount}건
              </span>
              <span className="inline-flex min-h-10 items-center rounded-lg border border-[#eed7b7] bg-[#fff8ee] px-3.5 text-[12px] font-bold text-[#87520b]">
                연구용 시제품 · 임상 사용 승인 아님
              </span>
            </div>
          </div>
        </div>
      </section>

      <section id="checker" className="px-3 pb-8 sm:px-6 sm:pb-12">
        <div className="mx-auto max-w-[1240px]">
          <OtcProductSafetyClient runtime={runtimeData as OtcRuntime} />
        </div>
      </section>

      <section className="border-t border-[#e1e5ea] bg-white px-4 py-7 sm:px-6">
        <div className="mx-auto grid max-w-[1240px] gap-5 sm:grid-cols-3 sm:gap-8">
          {[
            ["제품별 범위부터 확인", "제품 카드에서 지원 점검 유형, 공개 규칙 연결, 허가 조건을 따로 보여드려요."],
            ["판정 기준은 고정", "AI가 위험 수준이나 용량 기준을 만들지 않아요. 공개 안전성 규칙과 제품별 허가 사용·복용 조건만 적용해요."],
            ["근거 범위까지 확인", "현재 성분에 직접 일치하는 문헌과 같은 규칙의 다른 성분 연구를 섞지 않고 보여드려요."],
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

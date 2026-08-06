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
          {/* 머리글은 제목·한 줄 설명·한계 한 줄까지만 둔다. 예전에는 여기에
              숫자 배지 넷이 상자를 이루고 있어서, 도구를 쓰기도 전에 읽을 것이
              네 덩이 더 있었다. 같은 숫자는 화면 맨 아래 연구 범위 문단이 이미
              적고 있다. */}
          {/* 본문(점검 도구)이 920px 한 줄로 서므로 머리글도 같은 폭에 맞춘다.
              폭이 어긋나면 제목과 도구가 서로 다른 화면처럼 보인다. */}
          <div className="mx-auto w-full max-w-[920px]">
            <p className="inline-flex min-h-8 items-center rounded-lg bg-[#e8f5f1] px-3 text-[13px] font-extrabold text-[#17604f]">
              국내 OTC 근거 조회
            </p>
            <h1 className="mt-3 break-keep text-[32px] font-extrabold leading-[1.25] tracking-[-0.035em] sm:text-[42px]">
              함께 쓰는 약의 중복 성분·용량 점검
            </h1>
            <p className="mt-3 break-keep text-[15px] font-medium leading-[1.65] text-[#667085] sm:text-[17px]">
              제품명만 담으면 중복 성분과 하루 사용량, 연령·질환·병용약 주의를
              식약처 허가 원문까지 연결해 보여줍니다.
            </p>
            <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-2 text-[13px] font-bold text-[#667085]">
              <span className="inline-flex min-h-8 items-center rounded-lg border border-[#eed7b7] bg-[#fff8ee] px-3 text-[#87520b]">
                연구용 시제품 · 임상 사용 승인 아님
              </span>
              <span className="break-keep font-medium">
                허가 확인 제품 {runtimeData.products.length}개 · 공개 안전성 규칙{" "}
                {runtimeData.rulesReleased}개 · 허가 복용 조건{" "}
                {administrationConstraintCount}건 · 채택 문헌{" "}
                {v5LiteratureLinkCount}건
              </span>
            </p>
          </div>
        </div>
      </section>

      <section id="checker" className="px-4 pb-8 pt-1 sm:px-6 sm:pb-12 sm:pt-2">
        <div className="mx-auto max-w-[1240px]">
          <OtcProductSafetyClient runtime={runtimeData as OtcRuntime} />
        </div>
      </section>

      <section className="border-t border-[#e1e5ea] bg-white px-4 py-7 sm:px-6">
        <div className="mx-auto w-full max-w-[920px]">
        <div className="grid gap-5 sm:grid-cols-3 sm:gap-8">
          {[
            ["제품명부터 시작", "성분을 몰라도 제품을 검색해 함께 복용하는 조합을 만들 수 있습니다."],
            ["고정된 판정 기준", "AI가 위험 수준이나 용량 기준을 만들지 않습니다. 공개 안전성 규칙과 허가 복용 조건만 적용합니다."],
            ["근거까지 바로 확인", "각 주의 항목에서 식약처 허가 원문과 판정에 맞는 학술문헌을 함께 볼 수 있습니다."],
          ].map(([title, description], index) => (
            <div key={title} className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#20324f] text-[13px] font-extrabold text-white">
                {index + 1}
              </span>
              <div>
                <h2 className="text-[15px] font-extrabold text-[#17223b]">{title}</h2>
                <p className="mt-1 break-keep text-[14px] font-medium leading-[1.65] text-[#667085]">{description}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-6 break-keep border-t border-[#eef1f4] pt-5 text-[13px] font-medium leading-[1.7] text-[#5f6b7a]">
          이 시제품은 공개 안전성 규칙과 제품별 허가 사용·복용 조건만 판정합니다.
          제품별 직접 규칙 연결 {productRuleBindingCount}건과 허가 사용·복용 조건 {administrationConstraintCount}건을 사용합니다.
          v5.0 채택 문헌 {v5LiteratureRuleCount}규칙 {v5LiteratureLinkCount}건은
          직접 일치 {v5DirectMatchLinkCount}건, 범위 일치 시 직접 {v5ConditionalDirectLinkCount}건,
          배경 전용 {v5BackgroundOnlyLinkCount}건으로 나뉩니다.
          감사 전용·결과 화면 제외 {v5ExcludedLinkCount}건은 화면에 넣지 않습니다.
        </p>
        </div>
      </section>
    </main>
  );
}

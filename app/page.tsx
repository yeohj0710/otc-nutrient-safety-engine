import type { Metadata } from "next";

import runtimeData from "@/src/generated/otc-runtime.json";
import supportingLiterature from "@/src/generated/otc-supporting-literature.json";
import researchSummary from "@/src/generated/recollect/research-summary.json";
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

const numberFormat = (value: number) => value.toLocaleString("ko-KR");
const correction = researchSummary.screening.posthocCorrection;

/* 알림 상자에 싣는 연구 진행 기록. 날짜는 커밋과 정정 규약 번호에서 가져온다. */
const notices = [
  {
    date: "2026-09-05",
    title: "문헌 선별 사후 정정 반영",
    body: `검토 ${numberFormat(correction.reviewed_rows)}행을 대조해 판정을 정정했습니다. AI 채점 지표는 정정 전 값을 그대로 둡니다.`,
  },
  {
    date: "2026-08-31",
    title: "연구 정보 화면을 규칙별 문헌 연동 서술로 개편",
  },
  {
    date: "2026-08-29",
    title: "화면 수치를 문헌 재수집 결과로 교체",
  },
];

export const metadata: Metadata = {
  title: siteName,
  description: siteDescription,
  alternates: {
    canonical: "/",
  },
};

function QuickIcon({ kind }: { kind: "search" | "rule" | "evidence" }) {
  if (kind === "search") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="11" cy="11" r="6.5" />
        <path d="m20 20-4.2-4.2" />
      </svg>
    );
  }
  if (kind === "rule") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 4 6.5v5c0 4.6 3.4 8.4 8 9.5 4.6-1.1 8-4.9 8-9.5v-5L12 3Z" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 3h9l4 4v14H6z" />
      <path d="M15 3v4h4M9 12h6M9 16h6" />
    </svg>
  );
}

export default function Home() {
  const [lead, ...rest] = notices;

  return (
    <main id="main-content" tabIndex={-1} className="app-page min-h-screen">
      <section className="gov-hero" aria-labelledby="site-title">
        <div className="mx-auto max-w-[1240px]">
          <div className="gov-hero-grid">
            <div>
              <p className="gov-hero-kicker">졸업논문 연구, 국내 일반의약품 근거 추적형 안전성 조회</p>
              <h1 id="site-title" className="gov-hero-title">
                일반의약품 함께복용 점검
              </h1>
              <p className="gov-hero-lead">
                제품명을 검색해 담으면 중복 성분, 하루 사용량, 연령과 질환과 병용약 주의 항목을
                식약처 허가 원문과 함께 확인합니다. 판정 기준은 공개 안전성 규칙과 허가사항이고,
                AI는 설명만 돕습니다.
              </p>
              <p className="gov-hero-badges">
                <span className="gov-badge gov-badge-warn">연구용 시제품, 임상 사용 승인 아님</span>
                <span className="gov-badge">허가 확인 제품 {runtimeData.products.length}개</span>
                <span className="gov-badge">공개 안전성 규칙 {runtimeData.rulesReleased}개</span>
                <span className="gov-badge">허가 복용 조건 {administrationConstraintCount}건</span>
                <span className="gov-badge">채택 문헌 {v5LiteratureLinkCount}건</span>
              </p>
            </div>

            <aside className="gov-notice" aria-labelledby="notice-title">
              <div className="gov-notice-tabs">
                <span id="notice-title" className="gov-notice-tab" aria-current="true">
                  연구 안내
                </span>
                <span className="gov-notice-tab">진행 기록</span>
              </div>
              <div className="gov-notice-lead">
                <p className="gov-notice-date">
                  <small>{lead.date.slice(0, 4)}</small>
                  <strong>{lead.date.slice(5).replace("-", ".")}</strong>
                </p>
                <div>
                  <h3>{lead.title}</h3>
                  <p>{lead.body}</p>
                </div>
              </div>
              <ul className="gov-notice-list">
                {rest.map((item) => (
                  <li key={item.date + item.title}>
                    <span>{item.title}</span>
                    <time dateTime={item.date}>{item.date}</time>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        </div>
      </section>

      <section id="checker" className="px-4 pb-10 pt-6 sm:px-6 sm:pb-14 sm:pt-8">
        <div className="mx-auto max-w-[1240px]">
          <OtcProductSafetyClient runtime={runtimeData as OtcRuntime} />
        </div>
      </section>

      <section id="guide" className="gov-band" aria-label="이용 안내">
        <div className="mx-auto max-w-[1240px]">
          <div className="gov-quick">
            {[
              {
                kind: "search" as const,
                title: "제품명부터 검색",
                body: "성분을 몰라도 제품명으로 검색해 함께 복용하는 조합을 담을 수 있습니다.",
              },
              {
                kind: "rule" as const,
                title: "고정된 판정 기준",
                body: "AI가 위험 수준이나 용량 기준을 만들지 않습니다. 공개 안전성 규칙과 허가 복용 조건만 적용합니다.",
              },
              {
                kind: "evidence" as const,
                title: "근거 원문 확인",
                body: "각 주의 항목에서 식약처 허가 원문과 판정에 맞는 학술문헌을 함께 볼 수 있습니다.",
              },
            ].map((item) => (
              <div key={item.title} className="gov-quick-item">
                <span className="gov-quick-icon">
                  <QuickIcon kind={item.kind} />
                </span>
                <div>
                  <h2>{item.title}</h2>
                  <p>{item.body}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="gov-scope">
            <h2>판정 범위</h2>
            <p>
              이 시제품은 공개 안전성 규칙과 제품별 허가 사용/복용 조건만 판정합니다.
              제품별 직접 규칙 연결 {productRuleBindingCount}건과 허가 사용/복용 조건 {administrationConstraintCount}건을 사용합니다.
              문장과 출처를 대조한 문헌 {v5LiteratureRuleCount}규칙 {v5LiteratureLinkCount}건은
              직접 일치 {v5DirectMatchLinkCount}건, 범위 일치 시 직접 {v5ConditionalDirectLinkCount}건,
              배경 전용 {v5BackgroundOnlyLinkCount}건으로 나뉩니다.
              감사 전용, 결과 화면 제외 {v5ExcludedLinkCount}건은 화면에 넣지 않습니다.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}

export const siteName = "일반의약품형 영양성분 안전성 조회 시스템";
export const siteTagline =
  "고함량 비타민·미네랄 성분의 용량, 약물, 질환 조건별 안전 근거를 함께 보는 안내";
export const siteDescription =
  "일반의약품과 건강기능식품 경계에 있는 고함량 영양성분을 중심으로 용량, 복용 약물, 질환 상태에 따른 주의사항과 근거 문헌을 조회하는 성분 중심 안전성 안내 서비스입니다.";
export const siteKeywords = [
  "일반의약품형 영양성분 안전성 조회 시스템",
  "고함량 비타민 안전성",
  "고함량 미네랄 안전성",
  "비타민 D 과량",
  "비타민 B6 신경병증",
  "철분 보충제 이상반응",
  "영양제 상호작용",
  "성분 중심 안전성 근거",
];

export function getSiteUrl() {
  const rawUrl =
    process.env.NEXT_PUBLIC_SITE_URL ??
    process.env.SITE_URL ??
    (process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : process.env.VERCEL_URL
        ? `https://${process.env.VERCEL_URL}`
        : "http://localhost:3000");

  return new URL(rawUrl);
}

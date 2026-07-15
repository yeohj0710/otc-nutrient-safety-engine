export const siteName = "국내 일반의약품 안전성 조회 시스템";
export const siteTagline =
  "제품명으로 중복 성분·용량·간격·연령·질환·병용약 위험 신호를 확인하는 연구용 안내";
export const siteDescription =
  "국내 일반의약품의 허가 제품·성분·함량을 바탕으로 함께 복용하는 제품의 주요 위험 신호와 근거 출처를 확인하는 연구용 안전성 조회 사이트입니다.";
export const siteKeywords = [
  "일반의약품 안전성",
  "일반의약품 중복복용",
  "감기약 중복 성분",
  "해열진통제 최대용량",
  "NSAID 병용주의",
  "의약품안전나라 허가정보",
  "제품명 의약품 조회",
  "근거 추적형 안전성 조회",
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

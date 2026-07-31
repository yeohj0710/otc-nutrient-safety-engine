import type { Metadata } from "next";
import { ResearchV3Explorer } from "@/src/components/research-v3-explorer";
import { getResearchV3RuntimeMeta } from "@/src/lib/research-v3/engine";

// 이 화면은 AM-OTC-001 로 방향을 바꾸기 전의 계보 자료다. 현재 연구는 국내
// 일반의약품 중복복용이고 그 정보는 /research 에 있다. 지우지 않고 남기되,
// 현재 결과로 오해되지 않도록 제목과 화면에 계보임을 밝힌다.
export const metadata: Metadata = {
  title: "선행 계보 · 고함량 영양성분 기준 초안",
  description:
    "2026-07-27 개정 전 다루던 고함량 영양성분 기준 초안 화면. 현재 연구의 결과가 아닙니다.",
  robots: { index: false, follow: false },
};

export default function ResearchV3Page() {
  const meta = getResearchV3RuntimeMeta();
  return <ResearchV3Explorer meta={meta} />;
}

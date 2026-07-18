import type { Metadata } from "next";
import { ResearchV3Explorer } from "@/src/components/research-v3-explorer";
import { getResearchV3RuntimeMeta } from "@/src/lib/research-v3/engine";

export const metadata: Metadata = {
  title: "고함량 영양성분 기준 확인",
  description: "검토 중인 KDRI 기준 초안을 성분과 하루 총량으로 확인하는 연구 화면",
};

export default function ResearchV3Page() {
  const meta = getResearchV3RuntimeMeta();
  return <ResearchV3Explorer meta={meta} />;
}

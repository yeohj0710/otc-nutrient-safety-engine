import type { Metadata } from "next";
import { ResearchSummary } from "@/src/components/research-summary";

export const metadata: Metadata = {
  title: "연구 정보",
  description:
    "식약처 허가원문 결정층과 AI 선별 문헌층의 구성, 선별 교차 확인 결과, 규칙–문헌 연결 현황과 한계",
  alternates: { canonical: "/research" },
};

export default function ResearchPage() {
  return <ResearchSummary />;
}

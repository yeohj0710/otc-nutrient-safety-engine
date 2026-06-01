import type { MetadataRoute } from "next";

import { getKnowledgeIndex } from "@/src/lib/knowledge";
import { getSiteUrl } from "@/src/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const siteUrl = getSiteUrl();
  const knowledgeIndex = getKnowledgeIndex();

  return [
    {
      url: new URL("/", siteUrl).toString(),
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 1,
    },
    ...knowledgeIndex.safetyRules.map((rule) => ({
      url: new URL(`/rules/${rule.id}`, siteUrl).toString(),
      lastModified: rule.lastReviewedAt ?? new Date().toISOString(),
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
  ];
}

import type { MetadataRoute } from "next";

import { getSiteUrl } from "@/src/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const siteUrl = getSiteUrl();
  const lastModified = new Date();

  return [
    {
      url: new URL("/", siteUrl).toString(),
      lastModified,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: new URL("/research", siteUrl).toString(),
      lastModified,
      changeFrequency: "monthly",
      priority: 0.8,
    },
  ];
}

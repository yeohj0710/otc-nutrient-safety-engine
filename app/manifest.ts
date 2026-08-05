import type { MetadataRoute } from "next";

import { siteDescription, siteName } from "@/src/lib/site";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: siteName,
    short_name: "OTC 함께복용 점검",
    description: siteDescription,
    start_url: "/",
    display: "standalone",
    background_color: "#f3f5f7",
    theme_color: "#ffffff",
    lang: "ko-KR",
    icons: [
      {
        src: "/yonsei-logo.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}

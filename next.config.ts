import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  async redirects() {
    // Superseded research views remain in the repository for provenance.
    return ["/research-v3", "/ingredients/:path*", "/rules/:path*", "/sources/:path*"].map((source) => ({
      source,
      destination: "/research",
      permanent: true,
    }));
  },
};

export default nextConfig;

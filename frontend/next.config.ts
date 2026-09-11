import type { NextConfig } from "next";

// The browser only ever talks to this Next.js origin; /api/* is proxied to FastAPI server-side.
// Same-origin requests let the backend use an httpOnly, SameSite=Strict session cookie.
const API_URL = process.env.CAREFLOW_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: {
    // AI answers from a local CPU-bound LLM can take minutes; the default rewrite-proxy timeout would
    // drop the connection ("socket hang up") even though the backend completes successfully.
    proxyTimeout: 10 * 60 * 1000,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default nextConfig;

import type { NextConfig } from "next";

// Keep the deterministic engine / RAG / study core in Python. Next.js is the
// frontend; /api/* is proxied to the Flask API so the browser sees one origin.
const apiTarget = process.env.EPL_API_TARGET || "http://localhost:5000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }];
  },
};

export default nextConfig;

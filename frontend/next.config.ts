import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL;
    return backend ? [{source: '/api/v1/:path*', destination: `${backend.replace(/\/$/, '')}/api/v1/:path*`}] : [];
  },
  async headers() { return [{source: '/:path*', headers: [
    {key: 'X-Content-Type-Options', value: 'nosniff'},
    {key: 'Referrer-Policy', value: 'no-referrer'},
    {key: 'X-Frame-Options', value: 'DENY'},
  ]}]; },
  experimental: {
    agentFeedback: true,
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;

/**
 * Next.js config (CommonJS — package.json has no "type":"module").
 *
 * - `output: "standalone"` produces a self-contained server bundle for a small
 *   production Docker image (`node server.js`).
 * - `rewrites()` proxies the app's `/api/v1/*` calls to the FastAPI backend so
 *   the browser only ever talks to the frontend origin (no CORS). The target is
 *   read at server startup from API_PROXY_TARGET; defaults to localhost for dev.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    const target = process.env.API_PROXY_TARGET || "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${target}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

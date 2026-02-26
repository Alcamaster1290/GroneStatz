const path = require("path");
/** @type {import('next').NextConfig} */
const apiBase = process.env.NEXT_PUBLIC_API_URL || "/api";
const proxyTarget =
  apiBase.startsWith("http://") || apiBase.startsWith("https://")
    ? apiBase.replace(/\/$/, "")
    : "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  webpack(config) {
    config.resolve.alias["@"] = path.resolve(__dirname);
    return config;
  },
  async redirects() {
    return [
      {
        source: "/",
        destination: "/landing",
        permanent: true
      }
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${proxyTarget}/:path*`
      }
    ];
  }
};

module.exports = nextConfig;

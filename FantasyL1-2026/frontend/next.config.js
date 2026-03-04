const path = require("path");
/** @type {import('next').NextConfig} */
const apiBase = process.env.NEXT_PUBLIC_API_URL || "/api";
const mobileBuildProfile = (process.env.MOBILE_BUILD_PROFILE || "").toLowerCase();
const isMobileBundleBuild = mobileBuildProfile === "qa" || mobileBuildProfile === "prod";
const proxyTarget =
  apiBase.startsWith("http://") || apiBase.startsWith("https://")
    ? apiBase.replace(/\/$/, "")
    : "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  output: isMobileBundleBuild ? "export" : undefined,
  images: isMobileBundleBuild
    ? {
        unoptimized: true
      }
    : undefined,
  trailingSlash: isMobileBundleBuild,
  webpack(config) {
    config.resolve.alias["@"] = path.resolve(__dirname);
    return config;
  }
};

if (!isMobileBundleBuild) {
  nextConfig.redirects = async () => [
    {
      source: "/",
      destination: "/landing",
      permanent: true
    }
  ];

  nextConfig.rewrites = async () => [
    {
      source: "/api/:path*",
      destination: `${proxyTarget}/:path*`
    }
  ];
}

module.exports = nextConfig;

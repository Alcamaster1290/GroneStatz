import type { MetadataRoute } from "next";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL ||
  "https://www.fantasyliga1peru.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/landing", "/login", "/ranking", "/fixtures"],
        disallow: ["/admin", "/app", "/team", "/market", "/stats", "/settings", "/transfer"]
      }
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
    host: siteUrl
  };
}

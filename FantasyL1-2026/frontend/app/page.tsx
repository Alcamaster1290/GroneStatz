import type { Metadata } from "next";

import LandingTabs from "@/components/LandingTabs";

// Keep "/" rendered from server on every request to avoid stale ISR cache
// accidentally serving an old redirect response.
export const dynamic = "force-dynamic";
export const revalidate = 0;

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL ||
  "https://fantasyliga1peru.com";

const title = "Fantasy Liga 1 Perú 2026 | Landing oficial";
const description =
  "Juega Fantasy Liga 1 Perú 2026. Revisa el Top 10 público, planes Premium por rondas y entra al juego en segundos.";

export const metadata: Metadata = {
  title,
  description,
  alternates: {
    canonical: "/"
  },
  openGraph: {
    type: "website",
    url: "/",
    title,
    description
  },
  twitter: {
    card: "summary_large_image",
    title,
    description
  }
};

export default function Home() {
  const websiteJsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Fantasy Liga 1 Perú",
    url: siteUrl,
    inLanguage: "es-PE"
  };

  return (
    <>
      <div className="relative left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] w-screen">
        <div className="mx-auto w-full max-w-6xl px-4 md:px-8">
          <LandingTabs />
        </div>
      </div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
      />
    </>
  );
}

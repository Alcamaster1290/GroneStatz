import type { Metadata } from "next";

import LandingTabs from "@/components/LandingTabs";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL ||
  "https://fantasyliga1peru.com";

const title = "Fantasy Liga 1 Peru 2026 | Liga 1 Peru fantasy en vivo";
const description =
  "Juega Fantasy Liga 1 Peru 2026. Sigue el top publico, arma tu equipo y compite en el juego fantasy oficial de la Liga 1 Peru.";

export const metadata: Metadata = {
  title,
  description,
  keywords: [
    "liga 1 peru",
    "liga 1 peru 2026",
    "fantasy liga 1 peru",
    "liga 1 peru fantasy",
    "fantasy peru",
    "ranking liga 1 peru"
  ],
  alternates: {
    canonical: "/"
  },
  openGraph: {
    type: "website",
    url: "/",
    title,
    description,
    siteName: "Fantasy Liga 1 Peru"
  },
  twitter: {
    card: "summary_large_image",
    title,
    description
  }
};

export default function LandingPage() {
  const websiteJsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Fantasy Liga 1 Peru",
    alternateName: ["Liga 1 Peru Fantasy", "Liga 1 Peru 2026", "Fantasy Peru"],
    url: siteUrl,
    inLanguage: "es-PE",
    keywords: "liga 1 peru, liga 1 peru 2026, fantasy liga 1 peru, liga 1 peru fantasy"
  };

  const organizationJsonLd = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Fantasy Liga 1 Peru",
    url: siteUrl,
    logo: `${siteUrl}/logo.png`
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
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
      />
    </>
  );
}

import type { Metadata } from "next";

import LandingTabs from "@/components/LandingTabs";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL ||
  "https://fantasyliga1peru.com";

const title = "Fantasy Liga 1 Peru 2026 | Ranking y fixtures de la Liga 1 Peru";
const description =
  "Juega Fantasy Liga 1 Peru 2026. Revisa ranking, proximos partidos y compite en el fantasy oficial de la Liga 1 Peru.";

export const metadata: Metadata = {
  title,
  description,
  keywords: [
    "liga 1 peru",
    "liga 1 perú",
    "liga 1 peru 2026",
    "fantasy liga 1 peru",
    "fantasy liga 1 perú",
    "liga 1 peru fantasy",
    "fantasy peru",
    "ranking liga 1 peru",
    "fixture liga 1 peru",
    "futbol peruano"
  ],
  alternates: {
    canonical: "/landing"
  },
  openGraph: {
    type: "website",
    url: "/landing",
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

  const webApplicationJsonLd = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: "Fantasy Liga 1 Peru 2026",
    applicationCategory: "GameApplication",
    operatingSystem: "Web, Android, iOS",
    inLanguage: "es-PE",
    url: `${siteUrl}/landing`,
    description,
    keywords: "liga 1 peru, fantasy liga 1 peru, ranking liga 1 peru"
  };

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "¿Es gratis jugar?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Si. Solo registra un correo y contraseña y podras competir en el ranking general y ligas privadas con tus amigos."
        }
      },
      {
        "@type": "Question",
        name: "¿Cómo funciona el Mercado de jugadores?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "En Mercado eliges y compras tus 15 jugadores para la temporada, respetando el presupuesto inicial de 100 M y las reglas de composicion del plantel."
        }
      },
      {
        "@type": "Question",
        name: "¿Cómo obtienen puntos los jugadores?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "En 2026 se usan datos reales por fecha para calcular puntos como goles, asistencias, minutos, valla invicta y tarjetas. Estos puntos tambien actualizan el valor de mercado."
        }
      }
    ]
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
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(webApplicationJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
    </>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

import HomeAutoRedirect from "@/components/HomeAutoRedirect";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL ||
  "https://fantasyliga1peru.com";

const title = "Fantasy Liga 1 Peru 2026 | Juega Fantasy Gratis Online";
const description =
  "Fantasy Liga 1 Peru 2026 para armar tu equipo, competir por jornada y seguir estadisticas en vivo. Juega gratis desde web o movil.";

export const metadata: Metadata = {
  title,
  description,
  alternates: {
    canonical: "/"
  },
  keywords: [
    "fantasy liga 1 peru",
    "fantasy peru",
    "liga 1 peru fantasy",
    "juego fantasy futbol peru",
    "fantasy futbol peru 2026"
  ],
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

const faqItems = [
  {
    question: "Que es Fantasy Liga 1 Peru?",
    answer:
      "Es un juego fantasy donde eliges futbolistas de Liga 1 Peru y sumas puntos segun su rendimiento real en cada ronda."
  },
  {
    question: "Como empiezo a jugar?",
    answer:
      "Registra tu cuenta, arma un plantel de 15 jugadores, define tu once titular y haz cambios en el mercado antes del cierre de ronda."
  },
  {
    question: "Es gratis?",
    answer:
      "Si. Puedes jugar gratis, unirte a ligas privadas y competir en rankings generales por jornada."
  }
];

export default function Home() {
  const websiteJsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Fantasy Liga 1 Peru",
    url: siteUrl,
    inLanguage: "es-PE"
  };

  const appJsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Fantasy Liga 1 Peru 2026",
    applicationCategory: "SportsApplication",
    operatingSystem: "Web, Android, iOS",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "PEN"
    },
    url: siteUrl,
    inLanguage: "es-PE",
    description
  };

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqItems.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer
      }
    }))
  };

  return (
    <div className="space-y-8">
      <HomeAutoRedirect />

      <section className="glass rounded-3xl border border-white/10 p-5">
        <p className="text-xs uppercase tracking-[0.2em] text-muted">
          El unico Fantasy Manager del futbol peruano
        </p>
        <h1 className="mt-2 text-2xl font-semibold leading-tight text-ink">
          Fantasy Liga 1 Peru: arma tu equipo y compite cada jornada
        </h1>
        <p className="mt-3 text-sm text-muted">
          Crea tu plantilla, ajusta tu once titular y pelea en rankings con puntajes basados en
          partidos reales de Liga 1 Peru.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Link
            href="/team"
            className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
          >
            Entrar a jugar
          </Link>
          <Link
            href="/ranking"
            className="rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
          >
            Ver ranking
          </Link>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-ink">Como funciona</h2>
        <ol className="space-y-2 text-sm text-muted">
          <li>1. Elige 15 jugadores dentro del presupuesto.</li>
          <li>2. Define capitan, vicecapitan y once titular por ronda.</li>
          <li>3. Ajusta tu equipo en el mercado antes del cierre.</li>
          <li>4. Suma puntos y escala en ranking general y ligas privadas.</li>
        </ol>
      </section>

      <section className="grid gap-3 sm:grid-cols-2">
        <Link href="/market" className="glass rounded-2xl p-4 transition hover:border-white/20">
          <h2 className="text-sm font-semibold text-ink">Mercado</h2>
          <p className="mt-2 text-xs text-muted">
            Cambia jugadores y optimiza tu plantilla antes de cada fecha.
          </p>
        </Link>
        <Link href="/fixtures" className="glass rounded-2xl p-4 transition hover:border-white/20">
          <h2 className="text-sm font-semibold text-ink">Partidos y calendario</h2>
          <p className="mt-2 text-xs text-muted">
            Consulta rondas, horarios y resultados para planificar mejor.
          </p>
        </Link>
        <Link href="/stats" className="glass rounded-2xl p-4 transition hover:border-white/20">
          <h2 className="text-sm font-semibold text-ink">Estadisticas</h2>
          <p className="mt-2 text-xs text-muted">
            Revisa goles, asistencias, minutos y tendencias por jugador.
          </p>
        </Link>
        <Link href="/ranking" className="glass rounded-2xl p-4 transition hover:border-white/20">
          <h2 className="text-sm font-semibold text-ink">Ranking</h2>
          <p className="mt-2 text-xs text-muted">
            Compara tu rendimiento en la tabla general y en ligas privadas.
          </p>
        </Link>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-ink">Preguntas frecuentes</h2>
        <div className="space-y-2">
          {faqItems.map((item) => (
            <article key={item.question} className="glass rounded-2xl p-4">
              <h3 className="text-sm font-semibold text-ink">{item.question}</h3>
              <p className="mt-1 text-xs text-muted">{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(appJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
    </div>
  );
}

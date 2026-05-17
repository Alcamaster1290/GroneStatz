import type { Metadata } from "next";
import { Cormorant_Garamond, Source_Sans_3 } from "next/font/google";

import "./globals.css";

import AuthSessionBootstrap from "@/components/AuthSessionBootstrap";
import BottomNav from "@/components/BottomNav";
import MobileBootstrap from "@/components/MobileBootstrap";
import RouteAwareHeader from "@/components/RouteAwareHeader";
import ServiceWorkerRegister from "@/components/ServiceWorkerRegister";
import UiRedesignRouteGate from "@/components/UiRedesignRouteGate";

const displayFont = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-display"
});

const bodyFont = Source_Sans_3({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body"
});

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL ||
  "https://www.fantasyliga1peru.com";
const siteTitle = "Fantasy Liga 1 Peru 2026 | Fantasy oficial de la Liga 1 Peru";
const siteDescription =
  "Liga 1 Peru 2026 en formato fantasy: arma tu equipo, juega ranking general y ligas privadas con datos reales de cada fecha del futbol peruano.";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: siteTitle,
  description: siteDescription,
  applicationName: "Fantasy Liga 1 Peru 2026",
  manifest: "/manifest.json",
  keywords: [
    "liga 1 peru",
    "liga 1 perú",
    "liga 1 peru 2026",
    "liga 1",
    "liga peruana",
    "liga 1 peru fantasy",
    "fantasy liga 1 peru",
    "fantasy liga 1 perú",
    "fantasy peru 2026",
    "futbol peruano",
    "ranking liga 1 peru",
    "juego fantasy liga 1",
    "liga1 peru"
  ],
  alternates: {
    canonical: "/"
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1
    }
  },
  icons: {
    icon: "/favicon.png",
    apple: "/apple-touch-icon.png"
  },
  openGraph: {
    type: "website",
    url: "/",
    title: siteTitle,
    description: siteDescription,
    siteName: "Fantasy Liga 1 Peru",
    locale: "es_PE",
    images: [
      {
        url: "/logo.png",
        width: 1200,
        height: 630,
        alt: "Fantasy Liga 1 Peru"
      }
    ]
  },
  twitter: {
    card: "summary_large_image",
    title: siteTitle,
    description: siteDescription,
    images: ["/logo.png"]
  }
};

export const viewport = {
  themeColor: "#1b1110"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className={`${displayFont.variable} ${bodyFont.variable} text-ink`}>
        <UiRedesignRouteGate />
        <AuthSessionBootstrap />
        <div className="relative min-h-screen pb-24">
          <div className="pointer-events-none absolute inset-0 opacity-30">
            <div className="absolute -top-24 left-4 h-48 w-48 rounded-full bg-accent opacity-20 blur-3xl" />
            <div className="absolute top-40 right-10 h-64 w-64 rounded-full bg-accent2 opacity-20 blur-3xl" />
          </div>
          <main className="relative mx-auto w-full max-w-md px-4 pb-16 pt-6">
            <RouteAwareHeader />
            {children}
          </main>
        </div>
        <ServiceWorkerRegister />
        <MobileBootstrap />
        <BottomNav />
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

import BottomNav from "@/components/BottomNav";
import RouteAwareHeader from "@/components/RouteAwareHeader";
import ServiceWorkerRegister from "@/components/ServiceWorkerRegister";
import MobileBootstrap from "@/components/MobileBootstrap";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL ||
  "https://fantasyliga1peru.com";
const siteTitle = "Fantasy Liga 1 Perú 2026 | El único Fantasy Manager del fútbol peruano";
const siteDescription =
  "Arma tu equipo, juega en ligas y compite en el Fantasy Liga 1 Perú 2026. Mercado dinámico, estadísticas en vivo y rankings por jornada.";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: siteTitle,
  description: siteDescription,
  applicationName: "Fantasy Liga 1 Perú 2026",
  manifest: "/manifest.json",
  keywords: [
    "fantasy liga 1 perú",
    "liga 1 perú fantasy",
    "fantasy fútbol perú",
    "fantasy perú 2026"
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
    siteName: "Fantasy Liga 1 Perú",
    locale: "es_PE",
    images: [
      {
        url: "/logo.png",
        width: 1200,
        height: 630,
        alt: "Fantasy Liga 1 Perú"
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
  themeColor: "#0b0b0f"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="text-ink">
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

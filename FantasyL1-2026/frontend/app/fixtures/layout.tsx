import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Rondas y Fixtures Liga 1 Peru 2026 | Fantasy Liga 1 Peru",
  description:
    "Revisa calendario, resultados y estadisticas de rondas de la Liga 1 Peru 2026 en Fantasy Liga 1 Peru.",
  alternates: {
    canonical: "/fixtures"
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true
    }
  }
};

export default function PrivateRouteLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

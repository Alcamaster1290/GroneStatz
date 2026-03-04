import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ranking Liga 1 Peru 2026 | Fantasy Liga 1 Peru",
  description:
    "Consulta el ranking general y las ligas privadas del Fantasy Liga 1 Peru 2026 con datos reales por fecha.",
  alternates: {
    canonical: "/ranking"
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

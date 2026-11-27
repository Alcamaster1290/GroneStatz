import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import Header from "@/components/Header";
import { getJson } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { ReleaseInfo } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "GroneStats", template: "%s · GroneStats" },
  description: "Análisis de la Liga 1 del Perú: tabla, probabilidad de título, xG, formaciones y jugadores.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const release = await getJson<ReleaseInfo>("/v1/release");
  return (
    <html lang="es">
      <body className="min-h-screen bg-bg font-sans text-ink antialiased">
        <Header />
        <main className="mx-auto w-full max-w-7xl px-4 py-6">{children}</main>
        <footer className="mx-auto w-full max-w-7xl px-4 pb-10 pt-4 text-xs text-muted">
          <p>
            Datos hasta el {formatDate(release.data_as_of)} (hora de Lima) · release <span className="num">{release.release_id}</span> ·{" "}
            <Link href="/estado" className="underline">
              estado de los datos
            </Link>
          </p>
        </footer>
      </body>
    </html>
  );
}

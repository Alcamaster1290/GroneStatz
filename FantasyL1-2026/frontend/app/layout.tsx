import type { Metadata } from "next";
import "./globals.css";

import BottomNav from "@/components/BottomNav";
import ServiceWorkerRegister from "@/components/ServiceWorkerRegister";

export const metadata: Metadata = {
  title: "Fantasy Liga 1 2026",
  description: "Fantasy Liga 1 2026 v1.0",
  manifest: "/manifest.json"
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
            {children}
          </main>
        </div>
        <ServiceWorkerRegister />
        <BottomNav />
      </body>
    </html>
  );
}

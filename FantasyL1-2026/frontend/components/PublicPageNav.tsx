"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { hydrateSessionFromStorage } from "@/lib/session";
import { useFantasyStore } from "@/lib/store";

type PublicNavItem = {
  href: string;
  match: string;
  label: string;
};

export default function PublicPageNav() {
  const pathname = usePathname() || "/";
  const token = useFantasyStore((state) => state.token);

  useEffect(() => {
    if (!token) {
      hydrateSessionFromStorage();
    }
  }, [token]);

  const navItems: PublicNavItem[] = token
    ? [
        { href: "/app", match: "/app", label: "JUGAR" },
        { href: "/ranking", match: "/ranking", label: "Ranking" },
        { href: "/fixtures", match: "/fixtures", label: "Rondas" }
      ]
    : [
        { href: "/landing", match: "/landing", label: "Landing" },
        { href: "/ranking", match: "/ranking", label: "Ranking" },
        { href: "/fixtures", match: "/fixtures", label: "Rondas" },
        { href: "/login?redirect=/app", match: "/login", label: "JUEGA YA" }
      ];

  const isPlayActive = (currentPath: string) =>
    ["/app", "/team", "/market", "/stats", "/settings", "/transfer"].some(
      (path) => currentPath === path || currentPath.startsWith(`${path}/`)
    );

  return (
    <nav className="overflow-x-auto rounded-2xl border border-white/10 bg-black/25 p-2">
      <div className="flex min-w-max items-center gap-2">
        {navItems.map((item) => {
          const isActive =
            item.match === "/app"
              ? isPlayActive(pathname)
              : pathname === item.match || pathname.startsWith(`${item.match}/`);
          return (
            <Link
              key={item.match}
              href={item.href}
              className={
                "rounded-full border px-3 py-1 text-xs transition " +
                (isActive
                  ? "border-accent/60 bg-accent/15 text-accent"
                  : "border-white/10 text-muted hover:border-white/30 hover:text-ink")
              }
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

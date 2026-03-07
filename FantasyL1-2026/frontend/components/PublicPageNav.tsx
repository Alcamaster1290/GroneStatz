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
        { href: "/landing", match: "/landing", label: "Inicio" },
        { href: "/ranking", match: "/ranking", label: "Ranking" },
        { href: "/fixtures", match: "/fixtures", label: "Rondas" },
        { href: "/login?redirect=/app", match: "/login", label: "JUEGA YA" }
      ];

  const isPlayActive = (currentPath: string) =>
    ["/app", "/team", "/market", "/stats", "/settings", "/transfer"].some(
      (path) => currentPath === path || currentPath.startsWith(`${path}/`)
    );

  return (
    <nav className="ui-panel overflow-x-auto p-2">
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
                "ui-btn rounded-full px-3 py-1.5 text-[11px] transition " +
                (isActive ? "ui-btn-primary" : "ui-btn-secondary")
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

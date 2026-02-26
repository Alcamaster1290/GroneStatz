"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { useFantasyStore } from "@/lib/store";

type PublicNavItem = {
  href: string;
  match: string;
  label: string;
};

export default function PublicPageNav() {
  const pathname = usePathname() || "/";
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);

  useEffect(() => {
    if (token) return;
    const storedToken = localStorage.getItem("fantasy_token");
    const storedEmail = localStorage.getItem("fantasy_email");
    if (storedToken) {
      setToken(storedToken);
      if (storedEmail) {
        setUserEmail(storedEmail);
      }
    }
  }, [token, setToken, setUserEmail]);

  const playHref = token ? "/app" : "/login?redirect=/app";
  const navItems: PublicNavItem[] = pathname.startsWith("/login")
    ? [
        { href: "/landing", match: "/landing", label: "Landing" },
        { href: "/ranking", match: "/ranking", label: "Ranking" },
        { href: "/fixtures", match: "/fixtures", label: "Rondas" }
      ]
    : [
        { href: playHref, match: token ? "/app" : "/login", label: "JUGAR" },
        { href: "/ranking", match: "/ranking", label: "Ranking" },
        { href: "/fixtures", match: "/fixtures", label: "Rondas" }
      ];

  return (
    <nav className="overflow-x-auto rounded-2xl border border-white/10 bg-black/25 p-2">
      <div className="flex min-w-max items-center gap-2">
        {navItems.map((item) => {
          const isActive = pathname === item.match;
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

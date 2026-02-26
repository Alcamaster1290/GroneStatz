"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type PublicNavItem = {
  href: string;
  match: string;
  label: string;
};

const PUBLIC_NAV_ITEMS: PublicNavItem[] = [
  { href: "/", match: "/", label: "Landing" },
  { href: "/login?redirect=/app", match: "/login", label: "Login" },
  { href: "/ranking", match: "/ranking", label: "Ranking" },
  { href: "/fixtures", match: "/fixtures", label: "Rondas" }
];

export default function PublicPageNav() {
  const pathname = usePathname() || "/";

  return (
    <nav className="overflow-x-auto rounded-2xl border border-white/10 bg-black/25 p-2">
      <div className="flex min-w-max items-center gap-2">
        {PUBLIC_NAV_ITEMS.map((item) => {
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

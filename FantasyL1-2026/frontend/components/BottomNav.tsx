"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, Calendar, Home, Settings, ShoppingBag, Trophy } from "lucide-react";

import { useFantasyStore } from "@/lib/store";

const items = [
  { href: "/team", label: "Equipo", icon: Home, requiresAuth: true },
  { href: "/market", label: "Mercado", icon: ShoppingBag, requiresAuth: true },
  { href: "/stats", label: "Estadisticas", icon: BarChart3, requiresAuth: true },
  { href: "/ranking", label: "Ranking", icon: Trophy, requiresAuth: false },
  { href: "/fixtures", label: "Rondas", icon: Calendar, requiresAuth: false },
  { href: "/settings", label: "Ajustes", icon: Settings, requiresAuth: true }
];

export default function BottomNav() {
  const pathname = usePathname();
  const router = useRouter();
  const token = useFantasyStore((state) => state.token);

  if (pathname === "/" || pathname === "/landing" || pathname.startsWith("/login")) {
    return null;
  }

  const handleClick = (e: React.MouseEvent, href: string, requiresAuth: boolean) => {
    if (requiresAuth && !token) {
      e.preventDefault();
      router.push("/ranking");
    }
  };

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/10 bg-black/75 backdrop-blur-sm">
      <div className="mx-auto flex max-w-md items-center justify-between px-4 pb-3 pt-2.5 text-[11px]">
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          const Icon = item.icon;
          const disabled = item.requiresAuth && !token;

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={(e) => handleClick(e, item.href, item.requiresAuth)}
              className={
                "ui-btn flex min-w-[52px] flex-col items-center gap-1 rounded-xl px-2 py-1.5 transition " +
                (active
                  ? "ui-btn-primary"
                  : disabled
                    ? "cursor-not-allowed border border-white/10 text-white/30"
                    : "ui-btn-secondary")
              }
            >
              <Icon size={16} />
              <span className="leading-none">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

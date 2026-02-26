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

  if (pathname === "/" || pathname.startsWith("/login")) {
    return null;
  }

  const handleClick = (e: React.MouseEvent, href: string, requiresAuth: boolean) => {
    if (requiresAuth && !token) {
      e.preventDefault();
      router.push("/ranking");
    }
  };

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/10 bg-black/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-md items-center justify-between px-6 py-3 text-xs">
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
                "flex flex-col items-center gap-1 transition " +
                (active
                  ? "text-accent"
                  : disabled
                    ? "text-white/20 cursor-not-allowed"
                    : "text-muted hover:text-white/80")
              }
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

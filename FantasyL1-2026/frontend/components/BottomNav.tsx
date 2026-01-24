"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Calendar, Home, Settings, ShoppingBag } from "lucide-react";

const items = [
  { href: "/team", label: "Equipo", icon: Home },
  { href: "/market", label: "Mercado", icon: ShoppingBag },
  { href: "/fixtures", label: "Rondas", icon: Calendar },
  { href: "/settings", label: "Ajustes", icon: Settings }
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/10 bg-black/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-md items-center justify-between px-6 py-3 text-xs">
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={
                "flex flex-col items-center gap-1 transition " +
                (active ? "text-accent" : "text-muted")
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

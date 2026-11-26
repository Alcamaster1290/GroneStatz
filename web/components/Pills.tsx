import Link from "next/link";

export interface PillItem {
  label: string;
  href: string;
  active: boolean;
}

/** Selector de enlaces (temporada, torneo, fecha): se renderiza en el servidor, sin JavaScript. */
export default function Pills({ items, label }: { items: PillItem[]; label: string }) {
  return (
    <nav aria-label={label} className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={item.active ? "page" : undefined}
          className={`rounded-full border px-3 py-1 text-sm transition-colors ${
            item.active ? "border-accent bg-accent font-semibold text-white" : "border-line bg-surface text-muted hover:text-ink"
          }`}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}

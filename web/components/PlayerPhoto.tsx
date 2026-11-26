import { asset } from "@/lib/api";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** Foto del jugador; si SofaScore no la tiene, las iniciales sobre el color del equipo. */
export default function PlayerPhoto({ name, photo, color, size = 40 }: { name: string; photo: string | null; color?: string | null; size?: number }) {
  const src = asset(photo);
  const box = { width: size, height: size };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={name} loading="lazy" className="shrink-0 rounded-full bg-line object-cover" style={box} />;
  }
  return (
    <span
      role="img"
      aria-label={name}
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{ ...box, background: color ?? "var(--draw)", fontSize: Math.max(10, size * 0.34) }}
    >
      {initials(name)}
    </span>
  );
}

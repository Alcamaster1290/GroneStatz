import { asset } from "@/lib/api";
import type { Team } from "@/lib/types";

type TeamLike = Pick<Team, "name" | "color" | "crest">;

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** Escudo del equipo; sin archivo, un círculo con sus iniciales en el color del club. */
export default function Crest({ team, size = 28 }: { team: TeamLike | null; size?: number }) {
  const src = asset(team?.crest);
  const box = { width: size, height: size };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt="" loading="lazy" className="shrink-0 object-contain" style={box} />;
  }
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-full font-bold text-white"
      style={{ ...box, background: team?.color ?? "var(--draw)", fontSize: Math.max(9, size * 0.36) }}
    >
      {initials(team?.name ?? "?")}
    </span>
  );
}

import { number } from "@/lib/format";
import { HALF, OPTA, shotToHalfPitch } from "@/lib/pitch";

export interface ShotPoint {
  x: number | null;
  y: number | null;
  xg: number | null;
  is_goal: boolean;
  minute?: number | null;
  label?: string | null;
}

const METERS_WIDTH = 68;
const METERS_HALF_LENGTH = 52.5;

/**
 * Mapa de tiros sobre la media cancha ofensiva, con el arco arriba. En los datos `x` es la distancia a la línea de fondo del arco
 * que se ataca (igual para local y visita), así que los tiros de un equipo siempre caen sobre el mismo arco. El tamaño es el xG.
 */
export default function ShotMap({ shots, width = 340, caption }: { shots: ShotPoint[]; width?: number; caption: string }) {
  const height = (width * METERS_HALF_LENGTH) / METERS_WIDTH;
  const ky = width / 100;
  const kx = height / HALF;
  const line = "var(--pitch-line)";
  const cx = 50 * ky;
  const arcRadius = (9.15 * width) / METERS_WIDTH;
  const boxBottom = OPTA.box.depth * kx;
  const spotY = OPTA.spot * kx;
  const halfChord = Math.sqrt(Math.max(arcRadius ** 2 - (boxBottom - spotY) ** 2, 0));
  const plotted = shots.filter((shot) => shot.x !== null && shot.y !== null);
  const goals = plotted.filter((shot) => shot.is_goal).length;
  const xgTotal = plotted.reduce((sum, shot) => sum + (shot.xg ?? 0), 0);

  return (
    <figure className="m-0">
      <svg viewBox={`-6 -12 ${width + 12} ${height + 18}`} role="img" aria-label={caption} className="h-auto w-full max-w-[420px]">
        <rect x={0} y={0} width={width} height={height} fill="var(--pitch)" stroke={line} strokeWidth={1.5} />
        <rect x={OPTA.box.y0 * ky} y={0} width={(OPTA.box.y1 - OPTA.box.y0) * ky} height={boxBottom} fill="none" stroke={line} strokeWidth={1.5} />
        <rect x={OPTA.six.y0 * ky} y={0} width={(OPTA.six.y1 - OPTA.six.y0) * ky} height={OPTA.six.depth * kx} fill="none" stroke={line} strokeWidth={1.5} />
        <line x1={OPTA.goal.y0 * ky} x2={OPTA.goal.y1 * ky} y1={-3} y2={-3} stroke="var(--ink)" strokeWidth={4} strokeLinecap="round" />
        <circle cx={cx} cy={spotY} r={2} fill={line} />
        <path d={`M ${cx - halfChord} ${boxBottom} A ${arcRadius} ${arcRadius} 0 0 0 ${cx + halfChord} ${boxBottom}`} fill="none" stroke={line} strokeWidth={1.5} />
        <path d={`M ${cx - arcRadius} ${height} A ${arcRadius} ${arcRadius} 0 0 1 ${cx + arcRadius} ${height}`} fill="none" stroke={line} strokeWidth={1.5} />
        {plotted.map((shot, index) => {
          const { cx: px, cy: py } = shotToHalfPitch(shot.x as number, shot.y as number, width, height);
          const radius = 3 + 13 * Math.sqrt(Math.min(shot.xg ?? 0.04, 1));
          const text = `${shot.minute !== null && shot.minute !== undefined ? `${shot.minute}' · ` : ""}xG ${number(shot.xg, 2)}${shot.is_goal ? " · gol" : ""}${shot.label ? ` · ${shot.label}` : ""}`;
          return (
            <circle
              key={index}
              cx={px}
              cy={py}
              r={radius}
              fill="var(--accent)"
              fillOpacity={shot.is_goal ? 0.95 : 0.22}
              stroke={shot.is_goal ? "var(--ink)" : "var(--accent)"}
              strokeWidth={shot.is_goal ? 1.6 : 1}
            >
              <title>{text}</title>
            </circle>
          );
        })}
      </svg>
      <figcaption className="mt-1 text-xs text-muted">
        {caption} · <span className="num">{plotted.length}</span> {plotted.length === 1 ? "tiro" : "tiros"} · <span className="num">{goals}</span> {goals === 1 ? "gol" : "goles"} · xG <span className="num">{number(xgTotal, 2)}</span>. Círculo lleno = gol; tamaño = xG.
      </figcaption>
    </figure>
  );
}

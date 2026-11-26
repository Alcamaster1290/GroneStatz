import { OPTA, heatCell } from "@/lib/pitch";

const WIDTH = 525;
const HEIGHT = 340;

/**
 * Dónde jugó: cuadrícula de los puntos del heatmap sobre la cancha completa, atacando hacia la derecha
 * (en los datos `x` va de 0 en el arco propio a 100 en el rival). La opacidad crece con la raíz de los puntos de cada celda.
 */
export default function Heatmap({ cells, cols, rows, total, matches, caption }: { cells: { ix: number; iy: number; n: number }[]; cols: number; rows: number; total: number; matches: number; caption: string }) {
  const max = Math.max(...cells.map((cell) => cell.n), 1);
  const kx = WIDTH / 100;
  const ky = HEIGHT / 100;
  const line = "var(--pitch-line)";
  const centerRadius = (9.15 * WIDTH) / 105;
  const side = (flip: boolean) => {
    const edge = flip ? WIDTH : 0;
    const dir = flip ? -1 : 1;
    return (
      <g key={flip ? "right" : "left"}>
        <rect x={flip ? WIDTH - OPTA.box.depth * kx : 0} y={OPTA.box.y0 * ky} width={OPTA.box.depth * kx} height={(OPTA.box.y1 - OPTA.box.y0) * ky} fill="none" stroke={line} strokeWidth={1.5} />
        <rect x={flip ? WIDTH - OPTA.six.depth * kx : 0} y={OPTA.six.y0 * ky} width={OPTA.six.depth * kx} height={(OPTA.six.y1 - OPTA.six.y0) * ky} fill="none" stroke={line} strokeWidth={1.5} />
        <line x1={edge - dir * 3} x2={edge - dir * 3} y1={OPTA.goal.y0 * ky} y2={OPTA.goal.y1 * ky} stroke="var(--ink)" strokeWidth={4} strokeLinecap="round" />
        <circle cx={edge + dir * OPTA.spot * kx} cy={HEIGHT / 2} r={2} fill={line} />
      </g>
    );
  };

  return (
    <figure className="m-0">
      <svg viewBox={`-8 -4 ${WIDTH + 16} ${HEIGHT + 22}`} role="img" aria-label={caption} className="h-auto w-full max-w-[640px]">
        <rect x={0} y={0} width={WIDTH} height={HEIGHT} fill="var(--pitch)" />
        {cells.map((cell) => {
          const rect = heatCell(cell.ix, cell.iy, cols, rows, WIDTH, HEIGHT);
          return (
            <rect key={`${cell.ix}-${cell.iy}`} {...rect} fill="var(--accent)" fillOpacity={Math.min(0.92, Math.sqrt(cell.n / max) * 0.92)}>
              <title>{`${cell.n} puntos`}</title>
            </rect>
          );
        })}
        <rect x={0} y={0} width={WIDTH} height={HEIGHT} fill="none" stroke={line} strokeWidth={1.5} />
        <line x1={WIDTH / 2} x2={WIDTH / 2} y1={0} y2={HEIGHT} stroke={line} strokeWidth={1.5} />
        <circle cx={WIDTH / 2} cy={HEIGHT / 2} r={centerRadius} fill="none" stroke={line} strokeWidth={1.5} />
        {side(false)}
        {side(true)}
        <text x={WIDTH / 2} y={HEIGHT + 15} textAnchor="middle" fontSize={11} fill="var(--muted)">
          dirección de ataque →
        </text>
      </svg>
      <figcaption className="mt-1 text-xs text-muted">
        {caption} · <span className="num">{total.toLocaleString("es-PE")}</span> puntos de <span className="num">{matches}</span> partidos.
      </figcaption>
    </figure>
  );
}

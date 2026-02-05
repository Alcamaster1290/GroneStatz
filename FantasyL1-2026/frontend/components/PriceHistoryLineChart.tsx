import { useMemo } from "react";

import { PlayerPriceHistoryPoint } from "@/lib/types";

type PriceHistoryLineChartProps = {
  points: PlayerPriceHistoryPoint[];
};

const WIDTH = 640;
const HEIGHT = 240;
const PADDING = {
  top: 16,
  right: 18,
  bottom: 32,
  left: 42
};

const formatPrice = (value: number) => value.toFixed(1);

export default function PriceHistoryLineChart({ points }: PriceHistoryLineChartProps) {
  const sortedPoints = useMemo(
    () => [...points].sort((a, b) => a.round_number - b.round_number),
    [points]
  );

  if (sortedPoints.length === 0) {
    return null;
  }

  const prices = sortedPoints.map((point) => point.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const spread = maxPrice - minPrice;
  const extra = spread > 0 ? spread * 0.2 : 1;
  const domainMin = minPrice - extra;
  const domainMax = maxPrice + extra;
  const domainSpan = domainMax - domainMin || 1;

  const chartWidth = WIDTH - PADDING.left - PADDING.right;
  const chartHeight = HEIGHT - PADDING.top - PADDING.bottom;

  const getX = (index: number) => {
    if (sortedPoints.length === 1) {
      return PADDING.left + chartWidth / 2;
    }
    return PADDING.left + (index / (sortedPoints.length - 1)) * chartWidth;
  };
  const getY = (value: number) => {
    return PADDING.top + ((domainMax - value) / domainSpan) * chartHeight;
  };

  const linePoints = sortedPoints.map((point, index) => `${getX(index)},${getY(point.price)}`).join(" ");

  const yTicks = 4;
  const yGuides = Array.from({ length: yTicks + 1 }, (_, idx) => {
    const ratio = idx / yTicks;
    const value = domainMax - ratio * domainSpan;
    const y = PADDING.top + ratio * chartHeight;
    return {
      key: `y-${idx}`,
      y,
      label: formatPrice(value)
    };
  });

  const maxLabels = 6;
  const xStep = Math.max(1, Math.ceil(sortedPoints.length / maxLabels));
  const xTickIndexes = new Set<number>();
  for (let index = 0; index < sortedPoints.length; index += xStep) {
    xTickIndexes.add(index);
  }
  xTickIndexes.add(0);
  xTickIndexes.add(sortedPoints.length - 1);

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
        <svg
          className="h-auto w-full"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label="Evolucion de precio por ronda"
        >
          {yGuides.map((guide) => (
            <g key={guide.key}>
              <line
                x1={PADDING.left}
                y1={guide.y}
                x2={WIDTH - PADDING.right}
                y2={guide.y}
                stroke="rgba(255,255,255,0.12)"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
              <text
                x={PADDING.left - 8}
                y={guide.y + 4}
                textAnchor="end"
                fill="rgba(255,255,255,0.62)"
                fontSize="11"
              >
                {guide.label}
              </text>
            </g>
          ))}

          <polyline
            fill="none"
            points={linePoints}
            stroke="#f2c94c"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {sortedPoints.map((point, index) => {
            const x = getX(index);
            const y = getY(point.price);
            const showTick = xTickIndexes.has(index);
            return (
              <g key={`${point.round_number}-${index}`}>
                <circle cx={x} cy={y} r="4" fill="#120708" stroke="#5de0a5" strokeWidth="2" />
                {showTick ? (
                  <text
                    x={x}
                    y={HEIGHT - 10}
                    textAnchor="middle"
                    fill="rgba(255,255,255,0.75)"
                    fontSize="11"
                  >
                    R{point.round_number}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        {sortedPoints.map((point) => (
          <div key={`legend-${point.round_number}`} className="rounded-xl border border-white/10 bg-black/20 px-3 py-2">
            <p className="text-muted">Ronda {point.round_number}</p>
            <p className="font-semibold text-accent">{formatPrice(point.price)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

import { MarketFiltersState, Position } from "@/lib/types";

const POSITIONS: { value: Position; label: string }[] = [
  { value: "G", label: "Arquero" },
  { value: "D", label: "Defensa" },
  { value: "M", label: "Medio" },
  { value: "F", label: "Ataque" }
];

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const parseMaybeNumber = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

export default function MarketFilters({
  value,
  onChange,
  priceBounds,
  teams
}: {
  value: MarketFiltersState;
  onChange: (next: MarketFiltersState) => void;
  priceBounds?: { min: number; max: number };
  teams?: { id: number; name_short?: string; name_full?: string }[];
}) {
  const minBound = Number.isFinite(priceBounds?.min) ? priceBounds!.min : 0;
  const maxBound = Number.isFinite(priceBounds?.max) ? priceBounds!.max : 100;

  const handleTogglePosition = (position: Position) => {
    const next = value.positions.includes(position)
      ? value.positions.filter((item) => item !== position)
      : [...value.positions, position];
    onChange({ ...value, positions: next });
  };

  const handleMinChange = (raw: string) => {
    if (!raw.trim()) {
      onChange({ ...value, minPrice: "" });
      return;
    }
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return;
    const nextMin = clamp(Math.round(parsed * 10) / 10, minBound, maxBound);
    const currentMax = parseMaybeNumber(value.maxPrice);
    const nextMax = currentMax !== null ? Math.max(nextMin, currentMax) : maxBound;
    onChange({ ...value, minPrice: nextMin.toFixed(1), maxPrice: nextMax.toFixed(1) });
  };

  const handleMaxChange = (raw: string) => {
    if (!raw.trim()) {
      onChange({ ...value, maxPrice: "" });
      return;
    }
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return;
    const currentMin = parseMaybeNumber(value.minPrice);
    const safeMin = currentMin !== null ? currentMin : minBound;
    const nextMax = clamp(Math.round(parsed * 10) / 10, safeMin, maxBound);
    onChange({ ...value, maxPrice: nextMax.toFixed(1) });
  };

  const stepPrice = (raw: string, delta: number, boundMin: number, boundMax: number) => {
    const current = parseMaybeNumber(raw);
    const base = current !== null ? current : boundMin;
    const next = clamp(Math.round((base + delta) * 10) / 10, boundMin, boundMax);
    return next.toFixed(1);
  };

  const handleStepMin = (delta: number) => {
    const nextMin = stepPrice(value.minPrice, delta, minBound, maxBound);
    const currentMax = parseMaybeNumber(value.maxPrice);
    const nextMax = currentMax !== null ? Math.max(Number(nextMin), currentMax) : maxBound;
    onChange({ ...value, minPrice: nextMin, maxPrice: nextMax.toFixed(1) });
  };

  const handleStepMax = (delta: number) => {
    const minVal = parseMaybeNumber(value.minPrice);
    const safeMin = minVal !== null ? minVal : minBound;
    const nextMax = stepPrice(value.maxPrice, delta, safeMin, maxBound);
    onChange({ ...value, maxPrice: nextMax });
  };

  return (
    <div className="glass mb-4 space-y-3 rounded-2xl p-4">
      <input
        value={value.query}
        onChange={(event) => onChange({ ...value, query: event.target.value })}
        placeholder="Busqueda por nombre"
        className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
      />
      <div className="space-y-2">
        <p className="text-xs text-muted">Equipo</p>
        <select
          value={value.teamId}
          onChange={(event) => onChange({ ...value, teamId: event.target.value })}
          className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
        >
          <option value="">Todos</option>
          {(teams || []).map((team) => (
            <option key={team.id} value={String(team.id)}>
              {team.name_short || team.name_full || `Equipo ${team.id}`}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-2">
        <p className="text-xs text-muted">Posicion</p>
        <div className="flex flex-wrap gap-2">
          {POSITIONS.map((position) => {
            const active = value.positions.includes(position.value);
            return (
              <button
                key={position.value}
                type="button"
                onClick={() => handleTogglePosition(position.value)}
                className={
                  "rounded-full px-3 py-1 text-xs " +
                  (active
                    ? "bg-accent text-black"
                    : "border border-white/15 text-muted")
                }
              >
                {position.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <label className="text-xs text-muted">Precio min</label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleStepMin(-0.1)}
              className="h-9 w-9 rounded-xl border border-white/10 text-sm text-ink"
            >
              -
            </button>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              min={minBound}
              max={maxBound}
              value={value.minPrice}
              onChange={(event) => handleMinChange(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
            />
            <button
              type="button"
              onClick={() => handleStepMin(0.1)}
              className="h-9 w-9 rounded-xl border border-white/10 text-sm text-ink"
            >
              +
            </button>
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted">Precio max</label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleStepMax(-0.1)}
              className="h-9 w-9 rounded-xl border border-white/10 text-sm text-ink"
            >
              -
            </button>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              min={Number(value.minPrice) || minBound}
              max={maxBound}
              value={value.maxPrice}
              onChange={(event) => handleMaxChange(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
            />
            <button
              type="button"
              onClick={() => handleStepMax(0.1)}
              className="h-9 w-9 rounded-xl border border-white/10 text-sm text-ink"
            >
              +
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

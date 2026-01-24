import { useMemo } from "react";

import { MarketFiltersState } from "@/lib/types";

export default function MarketFilters({
  teams,
  value,
  onChange
}: {
  teams: { id: number; name_short?: string | null; name_full?: string | null }[];
  value: MarketFiltersState;
  onChange: (next: MarketFiltersState) => void;
}) {
  const teamOptions = useMemo(
    () =>
      teams.map((team) => ({
        value: String(team.id),
        label: team.name_short || team.name_full || `Team ${team.id}`
      })),
    [teams]
  );

  return (
    <div className="glass mb-4 space-y-3 rounded-2xl p-4">
      <input
        value={value.query}
        onChange={(event) => onChange({ ...value, query: event.target.value })}
        placeholder="Buscar jugador"
        className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
      />
      <div className="grid grid-cols-2 gap-2">
        <select
          value={value.position}
          onChange={(event) => onChange({ ...value, position: event.target.value })}
          className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
        >
          <option value="">Posicion</option>
          <option value="G">Arquero</option>
          <option value="D">Defensa</option>
          <option value="M">Medio</option>
          <option value="F">Ataque</option>
        </select>
        <select
          value={value.teamId}
          onChange={(event) => onChange({ ...value, teamId: event.target.value })}
          className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
        >
          <option value="">Equipo</option>
          {teamOptions.map((team) => (
            <option key={team.value} value={team.value}>
              {team.label}
            </option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input
          value={value.minPrice}
          onChange={(event) => onChange({ ...value, minPrice: event.target.value })}
          placeholder="Precio min"
          className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
        />
        <input
          value={value.maxPrice}
          onChange={(event) => onChange({ ...value, maxPrice: event.target.value })}
          placeholder="Precio max"
          className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-ink"
        />
      </div>
    </div>
  );
}

import type { Metadata } from "next";
import { getJson } from "@/lib/api";
import { formatDate, number } from "@/lib/format";
import type { CoverageRow, ModelRun, Status } from "@/lib/types";

export const metadata: Metadata = { title: "Estado de los datos" };

const KINDS: [string, string][] = [
  ["detail", "Detalle del partido"],
  ["shots", "Mapa de tiros"],
  ["heatmaps", "Heatmaps"],
  ["lineups", "Alineaciones"],
  ["momentum", "Momentum"],
  ["team_stats", "Estadísticas de equipo"],
  ["average_positions", "Posiciones medias"],
];
const GAP_LABEL: Record<string, string> = { detail: "Detalle", matches: "Partidos", venue: "Estadio", lineups: "Alineaciones", momentum: "Momentum", cards: "Tarjetas" };

function metricsOf(model: ModelRun): Record<string, unknown>[] {
  if (typeof model.metrics === "string") {
    try {
      const parsed = JSON.parse(model.metrics);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return Array.isArray(model.metrics) ? (model.metrics as Record<string, unknown>[]) : [];
}

export default async function StatusPage() {
  const status = await getJson<Status>("/v1/status");
  const seasons = Array.from(new Set(status.coverage.map((row) => row.season))).sort((a, b) => b - a);
  const cell = (season: number, kind: string): CoverageRow | undefined => status.coverage.find((row) => row.season === season && row.kind === kind);
  const xg = status.models.find((model) => model.model === "xg");
  const elo = status.models.find((model) => model.model === "elo");

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Estado de los datos</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">Qué hay, qué falta y por qué. Un hueco explicado no es una alarma: se registra con su motivo y su fuente.</p>

      <section className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Release">
        {[
          ["Release", status.release_id],
          ["Construido", formatDate(status.built_at)],
          ["Datos hasta", formatDate(status.data_as_of)],
          ["Vigencia", status.stale ? `Atrasado: ${status.overdue_matches} partidos sin resultado` : "Al día"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-line bg-surface px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
            <p className={`num mt-1 font-semibold ${label === "Vigencia" && status.stale ? "text-loss" : ""}`}>{value}</p>
          </div>
        ))}
      </section>

      <section className="mt-10">
        <h2 className="mb-1 text-lg font-semibold">Cobertura por temporada</h2>
        <p className="mb-3 text-sm text-muted">Partidos que tienen cada dato, sobre los partidos jugados con marcador normal (sin anulados ni adjudicados).</p>
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <caption className="sr-only">Cobertura de datos por temporada</caption>
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th scope="col" className="px-3 py-2">
                  Temporada
                </th>
                {KINDS.map(([, label]) => (
                  <th key={label} scope="col" className="px-2 py-2 text-right">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {seasons.map((season) => (
                <tr key={season} className="border-b border-line last:border-0">
                  <th scope="row" className="num px-3 py-2 text-left font-medium">
                    {season}
                  </th>
                  {KINDS.map(([kind]) => {
                    const row = cell(season, kind);
                    if (!row) return <td key={kind} className="px-2 py-2 text-right text-muted">—</td>;
                    const share = row.expected ? row.present / row.expected : 1;
                    return (
                      <td key={kind} className="num px-2 py-2 text-right" title={`${row.present} de ${row.expected} partidos`}>
                        <span className={row.missing === 0 ? "text-win" : share >= 0.9 ? "" : "font-semibold text-loss"}>{(share * 100).toFixed(share === 1 ? 0 : 1).replace(".", ",")} %</span>
                        <span className="ml-1 text-xs text-muted">
                          {row.present}/{row.expected}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Huecos conocidos</h2>
        <ul className="space-y-2">
          {status.known_gaps.map((gap, index) => (
            <li key={index} className="rounded-lg border border-line bg-surface px-4 py-3 text-sm">
              <p>
                <span className="mr-2 rounded bg-bg px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-muted">{GAP_LABEL[gap.kind] ?? gap.kind}</span>
                <span className="num text-muted">{gap.season ?? "2022–2026"}</span> · <span className="font-medium">{gap.scope}</span>
              </p>
              <p className="mt-1 text-muted">{gap.reason}</p>
              <p className="mt-1 text-xs text-muted">Fuente: {gap.source}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Modelos</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {xg ? (
            <div className="rounded-lg border border-line bg-surface p-4">
              <p className="font-semibold">
                xG propio <span className="num text-xs font-normal text-muted">versión {xg.version}</span>
              </p>
              <p className="mt-1 text-xs text-muted">{xg.trained_on}</p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[420px] border-collapse text-sm">
                  <caption className="sr-only">Validación del xG por temporada</caption>
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                      <th scope="col" className="py-1.5">Temporada</th>
                      {["Tiros", "AUC", "Pérdida", "xG total", "Goles"].map((heading) => (
                        <th key={heading} scope="col" className="py-1.5 text-right">{heading}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {metricsOf(xg).map((row) => (
                      <tr key={String(row.season)} className="border-b border-line last:border-0">
                        <td className="num py-1.5">{String(row.season)}</td>
                        <td className="num py-1.5 text-right">{number(Number(row.tiros_modelo))}</td>
                        <td className="num py-1.5 text-right">{number(Number(row.auc), 3)}</td>
                        <td className="num py-1.5 text-right">{number(Number(row.log_loss_modelo), 3)}</td>
                        <td className="num py-1.5 text-right">{number(Number(row.xG_total), 0)}</td>
                        <td className="num py-1.5 text-right">{number(Number(row.goles), 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
          {elo ? (
            <div className="rounded-lg border border-line bg-surface p-4">
              <p className="font-semibold">
                Probabilidad de título (Elo + Monte Carlo) <span className="num text-xs font-normal text-muted">versión {elo.version}</span>
              </p>
              <p className="mt-1 text-xs text-muted">Ajustado con {elo.trained_on}</p>
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                {Object.entries(typeof elo.params === "object" ? elo.params : {}).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs text-muted">{key}</dt>
                    <dd className="num">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : null}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-lg font-semibold">Últimos releases</h2>
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="w-full min-w-[480px] border-collapse text-sm">
            <caption className="sr-only">Registro de releases</caption>
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th scope="col" className="px-3 py-2">Release</th>
                <th scope="col" className="px-2 py-2">Construido</th>
                <th scope="col" className="px-2 py-2 text-right">Partidos</th>
                <th scope="col" className="px-3 py-2">Datos hasta</th>
              </tr>
            </thead>
            <tbody>
              {status.release_log.map((row) => (
                <tr key={row.release_id} className="border-b border-line last:border-0">
                  <td className="num px-3 py-2">{row.release_id}</td>
                  <td className="px-2 py-2">{formatDate(row.built_at)}</td>
                  <td className="num px-2 py-2 text-right">{row.matches}</td>
                  <td className="px-3 py-2">{formatDate(row.data_as_of)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

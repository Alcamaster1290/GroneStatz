/** Una cifra con su rótulo. `dim` atenúa las cifras con muestra chica; `hint` muestra su n. */
export default function StatCard({ label, value, hint, dim = false }: { label: string; value: string; hint?: string; dim?: boolean }) {
  return (
    <div className={`rounded-lg border border-line bg-surface px-4 py-3 ${dim ? "opacity-60" : ""}`}>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="num mt-1 text-2xl font-semibold leading-none">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

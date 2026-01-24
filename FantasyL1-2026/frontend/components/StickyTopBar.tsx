export default function StickyTopBar({
  budgetUsed,
  budgetLeft
}: {
  budgetUsed: number;
  budgetLeft: number;
}) {
  return (
    <div className="sticky top-4 z-30 mb-4 rounded-2xl border border-white/10 bg-black/50 p-4 backdrop-blur-xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted">Presupuesto usado</p>
          <p className="text-xl font-semibold text-ink">{budgetUsed.toFixed(1)}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted">Restante</p>
          <p className="text-xl font-semibold text-accent">{budgetLeft.toFixed(1)}</p>
        </div>
      </div>
    </div>
  );
}

export default function AppHeader() {
  return (
    <header className="mb-5">
      <div className="ui-panel flex items-center gap-3 px-3 py-2.5">
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-black/25 p-1.5">
          <img
            src="/favicon.png"
            alt="Fantasy Liga 1"
            className="h-full w-full rounded-full object-contain"
          />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.22em] text-muted">Fantasy Liga 1 Peru</p>
          <p className="text-lg font-semibold text-ink">Temporada 2026</p>
        </div>
      </div>
    </header>
  );
}

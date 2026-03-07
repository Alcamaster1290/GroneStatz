export default function AppHeader() {
  return (
    <header className="mb-5">
      <div className="ui-panel premium-frame flex items-center gap-3 px-3 py-2.5">
        <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/20 bg-black/35 p-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]">
          <img
            src="/favicon.png"
            alt="Fantasy Liga 1"
            className="h-full w-full rounded-full object-contain"
          />
        </div>
        <div className="min-w-0">
          <p className="premium-kicker text-[10px]">Fantasy Liga 1 Peru</p>
          <p className="premium-title text-lg font-semibold text-ink">Temporada 2026</p>
        </div>
      </div>
    </header>
  );
}

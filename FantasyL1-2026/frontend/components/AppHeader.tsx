export default function AppHeader() {
  return (
    <div className="mb-5 flex items-center gap-3">
      <img
        src="/favicon.png"
        alt="Fantasy Liga 1"
        className="h-10 w-10 rounded-full border border-white/10 bg-black/30 p-1"
      />
      <div>
        <p className="text-xs text-muted">Fantasy Liga 1 Peru</p>
        <p className="text-lg font-semibold text-ink">2026</p>
      </div>
    </div>
  );
}

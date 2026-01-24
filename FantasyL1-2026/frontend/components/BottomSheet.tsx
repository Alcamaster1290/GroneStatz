"use client";

import clsx from "clsx";

export default function BottomSheet({
  open,
  title,
  onClose,
  children
}: {
  open: boolean;
  title?: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className={clsx(
        "fixed inset-0 z-50 transition",
        open ? "pointer-events-auto" : "pointer-events-none"
      )}
    >
      <div
        onClick={onClose}
        className={clsx(
          "absolute inset-0 bg-black/60 transition-opacity",
          open ? "opacity-100" : "opacity-0"
        )}
      />
      <div
        className={clsx(
          "absolute inset-x-0 bottom-0 rounded-t-3xl border border-white/10 bg-surface p-6 shadow-glow transition-transform",
          open ? "translate-y-0" : "translate-y-full"
        )}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-ink">{title}</h3>
          <button onClick={onClose} className="text-sm text-muted" aria-label="Cerrar">
            X
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

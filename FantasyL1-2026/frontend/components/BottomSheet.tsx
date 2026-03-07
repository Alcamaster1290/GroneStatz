"use client";

import { useEffect } from "react";

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
  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  return (
    <div
      className={clsx(
        "fixed inset-0 z-50 transition",
        open ? "pointer-events-auto" : "pointer-events-none"
      )}
      aria-hidden={!open}
    >
      <div
        onClick={onClose}
        className={clsx(
          "absolute inset-0 bg-black/70 transition-opacity",
          open ? "opacity-100" : "opacity-0"
        )}
      />
      <div className="absolute inset-x-0 bottom-0 p-2 sm:p-4">
        <div
          role="dialog"
          aria-modal="true"
          aria-label={title || "Panel"}
          className={clsx(
            "ui-panel mx-auto w-full max-w-md rounded-t-3xl p-5 shadow-[0_22px_60px_rgba(0,0,0,0.5)] transition-transform",
            open ? "translate-y-0" : "translate-y-full"
          )}
        >
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-ink">{title}</h3>
            <button
              onClick={onClose}
              className="ui-btn ui-btn-secondary px-3 py-1 text-xs"
              aria-label="Cerrar"
            >
              Cerrar
            </button>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";

import clsx from "clsx";

type ModalDialogProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  maxWidthClass?: string;
};

export default function ModalDialog({
  open,
  title,
  onClose,
  children,
  maxWidthClass = "max-w-3xl"
}: ModalDialogProps) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const titleId = `modal-title-${title.toLowerCase().replace(/\s+/g, "-")}`;

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEsc);
    closeButtonRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", handleEsc);
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
        className={clsx(
          "absolute inset-0 bg-black/75 transition-opacity",
          open ? "opacity-100" : "opacity-0"
        )}
        onClick={onClose}
      />

      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          className={clsx(
            "ui-panel w-full rounded-2xl shadow-[0_28px_80px_rgba(0,0,0,0.48)]",
            maxWidthClass,
            open ? "scale-100 opacity-100" : "scale-95 opacity-0"
          )}
        >
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <h3 id={titleId} className="text-sm font-semibold text-ink">
              {title}
            </h3>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              className="ui-btn ui-btn-secondary px-3 py-1 text-xs"
              aria-label="Cerrar"
            >
              Cerrar
            </button>
          </div>
          <div className="max-h-[70vh] overflow-y-auto px-4 py-3">{children}</div>
        </div>
      </div>
    </div>
  );
}

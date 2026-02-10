"use client";

import Link from "next/link";
import { useState } from "react";
import { Save, ShoppingBag, Plus } from "lucide-react";

type FabMenuProps = {
  onSave: () => void;
  onRevert: () => void;
  isLineupSaved: boolean;
  canRevert: boolean;
  indicatorLabel: string;
  indicatorTone: "green" | "yellow" | "red";
  saveEnabled?: boolean;
};

export default function FabMenu({
  onSave,
  onRevert,
  isLineupSaved,
  canRevert,
  indicatorLabel,
  indicatorTone,
  saveEnabled = true
}: FabMenuProps) {
  const [open, setOpen] = useState(false);
  const toneClass =
    indicatorTone === "green"
      ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-200"
      : indicatorTone === "yellow"
        ? "border-amber-400/40 bg-amber-500/10 text-amber-200"
        : "border-red-400/40 bg-red-500/10 text-red-200";
  const dotClass =
    indicatorTone === "green"
      ? "bg-emerald-300"
      : indicatorTone === "yellow"
        ? "bg-amber-300"
        : "bg-red-300";

  return (
    <div className="fixed bottom-24 right-6 z-40 flex flex-col items-end gap-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => {
            if (!saveEnabled) return;
            onSave();
          }}
          disabled={!saveEnabled}
          className={
            "glass inline-flex items-center gap-2 rounded-full px-3 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-90 " +
            toneClass
          }
          aria-label="Estado del XI"
        >
          <span className={"inline-block h-2.5 w-2.5 rounded-full " + dotClass} />
          {indicatorLabel}
        </button>
        {!isLineupSaved && canRevert && saveEnabled ? (
          <button
            type="button"
            onClick={onRevert}
            className="glass inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/15 text-sm font-semibold text-ink"
            aria-label="Cancelar cambios del XI"
            title="Cancelar cambios"
          >
            X
          </button>
        ) : null}
      </div>
      {open ? (
        <div className="flex flex-col items-end gap-2">
          <button
            onClick={() => {
              if (!saveEnabled) return;
              onSave();
            }}
            disabled={!saveEnabled}
            className="glass flex items-center gap-2 rounded-full px-4 py-2 text-sm text-ink disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Save size={16} />
            {saveEnabled ? (isLineupSaved ? "XI guardado" : "Guardar XI") : "Ronda cerrada"}
          </button>
          <Link
            href="/market"
            className="glass flex items-center gap-2 rounded-full px-4 py-2 text-sm text-ink"
          >
            <ShoppingBag size={16} />
            Mercado
          </Link>
        </div>
      ) : null}
      <button
        onClick={() => setOpen((prev) => !prev)}
        className={
          "flex h-14 w-14 items-center justify-center rounded-full bg-accent text-black shadow-glow transition-transform " +
          (open ? "rotate-45" : "")
        }
        aria-label="Abrir acciones"
      >
        <Plus size={22} />
      </button>
    </div>
  );
}

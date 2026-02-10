"use client";

import Link from "next/link";
import { useState } from "react";
import { Save, ShoppingBag, Plus } from "lucide-react";

type FabMenuProps = {
  onSave: () => void;
  onRevert: () => void;
  isLineupSaved: boolean;
  canRevert: boolean;
};

export default function FabMenu({ onSave, onRevert, isLineupSaved, canRevert }: FabMenuProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-24 right-6 z-40 flex flex-col items-end gap-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onSave}
          className={
            "glass inline-flex items-center gap-2 rounded-full px-3 py-2 text-xs font-semibold transition " +
            (isLineupSaved
              ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-200"
              : "border-amber-400/40 bg-amber-500/10 text-amber-200")
          }
          aria-label="Guardar XI"
        >
          <span
            className={
              "inline-block h-2.5 w-2.5 rounded-full " +
              (isLineupSaved ? "bg-emerald-300" : "bg-amber-300")
            }
          />
          {isLineupSaved ? "XI GUARDADO" : "XI PENDIENTE"}
        </button>
        {!isLineupSaved && canRevert ? (
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
            onClick={onSave}
            className="glass flex items-center gap-2 rounded-full px-4 py-2 text-sm text-ink"
          >
            <Save size={16} />
            {isLineupSaved ? "XI guardado" : "Guardar XI"}
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

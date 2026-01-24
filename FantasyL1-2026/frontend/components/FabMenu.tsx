"use client";

import Link from "next/link";
import { useState } from "react";
import { Save, ShoppingBag, Plus } from "lucide-react";

export default function FabMenu({ onSave }: { onSave: () => void }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-24 right-6 z-40 flex flex-col items-end gap-3">
      {open ? (
        <div className="flex flex-col items-end gap-2">
          <button
            onClick={onSave}
            className="glass flex items-center gap-2 rounded-full px-4 py-2 text-sm text-ink"
          >
            <Save size={16} />
            Guardar XI
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
        className="flex h-14 w-14 items-center justify-center rounded-full bg-accent text-black shadow-glow"
      >
        <Plus size={22} />
      </button>
    </div>
  );
}

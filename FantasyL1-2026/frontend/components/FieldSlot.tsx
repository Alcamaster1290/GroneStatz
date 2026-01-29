"use client";

import clsx from "clsx";
import { useDroppable } from "@dnd-kit/core";

import { LineupSlot, Player } from "../lib/types";

export default function FieldSlot({
  slot,
  player,
  onClick
}: {
  slot: LineupSlot;
  player?: Player;
  onClick?: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `slot-${slot.slot_index}`,
    data: { slotIndex: slot.slot_index }
  });

  return (
    <button
      ref={setNodeRef}
      onClick={onClick}
      className={clsx(
        "glass relative flex h-20 w-full items-center justify-between rounded-2xl px-3 text-left",
        isOver ? "ring-2 ring-accent" : ""
      )}
    >
      <div>
        <p className="text-xs uppercase text-muted">{slot.role}</p>
        <p className="text-sm font-semibold text-ink">
          {player ? player.name : "Disponible"}
        </p>
      </div>
      <div className="text-right">
        <p className="text-xs text-muted">{slot.is_starter ? "XI" : "Bench"}</p>
        {player ? <p className="text-sm text-accent">{player.price_current.toFixed(1)}</p> : null}
      </div>
    </button>
  );
}

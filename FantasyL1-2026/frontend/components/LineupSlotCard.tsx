"use client";

import clsx from "clsx";
import { useDraggable, useDroppable } from "@dnd-kit/core";

import PlayerAvatarSquare from "@/components/PlayerAvatarSquare";
import { LineupSlot, Player } from "../lib/types";

export default function LineupSlotCard({
  slot,
  player,
  opponent,
  onClick,
  compact = false,
  isCaptain = false,
  isViceCaptain = false
}: {
  slot: LineupSlot;
  player?: Player;
  opponent?: { teamId: number; name?: string };
  onClick?: () => void;
  compact?: boolean;
  isCaptain?: boolean;
  isViceCaptain?: boolean;
}) {
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `slot-${slot.slot_index}`,
    data: { slotIndex: slot.slot_index }
  });

  const {
    attributes,
    listeners,
    setNodeRef: setDragRef,
    transform,
    isDragging
  } = useDraggable({
    id: player ? `player-${player.player_id}` : `slot-${slot.slot_index}-empty`,
    data: { playerId: player?.player_id, slotIndex: slot.slot_index },
    disabled: !player
  });

  const displayName = player ? player.short_name || player.shortName || player.name : "Disponible";

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`
      }
    : undefined;

  return (
    <div ref={setDropRef} className="relative">
      <button
        ref={setDragRef}
        style={style}
        onClick={onClick}
        {...listeners}
        {...attributes}
        className={clsx(
          compact
            ? "glass flex aspect-square w-full flex-col justify-between rounded-2xl p-2 text-left transition"
            : "glass flex h-20 w-full items-center justify-between rounded-2xl px-3 text-left transition",
          isOver ? "ring-2 ring-accent" : "",
          isDragging ? "opacity-60" : ""
        )}
      >
        {compact ? (
          <PlayerAvatarSquare
            playerId={player?.player_id}
            teamId={player?.team_id}
            isCaptain={isCaptain}
            isViceCaptain={isViceCaptain}
            className="aspect-square w-full ring-1 ring-white/10"
          />
        ) : (
          <>
            <div>
              <p className="text-xs uppercase text-muted">{slot.role}</p>
              <p className="text-sm font-semibold text-ink">{displayName}</p>
              {player && opponent ? (
                <div className="mt-1 flex items-center gap-1 text-[10px] text-muted">
                  <span>vs</span>
                  <span className="flex h-[12px] w-[12px] items-center justify-center">
                    <img
                      src={`/images/teams/${opponent.teamId}.png`}
                      alt=""
                      className="h-full w-full object-contain"
                      onError={(event) => {
                        (event.currentTarget as HTMLImageElement).style.display = "none";
                      }}
                    />
                  </span>
                </div>
              ) : null}
            </div>
            <div className="text-right">
              <p className="text-xs text-muted">{slot.is_starter ? "XI" : "Bench"}</p>
              {player ? <p className="text-sm text-accent">{player.price_current.toFixed(1)}</p> : null}
            </div>
          </>
        )}
      </button>
    </div>
  );
}

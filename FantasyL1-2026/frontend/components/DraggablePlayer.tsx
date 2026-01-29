"use client";

import clsx from "clsx";
import { useDraggable } from "@dnd-kit/core";

import PlayerAvatarSquare from "@/components/PlayerAvatarSquare";
import PlayerCard from "@/components/PlayerCard";
import { Player } from "../lib/types";

export default function DraggablePlayer({
  player,
  slotIndex,
  onClick,
  variant = "card",
  className,
  isCaptain = false,
  isViceCaptain = false
}: {
  player: Player;
  slotIndex: number;
  onClick?: () => void;
  variant?: "card" | "square";
  className?: string;
  isCaptain?: boolean;
  isViceCaptain?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `player-${player.player_id}`,
    data: { playerId: player.player_id, slotIndex }
  });

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        transition: isDragging ? "none" : "transform 150ms ease"
      }
    : { transition: "transform 150ms ease" };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={clsx(
        "touch-none select-none transition-transform",
        isDragging ? "opacity-0" : "",
        className
      )}
    >
      <div {...listeners} {...attributes}>
        {variant === "square" ? (
          <button
            type="button"
            onClick={onClick}
            className="w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <PlayerAvatarSquare
              playerId={player.player_id}
              teamId={player.team_id}
              isCaptain={isCaptain}
              isViceCaptain={isViceCaptain}
              className="aspect-square w-full ring-1 ring-white/10"
              rounded={false}
            />
          </button>
        ) : (
          <PlayerCard player={player} onClick={onClick} />
        )}
      </div>
    </div>
  );
}

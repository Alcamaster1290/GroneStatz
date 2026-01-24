import clsx from "clsx";

import { Player } from "@/lib/types";

const positionLabels: Record<string, string> = {
  G: "GK",
  D: "D",
  M: "M",
  F: "F"
};

export default function PlayerCard({
  player,
  onClick,
  compact = false
}: {
  player: Player;
  onClick?: () => void;
  compact?: boolean;
}) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        "glass flex w-full items-center justify-between gap-3 rounded-2xl p-3 transition",
        "hover:border-white/20",
        compact ? "py-2" : ""
      )}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface2 text-sm font-semibold">
          {positionLabels[player.position]}
        </div>
        <div>
          <p className="text-sm font-semibold text-ink">{player.name}</p>
          <div className="flex items-center gap-2 text-xs text-muted">
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-surface2">
              <img
                src={`/images/teams/${player.team_id}.png`}
                alt=""
                className="h-full w-full object-contain"
                onError={(event) => {
                  (event.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            </div>
          </div>
        </div>
      </div>
      <div className="text-right">
        <p className="text-sm font-semibold text-accent">{player.price_current.toFixed(1)}</p>
      </div>
    </div>
  );
}

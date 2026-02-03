import clsx from "clsx";
import { useEffect, useState } from "react";

import { Player } from "@/lib/types";

const positionLabels: Record<string, string> = {
  G: "Arquero",
  D: "Defensa",
  M: "Mediocampo",
  F: "Delantero"
};

function PlayerFace({ playerId, sizeClass }: { playerId: number; sizeClass: string }) {
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    setHidden(false);
  }, [playerId]);

  if (hidden) {
    return (
      <div
        className={clsx(
          "flex items-center justify-center rounded-full bg-surface2/60 ring-1 ring-white/10",
          sizeClass
        )}
      />
    );
  }

  return (
    <div className={clsx("overflow-hidden rounded-full ring-1 ring-white/10", sizeClass)}>
      <img
        src={`/images/players/${playerId}.png`}
        alt=""
        className="h-full w-full object-cover"
        onError={() => setHidden(true)}
      />
    </div>
  );
}

export default function PlayerCard({
  player,
  onClick,
  compact = false,
  showPoints = false
}: {
  player: Player;
  onClick?: () => void;
  compact?: boolean;
  showPoints?: boolean;
}) {
  const avatarSize = compact ? "h-9 w-9" : "h-11 w-11";
  const teamSize = compact ? "h-7 w-7" : "h-8 w-8";
  const goals = player.goals ?? 0;
  const assists = player.assists ?? 0;
  const saves = player.saves ?? 0;
  const goalsConceded = player.goals_conceded ?? 0;
  const pointsTotal = typeof player.points_total === "number" ? player.points_total : 0;
  const priceDelta =
    typeof player.price_delta === "number" ? player.price_delta : null;
  const isGoalkeeper = player.position === "G";
  const isDefender = player.position === "D";
  const isInjured = Boolean(player.is_injured);

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
        <PlayerFace playerId={player.player_id} sizeClass={avatarSize} />
        <div className={clsx("flex items-center justify-center rounded-full bg-surface2", teamSize)}>
          <img
            src={`/images/teams/${player.team_id}.png`}
            alt=""
            className="h-full w-full object-contain"
            onError={(event) => {
              (event.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        </div>
        <div>
          <p className="text-sm font-semibold text-ink">{player.name}</p>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
            <span className="rounded-full border border-white/10 px-2 py-0.5">
              {positionLabels[player.position]}
            </span>
            {isInjured ? (
              <span className="rounded-full border border-red-400/40 bg-red-500/10 px-2 py-0.5 text-[10px] text-red-200">
                Lesionado
              </span>
            ) : null}
            {isGoalkeeper ? (
              <>
                <span>Atajadas {saves}</span>
                <span>Goles {goals}</span>
                <span>GC {goalsConceded}</span>
              </>
            ) : isDefender ? (
              <>
                <span>Goles {goals}</span>
                <span>GC {goalsConceded}</span>
              </>
            ) : (
              <>
                <span>Goles {goals}</span>
                <span>Asist {assists}</span>
              </>
            )}
            {showPoints ? <span>Puntos {pointsTotal.toFixed(1)}</span> : null}
          </div>
        </div>
      </div>
      <div className="text-right">
        <p className="text-sm font-semibold text-accent">{player.price_current.toFixed(1)}</p>
        {priceDelta !== null ? (
          <p
            className={clsx(
              "text-[10px]",
              priceDelta >= 0 ? "text-emerald-300" : "text-red-300"
            )}
          >
            {priceDelta >= 0 ? "+" : ""}
            {priceDelta.toFixed(1)}
          </p>
        ) : null}
      </div>
    </div>
  );
}

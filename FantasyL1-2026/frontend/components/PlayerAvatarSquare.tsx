"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";

export default function PlayerAvatarSquare({
  playerId,
  teamId,
  isCaptain = false,
  isViceCaptain = false,
  className,
  rounded = true
}: {
  playerId?: number | null;
  teamId?: number | null;
  isCaptain?: boolean;
  isViceCaptain?: boolean;
  className?: string;
  rounded?: boolean;
}) {
  const sources = playerId
    ? [
        `/images/players/${playerId}.png`
      ]
    : [];
  const [srcIndex, setSrcIndex] = useState(0);
  const [hidden, setHidden] = useState(!playerId);

  useEffect(() => {
    setSrcIndex(0);
    setHidden(!playerId);
  }, [playerId]);

  const handleError = () => {
    setSrcIndex((prev) => {
      const next = prev + 1;
      if (next >= sources.length) {
        setHidden(true);
        return prev;
      }
      return next;
    });
  };

  if (!playerId || hidden) {
    return (
      <div
        className={clsx(
          "relative flex items-center justify-center bg-surface2/30",
          rounded ? "rounded-xl" : "",
          className
        )}
      />
    );
  }

  return (
    <div
      className={clsx(
        "relative",
        rounded ? "rounded-xl" : "",
        className
      )}
    >
      <div className={clsx("h-full w-full overflow-hidden", rounded ? "rounded-xl" : "")}>
        <img
          src={sources[srcIndex]}
          alt=""
          className="h-full w-full object-cover"
          onError={handleError}
        />
      </div>
      {teamId ? (
        <span className="absolute bottom-1 right-1 z-20 flex h-[25%] w-[25%] items-center justify-center">
          <img
            src={`/images/teams/${teamId}.png`}
            alt=""
            className="h-full w-full object-contain"
            onError={(event) => {
              (event.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        </span>
      ) : null}
      {isCaptain ? (
        <span className="absolute bottom-1 left-1 z-30 flex h-[25%] w-[25%] items-center justify-center rounded-full bg-yellow-300 text-[10px] font-bold text-black">
          C
        </span>
      ) : null}
      {isViceCaptain ? (
        <span className="absolute bottom-1 left-1 z-30 flex h-[25%] w-[25%] items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-black">
          V
        </span>
      ) : null}
    </div>
  );
}

"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";

export default function PlayerAvatarSquare({
  playerId,
  teamId,
  className,
  rounded = true
}: {
  playerId?: number | null;
  teamId?: number | null;
  className?: string;
  rounded?: boolean;
}) {
  const sources = playerId
    ? [
        `/images/players/${playerId}.png`,
        `/images/players/${playerId}.jpg`,
        `/images/players/${playerId}.jpeg`,
        `/images/players/${playerId}.webp`
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
        "relative overflow-hidden",
        rounded ? "rounded-xl" : "",
        className
      )}
    >
      <img
        src={sources[srcIndex]}
        alt=""
        className="h-full w-full object-cover"
        onError={handleError}
      />
      {teamId ? (
        <span className="absolute -bottom-1 -right-1 flex h-[25%] w-[25%] -translate-x-[10%] -translate-y-[10%] items-center justify-center">
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
    </div>
  );
}

"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import AuthPanel from "@/components/AuthPanel";
import BottomSheet from "@/components/BottomSheet";
import MarketFilters from "@/components/MarketFilters";
import PlayerCard from "@/components/PlayerCard";
import PriceHistoryLineChart from "@/components/PriceHistoryLineChart";
import {
  createTeam,
  getCatalogPlayers,
  getFixtures,
  getLineup,
  getPlayerPriceHistory,
  getTeam,
  getTeams,
  getTransferCount,
  transferPlayer,
  updateSquad
} from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { Fixture, Player, PlayerPriceHistoryPoint, TransferCount } from "@/lib/types";
import { validateSquad } from "@/lib/validation";

function PlayerFace({ playerId }: { playerId: number }) {
  const sources = [
    `/images/players/${playerId}.png`
  ];
  const [srcIndex, setSrcIndex] = useState(0);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    setSrcIndex(0);
    setHidden(false);
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

  if (hidden) {
    return (
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface2/80 ring-1 ring-white/10" />
    );
  }

  return (
    <div className="h-12 w-12 overflow-hidden rounded-full ring-1 ring-white/10">
      <img
        src={sources[srcIndex]}
        alt=""
        className="h-full w-full object-cover"
        onError={handleError}
      />
    </div>
  );
}

function TeamBadge({ teamId }: { teamId: number }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <span className="absolute -bottom-1 -right-1 flex h-[20px] w-[20px] items-center justify-center rounded-full">
      <img
        src={`/images/teams/${teamId}.png`}
        alt=""
        className="h-full w-full object-contain"
        onError={() => setHidden(true)}
      />
    </span>
  );
}

function PitchPlayer({
  player,
  onSelect,
  onRemove,
  isSelected
}: {
  player: Player;
  onSelect: (player: Player) => void;
  onRemove: (playerId: number) => void;
  isSelected: boolean;
}) {
  const displayName = player.short_name || player.shortName || player.name;

  return (
    <div
      onClick={() => onSelect(player)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(player);
        }
      }}
      role="button"
      tabIndex={0}
      className={
        "flex flex-col items-center gap-1 rounded-2xl px-2 py-2 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent " +
        (isSelected ? " bg-white/5" : "")
      }
    >
      <div className="relative">
        <PlayerFace playerId={player.player_id} />
        <TeamBadge teamId={player.team_id} />
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onRemove(player.player_id);
          }}
          className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-black/70 text-[10px] text-ink ring-1 ring-white/20"
          aria-label={`Quitar ${displayName}`}
        >
          X
        </button>
      </div>
      <div className="flex flex-col items-center">
        <span className="max-w-[72px] truncate text-[10px] text-ink">{displayName}</span>
        <span className="text-[9px] text-muted">{player.price_current.toFixed(1)}</span>
      </div>
    </div>
  );
}

const positionLabels: Record<string, string> = {
  G: "Arquero",
  D: "Defensa",
  M: "Mediocampo",
  F: "Delantero"
};

function formatRoundDateLabel(dateKey: string): string {
  if (!dateKey || dateKey === "TBD") return "Por confirmar";
  const [year, month, day] = dateKey.split("-").map((part) => Number(part));
  if (!year || !month || !day) return dateKey;
  const date = new Date(year, month - 1, day);
  const weekdays = [
    "Domingo",
    "Lunes",
    "Martes",
    "Miercoles",
    "Jueves",
    "Viernes",
    "Sabado"
  ];
  const months = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre"
  ];
  const weekday = weekdays[date.getDay()];
  const monthLabel = months[month - 1];
  if (!weekday || !monthLabel) return dateKey;
  return `${weekday} ${day} de ${monthLabel}`;
}

function kickoffToDateKey(value: string | null | undefined): string {
  if (!value) return "TBD";
  const raw = String(value).trim();
  if (!raw) return "TBD";
  return raw.split("T")[0].split(" ")[0] || "TBD";
}

function MarketPlayerDetails({ player, fixtures }: { player: Player; fixtures: Fixture[] }) {
  const displayName = player.short_name || player.shortName || player.name;
  const isKeeper = player.position === "G";
  const pointsValue =
    typeof player.points_total === "number" ? Math.trunc(player.points_total) : 0;
  const stats: { label: string; value: number | string; accent?: boolean }[] = [
    { label: "Puntos", value: pointsValue }
  ];
  const priceDelta =
    "price_delta" in player ? (player as { price_delta?: number }).price_delta : undefined;
  if (typeof priceDelta === "number") {
    const deltaSymbol = priceDelta === 0 ? "-" : priceDelta > 0 ? "▲" : "▼";
    const deltaValue = priceDelta === 0 ? "-" : priceDelta.toFixed(1);
    stats.push({
      label: "Variacion",
      value: `${deltaSymbol} ${deltaValue}`
    });
  }
  if (isKeeper) {
    stats.push(
      { label: "Atajadas", value: player.saves ?? 0 },
      { label: "Goles", value: player.goals ?? 0 },
      { label: "Goles recibidos", value: player.goals_conceded ?? 0 }
    );
  } else if (player.position === "D") {
    stats.push(
      { label: "Goles", value: player.goals ?? 0 },
      { label: "Goles recibidos", value: player.goals_conceded ?? 0 }
    );
  } else {
    stats.push(
      { label: "Goles", value: player.goals ?? 0 },
      { label: "Asistencias", value: player.assists ?? 0 }
    );
  }
  stats.push({ label: "Precio", value: player.price_current.toFixed(1), accent: true });

  const formatKickoff = (kickoff: string | null) => {
    if (!kickoff) return "Por confirmar";
    const normalized = kickoff.replace("T", " ").trim();
    const [datePart, timePart] = normalized.split(" ");
    const [year, month, day] = datePart.split("-");
    const shortYear = year ? year.slice(2) : "";
    const time = timePart ? timePart.slice(0, 5) : "";
    return `${day}/${month}/${shortYear}${time ? `, ${time}` : ""}`;
  };

  const teamFixtures = fixtures
    .filter(
      (fixture) =>
        fixture.home_team_id === player.team_id || fixture.away_team_id === player.team_id
    )
    .sort((a, b) => {
      const aKey = a.kickoff_at ? a.kickoff_at : "9999-99-99";
      const bKey = b.kickoff_at ? b.kickoff_at : "9999-99-99";
      return aKey.localeCompare(bKey);
    })
    .slice(0, 3);
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <PlayerFace playerId={player.player_id} />
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-surface2/60">
          <img
            src={`/images/teams/${player.team_id}.png`}
            alt=""
            className="h-full w-full object-contain"
            onError={(event) => {
              (event.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-ink">{displayName}</p>
          <p className="text-xs text-muted">
            {player.price_current.toFixed(1)} - {positionLabels[player.position] || player.position}
          </p>
        </div>
      </div>
      {player.is_injured ? (
        <div className="flex items-center gap-2 rounded-xl bg-red-500/80 px-3 py-2 text-xs font-semibold text-black">
          <span>!</span>
          <span>Lesionado</span>
        </div>
      ) : null}
      <div className="grid grid-cols-2 gap-2 rounded-2xl border border-white/10 bg-black/20 p-3 text-xs">
        {stats.map((stat) => (
          <div key={stat.label} className="space-y-1">
            <p className="text-[10px] uppercase text-muted">{stat.label}</p>
            <p
              className={
                "text-sm font-semibold " + (stat.accent ? "text-accent" : "text-ink")
              }
            >
              {stat.value}
            </p>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <p className="text-xs font-semibold text-ink">Partidos</p>
        {teamFixtures.length ? (
          <div className="space-y-2">
            {teamFixtures.map((fixture) => {
              const homeId = fixture.home_team_id;
              const awayId = fixture.away_team_id;
              return (
                <div
                  key={fixture.id}
                  className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-black/40">
                      {homeId ? (
                        <img
                          src={`/images/teams/${homeId}.png`}
                          alt=""
                          className="h-full w-full object-contain"
                        />
                      ) : null}
                    </span>
                    <span className="text-muted">-</span>
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-black/40">
                      {awayId ? (
                        <img
                          src={`/images/teams/${awayId}.png`}
                          alt=""
                          className="h-full w-full object-contain"
                        />
                      ) : null}
                    </span>
                  </div>
                  <div className="text-right text-[10px] text-muted">
                    <p>{formatKickoff(fixture.kickoff_at)}</p>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-muted">Sin partidos programados.</p>
        )}
      </div>
    </div>
  );
}

function PitchRow({
  label,
  players,
  onSelect,
  onRemove,
  selectedOutId
}: {
  label: string;
  players: Player[];
  onSelect: (player: Player) => void;
  onRemove: (playerId: number) => void;
  selectedOutId: number | null;
}) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">{label}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {players.length > 0 ? (
          players.map((player) => (
            <PitchPlayer
              key={player.player_id}
              player={player}
              onSelect={onSelect}
              onRemove={onRemove}
              isSelected={selectedOutId === player.player_id}
            />
          ))
        ) : (
          <div className="h-12 w-12 rounded-full bg-surface2/30" />
        )}
      </div>
    </div>
  );
}

export default function MarketPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const userEmail = useFantasyStore((state) => state.userEmail);
  const squad = useFantasyStore((state) => state.squad);
  const setSquad = useFantasyStore((state) => state.setSquad);
  const draftSquadState = useFantasyStore((state) => state.marketDraftSquad);
  const setDraftSquad = useFantasyStore((state) => state.setMarketDraftSquad);
  const setDraftBackup = useFantasyStore((state) => state.setMarketDraftBackup);
  const draftLoaded = useFantasyStore((state) => state.marketDraftLoaded);
  const setDraftLoaded = useFantasyStore((state) => state.setMarketDraftLoaded);
  const draftSquad = Array.isArray(draftSquadState) ? draftSquadState : [];

  const [playersBase, setPlayersBase] = useState<Player[]>([]);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>([]);
  const filters = useFantasyStore((state) => state.marketFilters);
  const setFilters = useFantasyStore((state) => state.setMarketFilters);
  const [outPlayerId, setOutPlayerId] = useState<number | null>(null);
  const [inPlayerId, setInPlayerId] = useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [loadingPlayers, setLoadingPlayers] = useState(false);
  const [errorPopup, setErrorPopup] = useState<string[] | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [randomLoading, setRandomLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [postSavePromptOpen, setPostSavePromptOpen] = useState(false);
  const [postSaveLaterOpen, setPostSaveLaterOpen] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [transferInfo, setTransferInfo] = useState<TransferCount | null>(null);
  const [playersAll, setPlayersAll] = useState<Player[] | null>(null);
  const [budgetCap, setBudgetCap] = useState(100);
  const [currentRoundNumber, setCurrentRoundNumber] = useState<number | null>(null);
  const [priceHistoryOpen, setPriceHistoryOpen] = useState(false);
  const [priceHistoryLoading, setPriceHistoryLoading] = useState(false);
  const [priceHistoryError, setPriceHistoryError] = useState<string | null>(null);
  const [priceHistoryPlayer, setPriceHistoryPlayer] = useState<Player | null>(null);
  const [priceHistoryPoints, setPriceHistoryPoints] = useState<PlayerPriceHistoryPoint[]>([]);
  const lastPositionsKey = useRef<string>("");
  const lastTeamKey = useRef<string>("");
  const priceHistoryRequestId = useRef(0);
  const router = useRouter();

  const parseMaybeNumber = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const roundToTenth = (value: number) => Math.round(value * 10) / 10;
  const resolveBudgetCap = (team: { budget_cap?: number }) => {
    const baseCap = Number.isFinite(team.budget_cap) ? Number(team.budget_cap) : 100;
    return roundToTenth(baseCap);
  };
  const normalizeErrorCode = (raw: string) => raw.replace(/^Error:\s*/i, "").trim();
  const splitErrorCodes = (raw: unknown) => {
    const cleaned = normalizeErrorCode(String(raw || "") || "api_error");
    return cleaned
      .split("|")
      .map((part) => part.trim())
      .filter(Boolean);
  };

  const parentRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const stored = localStorage.getItem("fantasy_token");
    const storedEmail = localStorage.getItem("fantasy_email");
    if (!token && stored) {
      setToken(stored);
    }
    if (!userEmail && storedEmail) {
      setUserEmail(storedEmail);
    }
  }, [token, setToken, userEmail, setUserEmail]);

  useEffect(() => {
    if (!Array.isArray(draftSquadState)) {
      setDraftSquad([]);
    }
  }, [draftSquadState, setDraftSquad]);

  useEffect(() => {
    if (!Array.isArray(filters.positions)) {
      setFilters({ ...filters, positions: [] });
    }
  }, [filters, setFilters]);

  useEffect(() => {
    if (typeof filters.teamId !== "string") {
      setFilters({ ...filters, teamId: "" });
    }
  }, [filters, setFilters]);

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      const team = await getTeam(token);
      setSquad(
        team.squad || [],
        team.budget_cap,
        team.budget_used,
        team.budget_left
      );
      setBudgetCap(resolveBudgetCap(team));
      if (!draftLoaded) {
        if (draftSquad.length === 0) {
          setDraftSquad(team.squad || []);
        }
        setDraftLoaded(true);
      }
      if (team.name) {
        setTeamName(team.name);
      }
    };
    load().catch(() => {
    });
  }, [token, setSquad, setDraftSquad, draftSquad.length, draftLoaded, setDraftLoaded]);

  useEffect(() => {
    getFixtures()
      .then(setFixtures)
      .catch(() => setFixtures([]));
  }, []);

  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch(() => setTeams([]));
  }, []);

  useEffect(() => {
    if (!token) return;
    getLineup(token)
      .then((lineup) => setCurrentRoundNumber(lineup.round_number))
      .catch(() => setCurrentRoundNumber(null));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    getTransferCount(token)
      .then(setTransferInfo)
      .catch(() => setTransferInfo(null));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    if (!sheetOpen) return;
    getTransferCount(token)
      .then(setTransferInfo)
      .catch(() => setTransferInfo(null));
  }, [token, sheetOpen]);

  const positionsKey = useMemo(
    () => (Array.isArray(filters.positions) ? filters.positions.join("|") : ""),
    [filters.positions]
  );
  const teamKey = useMemo(() => filters.teamId || "", [filters.teamId]);

  useEffect(() => {
    if (lastPositionsKey.current !== positionsKey) {
      lastPositionsKey.current = positionsKey;
      if (filters.minPrice !== "" || filters.maxPrice !== "") {
        setFilters({ ...filters, minPrice: "", maxPrice: "" });
      }
    }
  }, [positionsKey, filters, setFilters]);

  useEffect(() => {
    if (lastTeamKey.current !== teamKey) {
      lastTeamKey.current = teamKey;
      if (filters.minPrice !== "" || filters.maxPrice !== "") {
        setFilters({ ...filters, minPrice: "", maxPrice: "" });
      }
    }
  }, [teamKey, filters, setFilters]);

  useEffect(() => {
    if (playersAll && playersAll.length > 0) return;
    let cancelled = false;
    const loadAll = async () => {
      const limit = 200;
      const maxPages = 10;
      const all: Player[] = [];
      for (let page = 0; page < maxPages; page += 1) {
        const result = await getCatalogPlayers({
          limit,
          offset: page * limit
        });
        all.push(...result);
        if (result.length < limit) break;
      }
      const unique = new Map<number, Player>();
      all.forEach((player) => {
        unique.set(player.player_id, player);
      });
      const sorted = Array.from(unique.values()).sort((a, b) => b.price_current - a.price_current);
      if (!cancelled) {
        setPlayersAll(sorted);
      }
    };

    loadAll().catch(() => {
      if (!cancelled) setPlayersAll([]);
    });

    return () => {
      cancelled = true;
    };
  }, [playersAll]);

  useEffect(() => {
    const fetchPlayers = async () => {
      setFetchError(null);
      setLoadingPlayers(true);
      const limit = 200;
      const maxPages = 10;
      const all: Player[] = [];
      const positions =
        Array.isArray(filters.positions) && filters.positions.length > 0 ? filters.positions : [""];

      for (const position of positions) {
        for (let page = 0; page < maxPages; page += 1) {
          const result = await getCatalogPlayers({
            position: position || undefined,
            q: filters.query || undefined,
            team_id: filters.teamId ? Number(filters.teamId) : undefined,
            limit,
            offset: page * limit
          });
          all.push(...result);
          if (result.length < limit) break;
        }
      }

      const unique = new Map<number, Player>();
      all.forEach((player) => {
        unique.set(player.player_id, player);
      });
      const sorted = Array.from(unique.values()).sort((a, b) => b.price_current - a.price_current);
      setPlayersBase(sorted);
      setLoadingPlayers(false);
    };

    const timeout = setTimeout(() => {
      fetchPlayers().catch((err) => {
        setPlayersBase([]);
        setFetchError(String(err));
        setLoadingPlayers(false);
      });
    }, 250);

    return () => clearTimeout(timeout);
  }, [filters.query, positionsKey, teamKey]);

  const priceBounds = useMemo(() => {
    if (playersBase.length === 0) return { min: 0, max: 0 };
    let min = Number.POSITIVE_INFINITY;
    let max = 0;
    for (const player of playersBase) {
      if (player.price_current < min) min = player.price_current;
      if (player.price_current > max) max = player.price_current;
    }
    return { min, max };
  }, [playersBase]);

  useEffect(() => {
    if (playersBase.length === 0) {
      if (filters.minPrice || filters.maxPrice) {
        setFilters({ ...filters, minPrice: "", maxPrice: "" });
      }
      return;
    }
    const minBound = priceBounds.min;
    const maxBound = priceBounds.max;
    const minNum = parseMaybeNumber(filters.minPrice);
    const maxNum = parseMaybeNumber(filters.maxPrice);
    let nextMin = minNum !== null ? Math.min(Math.max(minNum, minBound), maxBound) : minBound;
    let nextMax = maxNum !== null ? Math.min(Math.max(maxNum, minBound), maxBound) : maxBound;
    if (nextMax < nextMin) nextMax = nextMin;
    const nextMinStr = nextMin.toFixed(1);
    const nextMaxStr = nextMax.toFixed(1);
    if (nextMinStr !== filters.minPrice || nextMaxStr !== filters.maxPrice) {
      setFilters({ ...filters, minPrice: nextMinStr, maxPrice: nextMaxStr });
    }
  }, [playersBase.length, priceBounds.min, priceBounds.max, filters.minPrice, filters.maxPrice, filters, setFilters]);

  const filteredPlayers = useMemo(() => {
    if (playersBase.length === 0) return [];
    const minNum = parseMaybeNumber(filters.minPrice);
    const maxNum = parseMaybeNumber(filters.maxPrice);
    const min = minNum !== null ? minNum : priceBounds.min;
    const max = maxNum !== null ? maxNum : priceBounds.max;
    return playersBase.filter((player) => player.price_current >= min && player.price_current <= max);
  }, [playersBase, filters.minPrice, filters.maxPrice, priceBounds.min, priceBounds.max]);

  const activeTeams = useMemo(() => {
    const source = playersAll && playersAll.length > 0 ? playersAll : playersBase;
    const counts = new Map<number, number>();
    source.forEach((player) => {
      counts.set(player.team_id, (counts.get(player.team_id) || 0) + 1);
    });
    return teams.filter((team) => (counts.get(team.id) || 0) > 1);
  }, [teams, playersAll, playersBase]);

  const nextRoundStartLabel = useMemo(() => {
    if (!currentRoundNumber) return "Por confirmar";
    const roundDates = fixtures
      .filter((fixture) => fixture.round_number === currentRoundNumber)
      .map((fixture) => kickoffToDateKey(fixture.kickoff_at))
      .filter((dateKey) => dateKey && dateKey !== "TBD")
      .sort((a, b) => a.localeCompare(b));
    if (roundDates.length === 0) return "Por confirmar";
    return formatRoundDateLabel(roundDates[0]);
  }, [fixtures, currentRoundNumber]);

  const rowVirtualizer = useVirtualizer({
    count: filteredPlayers.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 6
  });

  const outPlayer = useMemo(
    () => draftSquad.find((player) => player.player_id === outPlayerId),
    [draftSquad, outPlayerId]
  );

  const inPlayer = useMemo(
    () => playersBase.find((player) => player.player_id === inPlayerId),
    [playersBase, inPlayerId]
  );

  const playersByPosition = useMemo(() => {
    return {
      G: draftSquad.filter((player) => player.position === "G"),
      D: draftSquad.filter((player) => player.position === "D"),
      M: draftSquad.filter((player) => player.position === "M"),
      F: draftSquad.filter((player) => player.position === "F")
    };
  }, [draftSquad]);

  const clubCounts = useMemo(() => {
    const counts: Record<number, number> = {};
    draftSquad.forEach((player) => {
      counts[player.team_id] = (counts[player.team_id] || 0) + 1;
    });
    return counts;
  }, [draftSquad]);

  const maxClubCount = useMemo(() => {
    const values = Object.values(clubCounts);
    return values.length > 0 ? Math.max(...values) : 0;
  }, [clubCounts]);

  const clubRuleOk = maxClubCount <= 3;

  const draftBudget = useMemo(() => {
    const total = draftSquad.reduce((sum, player) => {
      return sum + roundToTenth(player.price_current);
    }, 0);
    return roundToTenth(total);
  }, [draftSquad]);
  const budgetLeftRaw = roundToTenth(budgetCap - draftBudget);
  const budgetLeft = Math.abs(budgetLeftRaw) < 0.05 ? 0 : budgetLeftRaw;
  const transferPreview = useMemo(() => {
    const squadIds = new Set(squad.map((player) => player.player_id));
    const draftIds = new Set(draftSquad.map((player) => player.player_id));
    const outgoing = squad.filter((player) => !draftIds.has(player.player_id));
    const incoming = draftSquad.filter((player) => !squadIds.has(player.player_id));
    const transferCount = Math.min(outgoing.length, incoming.length);
    const transfersUsed = transferInfo?.transfers_used ?? 0;
    return {
      outgoing,
      incoming,
      transferCount,
      transfersUsed
    };
  }, [draftSquad, squad, transferInfo]);

  const formatError = (code: string) => {
    const safeCode = normalizeErrorCode(code);
    const positionCounts = {
      G: playersByPosition.G.length,
      D: playersByPosition.D.length,
      M: playersByPosition.M.length,
      F: playersByPosition.F.length
    };
    const budgetOver =
      draftBudget > budgetCap ? roundToTenth(draftBudget - budgetCap).toFixed(1) : "0.0";
    const messages: Record<
      string,
      { title: string; detail?: string; tone?: "warning" | "danger" }
    > = {
      squad_must_have_15_players: {
        title: "Te faltan jugadores",
        detail: `Tienes ${draftSquad.length}/15`,
        tone: "warning"
      },
      squad_has_duplicate_players: {
        title: "Jugadores repetidos",
        detail: "Un jugador aparece mas de una vez.",
        tone: "danger"
      },
      squad_must_have_2_goalkeepers: {
        title: "Arqueros incompletos",
        detail: `Necesitas 2 arqueros. Tienes ${positionCounts.G}.`,
        tone: "warning"
      },
      squad_defenders_out_of_range: {
        title: "Defensas fuera de rango",
        detail: `Debes tener entre 3 y 6 defensas. Tienes ${positionCounts.D}.`,
        tone: "warning"
      },
      squad_midfielders_out_of_range: {
        title: "Mediocampistas fuera de rango",
        detail: `Debes tener entre 3 y 6 mediocampistas. Tienes ${positionCounts.M}.`,
        tone: "warning"
      },
      squad_forwards_out_of_range: {
        title: "Delanteros fuera de rango",
        detail: `Debes tener entre 1 y 3 delanteros. Tienes ${positionCounts.F}.`,
        tone: "warning"
      },
      max_3_players_per_team: {
        title: "Maximo 3 por club",
        detail: "Hay un club con mas de 3 jugadores.",
        tone: "danger"
      },
      budget_exceeded: {
        title: "Presupuesto excedido",
        detail: `Excediste el presupuesto por ${budgetOver} M.`,
        tone: "danger"
      },
      equipo_lleno: {
        title: "Plantel completo",
        detail: "Ya tienes 15 jugadores.",
        tone: "warning"
      },
      no_players_available: {
        title: "Sin jugadores disponibles",
        detail: "No hay jugadores para generar el equipo.",
        tone: "warning"
      },
      no_valid_random_squad: {
        title: "No se pudo generar equipo",
        detail: "Intenta de nuevo o ajusta el catalogo.",
        tone: "warning"
      },
        round_closed: {
          title: "Ronda cerrada",
          detail: "La ronda esta cerrada. Guardaremos el equipo para la siguiente ronda.",
          tone: "danger"
        },
        out_player_not_in_squad: {
          title: "Jugador no esta en tu plantel",
          detail: "Selecciona un jugador que ya forme parte de tu equipo.",
          tone: "danger"
        },
        in_player_already_in_squad: {
          title: "Jugador ya esta en tu plantel",
          detail: "El jugador elegido ya pertenece a tu equipo.",
          tone: "warning"
        },
      squad_diff_mismatch: {
        title: "Cambios inconsistentes",
        detail: "Revisa el plantel antes de guardar e intenta nuevamente.",
        tone: "danger"
      },
      rounds_not_configured: {
        title: "Sin rondas activas",
        detail: "Carga rondas desde Admin para habilitar Mercado.",
        tone: "warning"
      },
      network_error: {
        title: "Sin conexion",
        detail: "No se puede conectar con el backend. Verifica el servidor.",
        tone: "danger"
      },
      offline_write_blocked: {
        title: "Sin conexion",
        detail: "No puedes guardar cambios sin internet. Modo solo lectura.",
        tone: "warning"
      },
      service_unavailable: {
        title: "Servicio no disponible",
        detail: "El backend esta caido o no responde.",
        tone: "danger"
      },
      endpoint_not_found: {
        title: "Endpoint no encontrado",
        detail: "La API no responde a esta ruta.",
        tone: "danger"
      },
      server_error: {
        title: "Error del servidor",
        detail: "Ocurrio un error interno.",
        tone: "danger"
      }
    };

    if (safeCode.startsWith("players_not_found")) {
      return {
        title: "Jugadores no encontrados",
        detail: safeCode.replace("players_not_found:", "").trim(),
        tone: "danger"
      };
    }

    return (
      messages[safeCode] || {
        title: "Error",
        detail: safeCode,
        tone: "danger"
      }
    );
  };

  const handleOpenPriceHistory = async (player: Player) => {
    setPriceHistoryPlayer(player);
    setPriceHistoryOpen(true);
    setPriceHistoryLoading(true);
    setPriceHistoryError(null);
    setPriceHistoryPoints([]);

    const requestId = priceHistoryRequestId.current + 1;
    priceHistoryRequestId.current = requestId;

    try {
      const points = await getPlayerPriceHistory(player.player_id);
      if (priceHistoryRequestId.current !== requestId) return;
      setPriceHistoryPoints(points);
    } catch (err) {
      if (priceHistoryRequestId.current !== requestId) return;
      const codes = splitErrorCodes(err);
      setPriceHistoryError(codes[0] || "api_error");
    } finally {
      if (priceHistoryRequestId.current === requestId) {
        setPriceHistoryLoading(false);
      }
    }
  };

  const handleConfirmPlayer = async () => {
    if (!inPlayerId) return;
    const incoming = playersBase.find((player) => player.player_id === inPlayerId);
    if (!incoming) return;

    setActionError(null);

    const alreadyInTeam = draftSquad.some((player) => player.player_id === incoming.player_id);
    if (!outPlayerId && draftSquad.length >= 15 && !alreadyInTeam) {
      setActionError("equipo_lleno");
      return;
    }

    const shouldTransfer =
      Boolean(outPlayerId) && Boolean(token) && squad.length === 15 && draftLoaded;

    if (shouldTransfer && outPlayerId && token) {
      try {
        await transferPlayer(token, outPlayerId, incoming.player_id, currentRoundNumber || undefined);
        const team = await getTeam(token);
        setSquad(
          team.squad || [],
          team.budget_cap,
          team.budget_used,
          team.budget_left
        );
        setDraftSquad(team.squad || []);
        setBudgetCap(resolveBudgetCap(team));
        getTransferCount(token)
          .then(setTransferInfo)
          .catch(() => setTransferInfo(null));
        setSaveMessage("Transferencia guardada");
      } catch (err) {
        const codes = splitErrorCodes(err);
        setActionError(codes[0] || "api_error");
        return;
      }
    } else {
      setDraftSquad((prev) => {
        let next = prev;
        if (outPlayerId) {
          next = prev.filter((player) => player.player_id !== outPlayerId);
        }
        if (!next.some((player) => player.player_id === incoming.player_id)) {
          next = [...next, incoming];
        }
        return next;
      });
    }

    setSheetOpen(false);
    setInPlayerId(null);
    setOutPlayerId(null);
  };

  const handleGenerateRandomTeam = async () => {
    setSaveMessage(null);
    setErrorPopup(null);

    setRandomLoading(true);
    try {
      let allPlayers = playersAll;
      if (!allPlayers || allPlayers.length === 0) {
        const limit = 200;
        const maxPages = 10;
        const all: Player[] = [];
        for (let page = 0; page < maxPages; page += 1) {
          const result = await getCatalogPlayers({
            limit,
            offset: page * limit
          });
          all.push(...result);
          if (result.length < limit) break;
        }
        const unique = new Map<number, Player>();
        all.forEach((player) => {
          unique.set(player.player_id, player);
        });
        allPlayers = Array.from(unique.values()).sort((a, b) => b.price_current - a.price_current);
        setPlayersAll(allPlayers);
      }

      if (!allPlayers || allPlayers.length === 0) {
        setErrorPopup([fetchError || "no_players_available"]);
        return;
      }

      const pool = {
        G: allPlayers.filter((player) => player.position === "G"),
        D: allPlayers.filter((player) => player.position === "D"),
        M: allPlayers.filter((player) => player.position === "M"),
        F: allPlayers.filter((player) => player.position === "F")
      };

      const missing: string[] = [];
      if (pool.G.length < 2) missing.push("not_enough_goalkeepers");
      if (pool.D.length < 3) missing.push("not_enough_defenders");
      if (pool.M.length < 3) missing.push("not_enough_midfielders");
      if (pool.F.length < 1) missing.push("not_enough_forwards");
      if (missing.length > 0) {
        setErrorPopup(missing);
        return;
      }

      const combos: { D: number; M: number; F: number }[] = [];
      for (let D = 3; D <= 6; D += 1) {
        for (let M = 3; M <= 6; M += 1) {
          for (let F = 1; F <= 3; F += 1) {
            if (D + M + F === 13) {
              combos.push({ D, M, F });
            }
          }
        }
      }

    const shuffled = <T,>(items: T[]) => {
      const copy = [...items];
      for (let i = copy.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
      }
      return copy;
    };

    const pickWithTeamLimit = (
      items: Player[],
      count: number,
      teamCounts: Record<number, number>
    ) => {
      const selection: Player[] = [];
      for (const player of shuffled(items)) {
        const current = teamCounts[player.team_id] || 0;
        if (current >= 3) continue;
        selection.push(player);
        teamCounts[player.team_id] = current + 1;
        if (selection.length === count) break;
      }
      return selection.length === count ? selection : null;
    };

    const buildCheapestFallback = () => {
      const teamCounts: Record<number, number> = {};
      const pickCheapest = (items: Player[], count: number) => {
        const sorted = [...items].sort((a, b) => a.price_current - b.price_current);
        const selected: Player[] = [];
        for (const player of sorted) {
          const current = teamCounts[player.team_id] || 0;
          if (current >= 3) continue;
          selected.push(player);
          teamCounts[player.team_id] = current + 1;
          if (selected.length === count) break;
        }
        return selected.length === count ? selected : null;
      };

      const baseG = pickCheapest(pool.G, 2);
      const baseD = pickCheapest(pool.D, 3);
      const baseM = pickCheapest(pool.M, 3);
      const baseF = pickCheapest(pool.F, 1);
      if (!baseG || !baseD || !baseM || !baseF) return null;

      let squad = [...baseG, ...baseD, ...baseM, ...baseF];
      const counts = {
        D: baseD.length,
        M: baseM.length,
        F: baseF.length
      };

      const remainingSlots = 15 - squad.length;
      const fillers = [...pool.D, ...pool.M, ...pool.F].sort(
        (a, b) => a.price_current - b.price_current
      );
      for (const player of fillers) {
        if (squad.find((p) => p.player_id === player.player_id)) continue;
        const current = teamCounts[player.team_id] || 0;
        if (current >= 3) continue;
        if (player.position === "D" && counts.D >= 6) continue;
        if (player.position === "M" && counts.M >= 6) continue;
        if (player.position === "F" && counts.F >= 3) continue;
        squad.push(player);
        teamCounts[player.team_id] = current + 1;
        if (player.position === "D") counts.D += 1;
        if (player.position === "M") counts.M += 1;
        if (player.position === "F") counts.F += 1;
        if (squad.length >= 15) break;
      }

      if (squad.length !== 15) return null;
      const errors = validateSquad(squad, budgetCap);
      return errors.length === 0 ? squad : null;
    };

      let squad: Player[] | null = null;
      const maxAttempts = 600;

      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        const combo = combos[Math.floor(Math.random() * combos.length)];
        if (!combo) break;

        const teamCounts: Record<number, number> = {};
        const gk = pickWithTeamLimit(pool.G, 2, teamCounts);
        const defenders = gk ? pickWithTeamLimit(pool.D, combo.D, teamCounts) : null;
        const mids = defenders ? pickWithTeamLimit(pool.M, combo.M, teamCounts) : null;
        const forwards = mids ? pickWithTeamLimit(pool.F, combo.F, teamCounts) : null;

        if (!gk || !defenders || !mids || !forwards) continue;
        const candidate = [...gk, ...defenders, ...mids, ...forwards];
        const errors = validateSquad(candidate, budgetCap);
        if (errors.length === 0) {
          squad = candidate;
          break;
        }
      }

      if (!squad) {
        squad = buildCheapestFallback();
      }

      if (!squad) {
        setErrorPopup(["no_valid_random_squad"]);
        return;
      }

      setDraftSquad(squad);
      setOutPlayerId(null);
      setInPlayerId(null);
      setSheetOpen(false);
    } catch (err) {
      setErrorPopup(splitErrorCodes(err));
    } finally {
      setRandomLoading(false);
    }
  };

  const handleRemoveFromDraft = (playerId: number) => {
    setDraftSquad((prev) => prev.filter((player) => player.player_id !== playerId));
    if (outPlayerId === playerId) {
      setOutPlayerId(null);
    }
  };

  const handleClearTeam = () => {
    setDraftBackup(draftSquad);
    setDraftSquad([]);
    setOutPlayerId(null);
    setInPlayerId(null);
    setSheetOpen(false);
    setErrorPopup(null);
    setSaveMessage(null);
  };

  const handleSaveTeam = () => {
    if (!token) return;
    setErrorPopup(null);
    setSaveMessage(null);
    setPostSavePromptOpen(false);
    setPostSaveLaterOpen(false);
    getTransferCount(token)
      .then(setTransferInfo)
      .catch(() => setTransferInfo(null));
    setConfirmOpen(true);
  };

  const handleConfirmSaveTeam = async () => {
    if (!token) return;
    setErrorPopup(null);
    setSaveMessage(null);
    setSaving(true);
    setConfirmOpen(false);
    const validationErrors = validateSquad(draftSquad, budgetCap);
    if (validationErrors.length > 0) {
      setErrorPopup(validationErrors);
      setSaving(false);
      return;
    }
    try {
      const trimmedName = teamName.trim();
      if (trimmedName) {
        await createTeam(token, trimmedName);
      }
      await updateSquad(
        token,
        draftSquad.map((player) => player.player_id)
      );
      getTransferCount(token)
        .then(setTransferInfo)
        .catch(() => setTransferInfo(null));
      const team = await getTeam(token);
      setSquad(
        team.squad || [],
        team.budget_cap,
        team.budget_used,
        team.budget_left
      );
      setDraftSquad(team.squad || []);
      setTeamName(team.name || trimmedName);
      setSaveMessage("Equipo guardado");
      setPostSavePromptOpen(true);
    } catch (err) {
      const codes = splitErrorCodes(err);
      setErrorPopup(codes.length ? codes : ["api_error"]);
    } finally {
      setSaving(false);
    }
  };

  if (!token) return <AuthPanel />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Mercado</h1>
        <p className="text-sm text-muted">
          Elige 15 jugadores de la Liga 1 con un presupuesto de {budgetCap.toFixed(1)} M.
        </p>
        <p className="mt-1 text-xs text-muted">
          Transferencias ilimitadas sin costo por ronda.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span
            className={
              "rounded-full border px-3 py-1 " +
              (clubRuleOk
                ? "border-emerald-400/40 text-emerald-200"
                : "border-red-400/40 text-red-200")
            }
          >
            Max 3 jugadores del mismo club
          </span>
          <span
            className="rounded-full border border-emerald-400/40 px-3 py-1 text-emerald-200"
          >
            Transferencias ilimitadas
          </span>
        </div>
      </div>

      <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-emerald-700/55 via-emerald-900/45 to-black/35 p-4">
          <div className="pointer-events-none absolute inset-4 rounded-2xl border border-white/10" />
          <div className="pointer-events-none absolute left-4 right-4 top-1/2 h-px bg-white/10" />
          <div className="pointer-events-none absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10" />
          <div className="relative z-10 flex min-h-[520px] flex-col justify-between gap-6 py-3">
            <PitchRow
              label="Ataque"
              players={playersByPosition.F}
              onSelect={(player) => {
                setOutPlayerId(player.player_id);
                if (inPlayerId) setSheetOpen(true);
              }}
              onRemove={handleRemoveFromDraft}
              selectedOutId={outPlayerId}
            />
            <PitchRow
              label="Medio"
              players={playersByPosition.M}
              onSelect={(player) => {
                setOutPlayerId(player.player_id);
                if (inPlayerId) setSheetOpen(true);
              }}
              onRemove={handleRemoveFromDraft}
              selectedOutId={outPlayerId}
            />
            <PitchRow
              label="Defensa"
              players={playersByPosition.D}
              onSelect={(player) => {
                setOutPlayerId(player.player_id);
                if (inPlayerId) setSheetOpen(true);
              }}
              onRemove={handleRemoveFromDraft}
              selectedOutId={outPlayerId}
            />
            <PitchRow
              label="Arquero"
              players={playersByPosition.G}
              onSelect={(player) => {
                setOutPlayerId(player.player_id);
                if (inPlayerId) setSheetOpen(true);
              }}
              onRemove={handleRemoveFromDraft}
              selectedOutId={outPlayerId}
            />
          </div>
      </div>

        <div className="glass rounded-2xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted">Seleccionados</p>
              <p className="text-lg font-semibold text-ink">{draftSquad.length}/15</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted">Presupuesto</p>
              <p className="text-lg font-semibold text-accent">{draftBudget.toFixed(1)}</p>
              <p className="text-xs text-muted">Restante {budgetLeft.toFixed(1)}</p>
            </div>
          </div>
          {saveMessage ? <p className="mt-2 text-xs text-accent2">{saveMessage}</p> : null}
          <button
            onClick={handleGenerateRandomTeam}
            disabled={randomLoading}
            className="mt-3 w-full rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-ink"
          >
            {randomLoading ? "Generando..." : "Generar equipo aleatorio"}
          </button>
          <button
            onClick={handleSaveTeam}
            disabled={draftSquad.length !== 15 || saving}
            className={
              "mt-2 w-full rounded-xl px-4 py-2 text-sm font-semibold " +
              (draftSquad.length === 15
                ? "bg-accent text-black"
                : "border border-white/10 text-muted")
            }
          >
            Guardar Equipo
          </button>
          <button
            onClick={handleClearTeam}
            className="mt-2 w-full rounded-xl bg-red-500/80 px-4 py-2 text-sm font-semibold text-white"
          >
            Limpiar Equipo
          </button>
        </div>

        <MarketFilters
          value={filters}
          onChange={setFilters}
          priceBounds={priceBounds}
          teams={activeTeams}
        />
        {fetchError ? (
          <p className="text-xs text-warning">Error cargando jugadores: {fetchError}</p>
        ) : null}
        {!fetchError && loadingPlayers ? (
          <p className="text-xs text-muted">Cargando jugadores...</p>
        ) : null}
        {!fetchError && !loadingPlayers && filteredPlayers.length === 0 ? (
          <p className="text-xs text-muted">Sin resultados con los filtros actuales.</p>
        ) : null}

        <div ref={parentRef} className="scrollbar-hide h-[50vh] overflow-auto">
          <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: "relative" }}>
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const player = filteredPlayers[virtualRow.index];
              if (!player) return null;
              return (
                <div
                  key={player.player_id}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${virtualRow.start}px)`
                  }}
                >
                  <PlayerCard
                    player={player}
                    compact
                    showPoints
                    onPriceDeltaClick={handleOpenPriceHistory}
                    onClick={() => {
                      setInPlayerId(player.player_id);
                      setSheetOpen(true);
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>

      <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)} title="Confirmar jugador">
        <div className="max-h-[70vh] space-y-4 overflow-auto pr-1">
          <div>
            <p className="text-xs uppercase text-muted">Sale</p>
            {outPlayer ? (
              <div className="space-y-2">
                <PlayerCard player={outPlayer} compact showPoints />
                <MarketPlayerDetails player={outPlayer} fixtures={fixtures} />
              </div>
            ) : (
              <p className="text-xs text-muted">Sin reemplazo</p>
            )}
          </div>
          <div>
            <p className="text-xs uppercase text-muted">Entra</p>
            {inPlayer ? (
              <div className="space-y-2">
                <PlayerCard player={inPlayer} compact showPoints />
                <MarketPlayerDetails player={inPlayer} fixtures={fixtures} />
              </div>
            ) : (
              <p className="text-xs text-muted">Selecciona en mercado</p>
            )}
          </div>
          {transferInfo ? (
            <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-xs text-muted">
              <p>
                Transferencias realizadas en la ronda:{" "}
                <span className="font-semibold text-ink">{transferInfo.transfers_used}</span>
              </p>
            </div>
          ) : null}
          {actionError ? (
            <div className="rounded-xl border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
              {formatError(actionError).title}
            </div>
          ) : null}
          <button
            onClick={handleConfirmPlayer}
            disabled={!inPlayerId}
            className={
              "w-full rounded-xl px-4 py-2 text-sm font-semibold " +
              (inPlayerId ? "bg-accent text-black" : "border border-white/10 text-muted")
            }
          >
            Confirmar en equipo
          </button>
        </div>
      </BottomSheet>

      <BottomSheet
        open={priceHistoryOpen}
        onClose={() => setPriceHistoryOpen(false)}
        title="Evolucion de precio"
      >
        <div className="max-h-[70vh] space-y-4 overflow-auto pr-1">
          {priceHistoryPlayer ? (
            <div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-2">
              <p className="text-sm font-semibold text-ink">
                {priceHistoryPlayer.short_name || priceHistoryPlayer.shortName || priceHistoryPlayer.name}
              </p>
              <p className="text-xs text-muted">
                Precio actual {priceHistoryPlayer.price_current.toFixed(1)}
              </p>
            </div>
          ) : null}
          {priceHistoryLoading ? (
            <p className="text-xs text-muted">Cargando evolucion...</p>
          ) : null}
          {!priceHistoryLoading && priceHistoryError ? (
            <div className="rounded-xl border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
              {formatError(priceHistoryError).title}
            </div>
          ) : null}
          {!priceHistoryLoading && !priceHistoryError && priceHistoryPoints.length === 0 ? (
            <p className="text-xs text-muted">Sin historial de precios para este jugador.</p>
          ) : null}
          {!priceHistoryLoading && !priceHistoryError && priceHistoryPoints.length > 0 ? (
            <PriceHistoryLineChart points={priceHistoryPoints} />
          ) : null}
        </div>
      </BottomSheet>

      {errorPopup ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Error</p>
              <button
                onClick={() => setErrorPopup(null)}
                className="text-xs text-muted"
                aria-label="Cerrar"
              >
                X
              </button>
            </div>
            <div className="mt-3 space-y-2 text-xs">
              {errorPopup.map((error) => {
                const info = formatError(error);
                const toneClass =
                  info.tone === "danger"
                    ? "border-red-400/40 bg-red-500/10 text-red-200"
                    : "border-amber-400/40 bg-amber-500/10 text-amber-200";
                return (
                  <div
                    key={error}
                    className={`rounded-xl border px-3 py-2 ${toneClass}`}
                  >
                    <p className="font-semibold">{info.title}</p>
                    {info.detail ? <p className="text-[11px] opacity-90">{info.detail}</p> : null}
                  </div>
                );
              })}
            </div>
            <button
              onClick={() => setErrorPopup(null)}
              className="mt-4 w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
            >
              Entendido
            </button>
          </div>
        </div>
      ) : null}

      {confirmOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm space-y-4 rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Confirmar guardado</p>
              <button
                onClick={() => setConfirmOpen(false)}
                className="text-xs text-muted"
                aria-label="Cerrar"
              >
                X
              </button>
            </div>
            <p className="text-xs text-muted">
              Estas seguro que quieres guardar este equipo?
            </p>
            <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-muted">
              <p>
                Transferencias detectadas:{" "}
                <span className="font-semibold text-ink">{transferPreview.transferCount}</span>
              </p>
              <p>
                Transferencias ya usadas en la ronda:{" "}
                <span className="font-semibold text-ink">{transferPreview.transfersUsed}</span>
              </p>
              {transferPreview.transferCount > 0 ? (
                <div className="mt-2 space-y-1 rounded-xl border border-white/10 bg-black/20 p-2 text-[11px]">
                  <p className="font-semibold text-ink">Preboleta de cambios</p>
                  {Array.from({ length: transferPreview.transferCount }).map((_, index) => {
                    const out = transferPreview.outgoing[index];
                    const incoming = transferPreview.incoming[index];
                    return (
                      <p key={`${out?.player_id ?? "out"}-${incoming?.player_id ?? "in"}-${index}`}>
                        {out?.short_name || out?.name || "?"} {"->"} {incoming?.short_name || incoming?.name || "?"}
                      </p>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-2 text-[11px]">No hay transferencias pendientes en este guardado.</p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setConfirmOpen(false)}
                className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmSaveTeam}
                disabled={saving}
                className={
                  "flex-1 rounded-xl px-4 py-2 text-sm font-semibold " +
                  (!saving ? "bg-accent text-black" : "border border-white/10 text-muted")
                }
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {postSavePromptOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm space-y-4 rounded-2xl border border-white/10 p-4 text-sm text-ink">
            <p className="text-base font-semibold">Equipo guardado</p>
            <p className="text-xs text-muted">
              Ahora debes seleccionar tu XI titular para la ronda activa.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setPostSavePromptOpen(false);
                  router.push("/team");
                }}
                className="flex-1 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
              >
                Elegir XI titular
              </button>
              <button
                onClick={() => {
                  setPostSavePromptOpen(false);
                  setPostSaveLaterOpen(true);
                }}
                className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
              >
                Mas tarde
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {postSaveLaterOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm space-y-4 rounded-2xl border border-white/10 p-4 text-sm text-ink">
            <p className="text-base font-semibold">Recordatorio</p>
            <p className="text-xs text-muted">
              La siguiente ronda empieza el {nextRoundStartLabel}.
            </p>
            <button
              onClick={() => setPostSaveLaterOpen(false)}
              className="w-full rounded-xl bg-surface2/60 px-4 py-2 text-sm text-ink"
            >
              Entendido
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

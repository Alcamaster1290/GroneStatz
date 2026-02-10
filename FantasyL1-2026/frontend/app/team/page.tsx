"use client";

import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors
} from "@dnd-kit/core";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import AuthPanel from "@/components/AuthPanel";
import BottomSheet from "@/components/BottomSheet";
import DraggablePlayer from "@/components/DraggablePlayer";
import FabMenu from "@/components/FabMenu";
import FavoriteTeamGate from "@/components/FavoriteTeamGate";
import LineupSlotCard from "@/components/LineupSlotCard";
import PlayerCard from "@/components/PlayerCard";
import PlayerAvatarSquare from "@/components/PlayerAvatarSquare";
import StickyTopBar from "@/components/StickyTopBar";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import {
  createTeam,
  getFixtures,
  getHealth,
  getLineup,
  getPlayerMatches,
  getRounds,
  getTeam,
  getTeams,
  saveLineup,
  updateFavoriteTeam
} from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { Fixture, LineupSlot, Player, PlayerMatch, RoundInfo } from "@/lib/types";
import { validateLineup } from "@/lib/validation";

const DEFAULT_SLOTS: LineupSlot[] = [
  { slot_index: 0, is_starter: true, role: "G", player_id: null },
  { slot_index: 1, is_starter: true, role: "D", player_id: null },
  { slot_index: 2, is_starter: true, role: "D", player_id: null },
  { slot_index: 3, is_starter: true, role: "D", player_id: null },
  { slot_index: 4, is_starter: true, role: "D", player_id: null },
  { slot_index: 5, is_starter: true, role: "M", player_id: null },
  { slot_index: 6, is_starter: true, role: "M", player_id: null },
  { slot_index: 7, is_starter: true, role: "M", player_id: null },
  { slot_index: 8, is_starter: true, role: "M", player_id: null },
  { slot_index: 9, is_starter: true, role: "F", player_id: null },
  { slot_index: 10, is_starter: true, role: "F", player_id: null },
  { slot_index: 11, is_starter: false, role: "G", player_id: null },
  { slot_index: 12, is_starter: false, role: "D", player_id: null },
  { slot_index: 13, is_starter: false, role: "M", player_id: null },
  { slot_index: 14, is_starter: false, role: "F", player_id: null }
];

const buildDefaultSlots = () => DEFAULT_SLOTS.map((slot) => ({ ...slot }));

const safeSaveDraft = (key: string, payload: unknown) => {
  try {
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    try {
      localStorage.removeItem(key);
    } catch {
      // ignore
    }
  }
};

type LineupSnapshot = {
  roundNumber: number | null;
  slots: Array<Pick<LineupSlot, "slot_index" | "is_starter" | "role" | "player_id">>;
  captainId: number | null;
  viceCaptainId: number | null;
};

const sanitizeLineupSlots = (slots: LineupSlot[]) =>
  slots
    .map((slot) => ({
      slot_index: slot.slot_index,
      is_starter: slot.is_starter,
      role: slot.role,
      player_id: slot.player_id ?? null
    }))
    .sort((a, b) => a.slot_index - b.slot_index);

const buildLineupSnapshot = (
  roundNumber: number | null,
  slots: LineupSlot[],
  captainId: number | null,
  viceCaptainId: number | null
): LineupSnapshot => ({
  roundNumber,
  slots: sanitizeLineupSlots(slots),
  captainId: captainId ?? null,
  viceCaptainId: viceCaptainId ?? null
});

const lineupSnapshotsEqual = (a: LineupSnapshot | null, b: LineupSnapshot): boolean => {
  if (!a) return false;
  if (a.roundNumber !== b.roundNumber) return false;
  if ((a.captainId ?? null) !== (b.captainId ?? null)) return false;
  if ((a.viceCaptainId ?? null) !== (b.viceCaptainId ?? null)) return false;
  if (a.slots.length !== b.slots.length) return false;
  for (let index = 0; index < a.slots.length; index += 1) {
    const left = a.slots[index];
    const right = b.slots[index];
    if (!right) return false;
    if (left.slot_index !== right.slot_index) return false;
    if (left.is_starter !== right.is_starter) return false;
    if (left.role !== right.role) return false;
    if ((left.player_id ?? null) !== (right.player_id ?? null)) return false;
  }
  return true;
};

function PlayerFace({ playerId, sizeClass }: { playerId: number; sizeClass: string }) {
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
      <div
        className={`flex ${sizeClass} items-center justify-center rounded-full bg-surface2/80 ring-1 ring-white/10`}
      />
    );
  }

  return (
    <div className={`${sizeClass} overflow-hidden rounded-full ring-1 ring-white/10`}>
      <img
        src={sources[srcIndex]}
        alt=""
        className="h-full w-full object-cover"
        onError={handleError}
      />
    </div>
  );
}

function TeamBadge({ teamId, sizeClass }: { teamId: number; sizeClass: string }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <span
      className={`absolute -bottom-1 -right-1 flex ${sizeClass} -translate-x-[10%] -translate-y-[10%] items-center justify-center`}
    >
      <img
        src={`/images/teams/${teamId}.png`}
        alt=""
        className="h-full w-full object-contain"
        onError={() => setHidden(true)}
      />
    </span>
  );
}

const positionLabels: Record<string, string> = {
  G: "Arquero",
  D: "Defensa",
  M: "Mediocampo",
  F: "Delantero"
};

function PlayerFantasyDetails({
  player,
  teamName,
  matches,
  loadingMatches
}: {
  player: Player;
  teamName?: string;
  matches: PlayerMatch[];
  loadingMatches?: boolean;
}) {
  const displayName = player.short_name || player.shortName || player.name;
  const isKeeper = player.position === "G";
  const points =
    typeof player.points_total === "number" ? player.points_total.toFixed(1) : "--";
  const hasRoundStats =
    typeof player.goals_round === "number" ||
    typeof player.assists_round === "number" ||
    typeof player.saves_round === "number";
  const primaryStatLabel = isKeeper
    ? hasRoundStats
      ? "Atajadas (Ronda)"
      : "Atajadas"
    : hasRoundStats
      ? "Goles (Ronda)"
      : "Goles";
  const primaryStatValue = isKeeper
    ? hasRoundStats
      ? player.saves_round ?? 0
      : player.saves ?? 0
    : hasRoundStats
      ? player.goals_round ?? 0
      : player.goals ?? 0;
  const secondaryStatLabel = isKeeper
    ? "Goles recibidos"
    : hasRoundStats
      ? "Asistencias (Ronda)"
      : "Asistencias";
  const secondaryStatValue = isKeeper
    ? player.goals_conceded ?? 0
    : hasRoundStats
      ? player.assists_round ?? 0
      : player.assists ?? 0;
  const formatKickoff = (kickoff: string | null | undefined) => {
    if (!kickoff) return "Por confirmar";
    const normalized = kickoff.replace("T", " ").trim();
    const [datePart, timePart] = normalized.split(" ");
    const [year, month, day] = datePart.split("-");
    const shortYear = year ? year.slice(2) : "";
    const time = timePart ? timePart.slice(0, 5) : "";
    return `${day}/${month}/${shortYear}${time ? `, ${time}` : ""}`;
  };
  const teamMatches = matches
    .slice()
    .sort((a, b) => {
      const aKey = a.kickoff_at ? a.kickoff_at : "9999-99-99";
      const bKey = b.kickoff_at ? b.kickoff_at : "9999-99-99";
      return aKey.localeCompare(bKey);
    });
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <PlayerFace playerId={player.player_id} sizeClass="h-12 w-12" />
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
          <p className="text-[11px] text-muted">{teamName || ""}</p>
        </div>
      </div>
      {player.is_injured ? (
        <div className="flex items-center gap-2 rounded-xl bg-red-500/80 px-3 py-2 text-xs font-semibold text-black">
          <span>!</span>
          <span>Lesionado</span>
        </div>
      ) : null}
      <div className="grid grid-cols-2 gap-2 rounded-2xl border border-white/10 bg-black/20 p-3 text-xs">
        <div className="space-y-1">
          <p className="text-[10px] uppercase text-muted">Puntaje total</p>
          <p className="text-sm font-semibold text-ink">{points}</p>
        </div>
        <div className="space-y-1">
          <p className="text-[10px] uppercase text-muted">{primaryStatLabel}</p>
          <p className="text-sm font-semibold text-ink">{primaryStatValue}</p>
        </div>
        <div className="space-y-1">
          <p className="text-[10px] uppercase text-muted">{secondaryStatLabel}</p>
          <p className="text-sm font-semibold text-ink">{secondaryStatValue}</p>
        </div>
        <div className="space-y-1">
          <p className="text-[10px] uppercase text-muted">Precio</p>
          <p className="text-sm font-semibold text-accent">{player.price_current.toFixed(1)}</p>
        </div>
      </div>
      <div className="space-y-2">
        <p className="text-xs font-semibold text-ink">Partidos</p>
        {loadingMatches ? (
          <p className="text-xs text-muted">Cargando partidos...</p>
        ) : teamMatches.length ? (
          <div className="space-y-2">
            {teamMatches.map((fixture) => {
              const homeId = fixture.home_team_id;
              const awayId = fixture.away_team_id;
              const pointsLabel =
                typeof fixture.points === "number"
                  ? Math.trunc(fixture.points).toString()
                  : "--";
              const statLine = [
                `Min ${fixture.minutesplayed ?? 0}`,
                `G ${fixture.goals ?? 0}`,
                `A ${fixture.assists ?? 0}`
              ];
              if (isKeeper) {
                statLine.push(`Atj ${fixture.saves ?? 0}`);
                statLine.push(`GC ${fixture.goals_conceded ?? 0}`);
              } else if (player.position === "D") {
                statLine.push(`GC ${fixture.goals_conceded ?? 0}`);
              }
              return (
                <div
                  key={fixture.match_id}
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
                  <div className="flex flex-col items-end gap-1 text-right text-[10px] text-muted">
                    <p>{formatKickoff(fixture.kickoff_at)}</p>
                    <p className="text-ink">Pts {pointsLabel}</p>
                    <p className="text-[9px] text-muted">{statLine.join(" \u00B7 ")}</p>
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

function PitchSlot({
  slot,
  player,
  opponent,
  onClick,
  sizeClass,
  badgeClass,
  isCaptain,
  isViceCaptain,
  showPoints
}: {
  slot: LineupSlot;
  player?: Player;
  opponent?: { teamId: number; name?: string };
  onClick?: () => void;
  sizeClass: string;
  badgeClass: string;
  isCaptain: boolean;
  isViceCaptain: boolean;
  showPoints: boolean;
}) {
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `slot-${slot.slot_index}`,
    data: { slotIndex: slot.slot_index }
  });

  const { attributes, listeners, setNodeRef: setDragRef, transform, isDragging } = useDraggable({
    id: player ? `player-${player.player_id}` : `slot-${slot.slot_index}-empty`,
    data: { playerId: player?.player_id, slotIndex: slot.slot_index },
    disabled: !player
  });

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  const displayName = player ? player.short_name || player.shortName || player.name : "Disponible";
  const rawPoints =
    typeof slot.points_with_bonus === "number"
      ? slot.points_with_bonus
      : typeof slot.points_round === "number"
        ? slot.points_round
        : player && typeof player.points_round === "number"
          ? player.points_round
          : null;
  const pointsValue = typeof rawPoints === "number" ? Math.trunc(rawPoints) : null;

  return (
    <div ref={setDropRef}>
      <button
        ref={setDragRef}
        style={style}
        onClick={onClick}
        {...listeners}
        {...attributes}
        className={
          "flex flex-col items-center gap-1 rounded-2xl px-2 py-2 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent " +
          "cursor-grab active:cursor-grabbing " +
          (isOver ? "ring-2 ring-accent scale-[1.03] " : "") +
          (isDragging ? "opacity-0" : "")
        }
      >
          <div className="relative">
            {player ? (
              <>
                <PlayerFace playerId={player.player_id} sizeClass={sizeClass} />
                <TeamBadge teamId={player.team_id} sizeClass={badgeClass} />
                {isCaptain ? (
                  <span
                    className={`absolute -bottom-1 -left-1 z-30 flex ${badgeClass} -translate-x-[10%] -translate-y-[10%] items-center justify-center rounded-full bg-yellow-300 text-[10px] font-bold text-black`}
                  >
                    C
                  </span>
                ) : null}
                {isViceCaptain ? (
                  <span
                    className={`absolute -bottom-1 -left-1 z-30 flex ${badgeClass} -translate-x-[10%] -translate-y-[10%] items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-black`}
                  >
                    V
                  </span>
                ) : null}
                {showPoints && pointsValue !== null ? (
                  <span className="absolute -top-1 -right-1 z-30 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-black/80 px-1 text-[10px] font-semibold text-ink">
                    {pointsValue}
                  </span>
                ) : null}
              </>
            ) : (
              <div
                className={`flex ${sizeClass} items-center justify-center rounded-full bg-surface2/30`}
              />
          )}
        </div>
        <span className="max-w-[96px] truncate text-[10px] text-ink">{displayName}</span>
        {player && opponent ? (
          <span className="flex items-center gap-1 text-[9px] text-muted">
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
          </span>
        ) : null}
      </button>
    </div>
  );
}

function PitchRow({
  label,
  slots,
  squadMap,
  opponentByTeamId,
  onSelect,
  sizeClass,
  badgeClass,
  captainId,
  viceCaptainId,
  showPoints
}: {
  label: string;
  slots: LineupSlot[];
  squadMap: Map<number, Player>;
  opponentByTeamId: Map<number, { teamId: number; name?: string }>;
  onSelect: (slot: LineupSlot) => void;
  sizeClass: string;
  badgeClass: string;
  captainId: number | null;
  viceCaptainId: number | null;
  showPoints: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">{label}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {slots.map((slot) => {
            const player =
              (slot.player_id ? squadMap.get(slot.player_id) : undefined) ||
              (slot.player ?? undefined);
            const opponent = player ? opponentByTeamId.get(player.team_id) : undefined;
            return (
              <PitchSlot
                key={slot.slot_index}
                slot={slot}
                player={player}
                opponent={opponent}
                onClick={() => onSelect(slot)}
                sizeClass={sizeClass}
                badgeClass={badgeClass}
                isCaptain={Boolean(player && captainId === player.player_id)}
                isViceCaptain={Boolean(player && viceCaptainId === player.player_id)}
                showPoints={showPoints}
              />
            );
          })}
        </div>
      </div>
  );
}

export default function TeamPage() {
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const squad = useFantasyStore((state) => state.squad);
  const setSquad = useFantasyStore((state) => state.setSquad);
  const lineupSlots = useFantasyStore((state) => state.lineupSlots);
  const setLineupSlots = useFantasyStore((state) => state.setLineupSlots);
  const budgetUsed = useFantasyStore((state) => state.budgetUsed);
  const budgetLeft = useFantasyStore((state) => state.budgetLeft);
  const currentRound = useFantasyStore((state) => state.currentRound);
  const setCurrentRound = useFantasyStore((state) => state.setCurrentRound);
  const captainId = useFantasyStore((state) => state.captainId);
  const setCaptainId = useFantasyStore((state) => state.setCaptainId);
  const viceCaptainId = useFantasyStore((state) => state.viceCaptainId);
  const setViceCaptainId = useFantasyStore((state) => state.setViceCaptainId);
  const userEmail = useFantasyStore((state) => state.userEmail);

  const [loading, setLoading] = useState(false);
  const [activePlayerId, setActivePlayerId] = useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [starterPickerOpen, setStarterPickerOpen] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<LineupSlot | null>(null);
  const [saveErrors, setSaveErrors] = useState<string[] | null>(null);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [allFixtures, setAllFixtures] = useState<Fixture[]>([]);
  const [playerMatches, setPlayerMatches] = useState<PlayerMatch[]>([]);
  const [playerMatchesLoading, setPlayerMatchesLoading] = useState(false);
  const [playerMatchesError, setPlayerMatchesError] = useState<string | null>(null);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>(
    []
  );
  const [roundsInfo, setRoundsInfo] = useState<RoundInfo[]>([]);
  const [roundStatus, setRoundStatus] = useState<string | null>(null);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [appEnv, setAppEnv] = useState<string>("local");
  const [roundMissing, setRoundMissing] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [favoriteTeamId, setFavoriteTeamId] = useState<number | null>(null);
  const [needsTeamName, setNeedsTeamName] = useState(false);
  const [needsFavoriteTeam, setNeedsFavoriteTeam] = useState(false);
  const [teamLoaded, setTeamLoaded] = useState(false);
  const [isNewTeam, setIsNewTeam] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);
  const [favoriteGateOpen, setFavoriteGateOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [postWelcomeRedirect, setPostWelcomeRedirect] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);
  const [favoriteError, setFavoriteError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [marketPriceDelta, setMarketPriceDelta] = useState<number | null>(null);
  const [savedLineupSnapshot, setSavedLineupSnapshot] = useState<LineupSnapshot | null>(null);
  const router = useRouter();
  const [deltaOpen, setDeltaOpen] = useState(false);

  const formatError = (code: string) => {
    const positionCounts = squad.reduce(
      (acc, player) => {
        acc[player.position] = (acc[player.position] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
    const messages: Record<
      string,
      { title: string; detail?: string; tone?: "warning" | "danger" }
    > = {
      lineup_must_have_15_slots: {
        title: "Faltan slots",
        detail: "Debe existir un total de 15 slots (11 titulares y 4 suplentes).",
        tone: "warning"
      },
      lineup_slot_index_duplicate: {
        title: "Slots duplicados",
        detail: "Se detectaron slots repetidos en el XI.",
        tone: "danger"
      },
      lineup_requires_11_starters_and_4_bench: {
        title: "XI incompleto",
        detail: "Asegura 11 titulares y 4 suplentes.",
        tone: "warning"
      },
      lineup_has_empty_slots: {
        title: "Slots vacios",
        detail: "Completa todos los espacios antes de guardar.",
        tone: "warning"
      },
      lineup_has_duplicate_players: {
        title: "Jugadores repetidos",
        detail: "Un jugador esta asignado mas de una vez.",
        tone: "danger"
      },
      lineup_players_not_in_squad: {
        title: "Jugadores fuera del plantel",
        detail: "Hay jugadores que no pertenecen a tu equipo guardado.",
        tone: "danger"
      },
      lineup_starters_need_goalkeeper: {
        title: "Arquero faltante",
        detail: "El XI necesita 1 arquero titular.",
        tone: "warning"
      },
      lineup_starters_max_1_goalkeeper: {
        title: "Demasiados arqueros",
        detail: "Solo puedes tener 1 arquero en titulares.",
        tone: "warning"
      },
      lineup_starters_need_defender: {
        title: "Defensas insuficientes",
        detail: "Debe haber al menos 1 defensor en titulares.",
        tone: "warning"
      },
      lineup_starters_need_midfielder: {
        title: "Mediocampistas insuficientes",
        detail: "Debe haber al menos 1 mediocampista en titulares.",
        tone: "warning"
      },
      lineup_starters_need_forward: {
        title: "Delanteros insuficientes",
        detail: "Debe haber al menos 1 delantero en titulares.",
        tone: "warning"
      },
      lineup_starters_max_4_forwards: {
        title: "Demasiados delanteros",
        detail: "Maximo 4 delanteros en titulares.",
        tone: "warning"
      },
      captain_not_in_lineup: {
        title: "Capitan invalido",
        detail: "El capitan debe estar en el XI.",
        tone: "warning"
      },
      captain_not_in_starting_xi: {
        title: "Capitan en banca",
        detail: "El capitan debe ser titular.",
        tone: "warning"
      },
      vice_captain_not_in_lineup: {
        title: "Vice invalido",
        detail: "El vicecapitan debe estar en el XI.",
        tone: "warning"
      },
      vice_captain_not_in_starting_xi: {
        title: "Vice en banca",
        detail: "El vicecapitan debe ser titular.",
        tone: "warning"
      },
      captain_and_vice_same_player: {
        title: "Capitan duplicado",
        detail: "Capitan y vicecapitan no pueden ser el mismo jugador.",
        tone: "warning"
      },
      round_closed: {
        title: "Ronda cerrada",
        detail: "La ronda esta cerrada. No puedes guardar cambios.",
        tone: "danger"
      },
      rounds_not_configured: {
        title: "Sin rondas activas",
        detail: "Carga rondas desde Admin para habilitar el XI.",
        tone: "warning"
      },
      squad_must_have_15_players: {
        title: "Plantel incompleto",
        detail: `Tienes ${squad.length}/15 jugadores.`,
        tone: "warning"
      },
      squad_must_have_2_goalkeepers: {
        title: "Arqueros incompletos",
        detail: `Necesitas 2 arqueros. Tienes ${positionCounts.G || 0}.`,
        tone: "warning"
      },
      squad_defenders_out_of_range: {
        title: "Defensas fuera de rango",
        detail: `Debes tener entre 3 y 6 defensas. Tienes ${positionCounts.D || 0}.`,
        tone: "warning"
      },
      squad_midfielders_out_of_range: {
        title: "Mediocampistas fuera de rango",
        detail: `Debes tener entre 3 y 6 mediocampistas. Tienes ${positionCounts.M || 0}.`,
        tone: "warning"
      },
      squad_forwards_out_of_range: {
        title: "Delanteros fuera de rango",
        detail: `Debes tener entre 1 y 3 delanteros. Tienes ${positionCounts.F || 0}.`,
        tone: "warning"
      },
      max_3_players_per_team: {
        title: "Maximo 3 por club",
        detail: "Hay un club con mas de 3 jugadores.",
        tone: "danger"
      },
      budget_exceeded: {
        title: "Presupuesto excedido",
        detail: "Tu plantel supera los 100 M.",
        tone: "danger"
      },
      round_not_found: {
        title: "Ronda no encontrada",
        detail: "La ronda solicitada no existe.",
        tone: "warning"
      },
      offline_write_blocked: {
        title: "Sin conexion",
        detail: "No puedes guardar cambios sin internet. Modo solo lectura.",
        tone: "warning"
      }
    };

    return (
      messages[code] || {
        title: "Error",
        detail: code,
        tone: "danger"
      }
    );
  };

  const squadMap = useMemo(
    () => new Map(squad.map((player) => [player.player_id, player])),
    [squad]
  );

  const draftKey = useMemo(() => {
    const safeEmail = userEmail && userEmail.trim() ? userEmail.trim() : "anon";
    const round = currentRound ?? "none";
    return `fantasy_lineup_draft_${safeEmail}_${round}`;
  }, [userEmail, currentRound]);

  useEffect(() => {
    if (captainId && !squadMap.get(captainId)) {
      setCaptainId(null);
    }
    if (viceCaptainId && !squadMap.get(viceCaptainId)) {
      setViceCaptainId(null);
    }
  }, [captainId, viceCaptainId, squadMap, setCaptainId, setViceCaptainId]);
  const assignedIds = useMemo(() => {
    const ids = new Set<number>();
    lineupSlots.forEach((slot) => {
      if (slot.player_id) {
        ids.add(slot.player_id);
      }
    });
    return ids;
  }, [lineupSlots]);
  const availablePlayers = useMemo(
    () => squad.filter((player) => !assignedIds.has(player.player_id)),
    [squad, assignedIds]
  );
  const positionOrder: Record<string, number> = { G: 0, D: 1, M: 2, F: 3 };
  const sortedAvailablePlayers = useMemo(() => {
    return [...availablePlayers].sort((a, b) => {
      const diff = (positionOrder[a.position] ?? 99) - (positionOrder[b.position] ?? 99);
      if (diff !== 0) return diff;
      return a.name.localeCompare(b.name);
    });
  }, [availablePlayers]);
  const availablePlayersSorted = useMemo(() => {
    const order: Record<string, number> = { G: 0, D: 1, M: 2, F: 3 };
    return [...availablePlayers].sort((a, b) => {
      const diff = (order[a.position] ?? 99) - (order[b.position] ?? 99);
      if (diff !== 0) return diff;
      return a.name.localeCompare(b.name);
    });
  }, [availablePlayers]);
  const teamNameById = useMemo(() => {
    const map = new Map<number, string>();
    teams.forEach((team) => {
      map.set(team.id, team.name_short || team.name_full || `Equipo ${team.id}`);
    });
    return map;
  }, [teams]);
  const opponentByTeamId = useMemo(() => {
    const map = new Map<number, { teamId: number; name?: string }>();
    fixtures.forEach((fixture) => {
      if (!fixture.home_team_id || !fixture.away_team_id) return;
      const homeName = teamNameById.get(fixture.away_team_id);
      const awayName = teamNameById.get(fixture.home_team_id);
      map.set(fixture.home_team_id, { teamId: fixture.away_team_id, name: homeName });
      map.set(fixture.away_team_id, { teamId: fixture.home_team_id, name: awayName });
    });
    return map;
  }, [fixtures, teamNameById]);

  const roundDateRange = useMemo(() => {
    if (!fixtures.length) return null;
    const parsed = fixtures
      .map((fixture) => {
        const raw = fixture.kickoff_at ? String(fixture.kickoff_at).trim() : "";
        if (!raw) return null;
        const datePart = raw.split("T")[0].split(" ")[0];
        const [year, month, day] = datePart.split("-").map((part) => Number(part));
        if (!year || !month || !day) return null;
        return { year, month, day, key: `${year}-${month}-${day}` };
      })
      .filter((value): value is { year: number; month: number; day: number; key: string } => value !== null);
    if (!parsed.length) return null;
    parsed.sort((a, b) => {
      if (a.year !== b.year) return a.year - b.year;
      if (a.month !== b.month) return a.month - b.month;
      return a.day - b.day;
    });
    const first = parsed[0];
    const last = parsed[parsed.length - 1];
    return {
      min: `${first.day}/${first.month}`,
      max: `${last.day}/${last.month}`
    };
  }, [fixtures]);

  const nextFixture = useMemo(() => {
    const withKickoff = fixtures
      .filter((fixture) => fixture.kickoff_at)
      .slice()
      .sort((a, b) => String(a.kickoff_at).localeCompare(String(b.kickoff_at)));
    return withKickoff[0] ?? null;
  }, [fixtures]);

  const availableRounds = useMemo(() => {
    const configuredRounds = Array.from(
      new Set(
        roundsInfo
          .map((round) => round.round_number)
          .filter((round) => Number.isFinite(round))
      )
    ).sort((a, b) => a - b);
    if (configuredRounds.length) {
      return configuredRounds;
    }

    const fixtureRounds = Array.from(new Set(allFixtures.map((fixture) => fixture.round_number)))
      .filter((round) => Number.isFinite(round))
      .sort((a, b) => a - b);
    if (!fixtureRounds.length && currentRound) return [currentRound];
    return fixtureRounds;
  }, [roundsInfo, allFixtures, currentRound]);

  const roundIndex = useMemo(() => {
    if (!currentRound) return -1;
    return availableRounds.indexOf(currentRound);
  }, [availableRounds, currentRound]);

  const teamRoundPoints = useMemo(() => {
    if (!currentRound) return null;
    let total = 0;
    lineupSlots.forEach((slot) => {
      if (!slot.is_starter) return;
      if (typeof slot.points_with_bonus === "number") {
        total += slot.points_with_bonus;
        return;
      }
      if (typeof slot.points_round === "number") {
        total += slot.points_round;
      }
    });
    return Math.round(total * 10) / 10;
  }, [currentRound, lineupSlots]);
  const teamRoundPointsDisplay = teamRoundPoints === null ? "--" : String(Math.round(teamRoundPoints));
  const marketPriceDeltaDisplay =
    marketPriceDelta === null
      ? "--"
      : `${marketPriceDelta > 0 ? "+" : marketPriceDelta < 0 ? "-" : ""}${Math.abs(
          marketPriceDelta
        ).toFixed(1)}`;
  const marketPriceDeltaArrow =
    marketPriceDelta === null
      ? "\u2022"
      : marketPriceDelta > 0
        ? "\u25B2"
        : marketPriceDelta < 0
          ? "\u25BC"
          : "\u2022";
  const marketPriceDeltaToneClass =
    marketPriceDelta === null || marketPriceDelta === 0
      ? "border-white/10 bg-white/5 text-muted"
      : marketPriceDelta > 0
        ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-200"
        : "border-red-400/40 bg-red-500/10 text-red-200";
  const currentLineupSnapshot = useMemo(
    () =>
      buildLineupSnapshot(
        currentRound ?? null,
        lineupSlots,
        captainId ?? null,
        viceCaptainId ?? null
      ),
    [currentRound, lineupSlots, captainId, viceCaptainId]
  );
  const isLineupSaved = useMemo(
    () => lineupSnapshotsEqual(savedLineupSnapshot, currentLineupSnapshot),
    [savedLineupSnapshot, currentLineupSnapshot]
  );
  const canRevertLineup =
    roundStatus === "Pendiente" &&
    !isLineupSaved &&
    Boolean(savedLineupSnapshot) &&
    savedLineupSnapshot?.roundNumber === (currentRound ?? null);
  const hasSavedLineupForCurrentRound = useMemo(() => {
    if (!savedLineupSnapshot) return false;
    if (savedLineupSnapshot.roundNumber !== (currentRound ?? null)) return false;
    return savedLineupSnapshot.slots.some((slot) => slot.player_id !== null);
  }, [savedLineupSnapshot, currentRound]);
  const lineupIndicatorTone: "green" | "yellow" | "red" =
    roundStatus === "Cerrada"
      ? "red"
      : isLineupSaved
        ? "green"
        : "yellow";
  const lineupIndicatorLabel =
    roundStatus === "Cerrada"
      ? hasSavedLineupForCurrentRound
        ? "XI GUARDADO"
        : "SIN XI PARA ESTA RONDA"
      : isLineupSaved
        ? "XI GUARDADO"
        : "XI PENDIENTE";
  const lineupSaveEnabled = roundStatus === "Pendiente";

  const selectedPlayer =
    (selectedSlot?.player_id ? squadMap.get(selectedSlot.player_id) : undefined) ||
    selectedSlot?.player ||
    undefined;
  const selectedOpponent = selectedPlayer
    ? opponentByTeamId.get(selectedPlayer.team_id)
    : undefined;

  const normalizeLineupSlots = (
    slots: LineupSlot[],
    squadById: Map<number, Player>,
    isClosedRound: boolean
  ) =>
    slots.map((slot) => {
      if (!slot.player_id) {
        return { ...slot, player: null };
      }
      const squadPlayer = squadById.get(slot.player_id);
      if (isClosedRound) {
        const resolvedPlayer = squadPlayer || slot.player || null;
        return {
          ...slot,
          role: resolvedPlayer?.position || slot.role,
          player: resolvedPlayer
        };
      }
      if (squadPlayer) {
        return { ...slot, role: squadPlayer.position, player: null };
      }
      return { ...slot, player_id: null, player: null };
    });

  useEffect(() => {
    if (!selectedPlayer) {
      setPlayerMatches([]);
      setPlayerMatchesError(null);
      return;
    }
    setPlayerMatchesLoading(true);
    setPlayerMatchesError(null);
    getPlayerMatches(selectedPlayer.player_id)
      .then((data) => setPlayerMatches(data))
      .catch((err) => {
        setPlayerMatches([]);
        setPlayerMatchesError(String(err));
      })
      .finally(() => setPlayerMatchesLoading(false));
  }, [selectedPlayer?.player_id]);


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
    if (!token) return;

    const load = async () => {
      setLoading(true);
      try {
        const team = await getTeam(token);
        setSquad(
          team.squad || [],
          team.budget_cap,
          team.budget_used,
          team.budget_left
        );
        setMarketPriceDelta(
          typeof team.market_price_delta === "number" ? team.market_price_delta : null
        );
        const savedName = team.name || "";
        setTeamName(savedName);
        const hasName = Boolean(savedName.trim());
        const favoriteId =
          typeof team.favorite_team_id === "number" ? team.favorite_team_id : null;
        setFavoriteTeamId(favoriteId);
        const hasFavorite = Boolean(favoriteId);
        const deferredFavorite = localStorage.getItem(favoriteDeferredKey) === "1";
        if (hasFavorite) {
          localStorage.removeItem(favoriteDeferredKey);
        }
        setNeedsTeamName(!hasName);
        setNeedsFavoriteTeam(!hasFavorite && !deferredFavorite);
        setIsNewTeam(!hasName);
        setTeamLoaded(true);

        try {
          const lineup = await getLineup(token);
          setCurrentRound(lineup.round_number);
          const info = roundsInfo.find((round) => round.round_number === lineup.round_number);
          setRoundStatus(
            info?.status ? info.status : lineup.is_closed ? "Cerrada" : "Pendiente"
          );
          const lineupCaptainId = lineup.captain_player_id ?? null;
          const lineupViceCaptainId = lineup.vice_captain_player_id ?? null;
          const squadById = new Map(
            (team.squad || []).map((player) => [player.player_id, player])
          );
          const normalizedSlots = normalizeLineupSlots(
            lineup.slots || [],
            squadById,
            Boolean(lineup.is_closed)
          );
            const draftKeyForRound = `fantasy_lineup_draft_${(userEmail || "anon").trim() || "anon"}_${lineup.round_number}`;
            const storedDraft = localStorage.getItem(draftKeyForRound);
            if (storedDraft) {
              try {
                const parsed = JSON.parse(storedDraft) as {
                  roundNumber?: number;
                  slots?: LineupSlot[];
                  captainId?: number | null;
                  viceCaptainId?: number | null;
                };
                if (parsed?.roundNumber === lineup.round_number && Array.isArray(parsed.slots)) {
                  setLineupSlots(parsed.slots);
                  if (parsed.captainId) {
                    setCaptainId(parsed.captainId);
                  } else {
                    setCaptainId(lineupCaptainId);
                  }
                  if (parsed.viceCaptainId) {
                    setViceCaptainId(parsed.viceCaptainId);
                  } else {
                    setViceCaptainId(lineupViceCaptainId);
                  }
                } else {
                  setLineupSlots(normalizedSlots);
                  setCaptainId(lineupCaptainId);
                  setViceCaptainId(lineupViceCaptainId);
                }
              } catch {
                setLineupSlots(normalizedSlots);
                setCaptainId(lineupCaptainId);
                setViceCaptainId(lineupViceCaptainId);
              }
            } else {
              setLineupSlots(normalizedSlots);
              setCaptainId(lineupCaptainId);
              setViceCaptainId(lineupViceCaptainId);
            }
          setSavedLineupSnapshot(
            buildLineupSnapshot(
              lineup.round_number ?? null,
              normalizedSlots,
              lineupCaptainId,
              lineupViceCaptainId
            )
          );
          setRoundMissing(false);
          getFixtures()
            .then((allFixtures) => {
              setAllFixtures(allFixtures);
              const roundFixtures = allFixtures.filter(
                (fixture) => fixture.round_number === lineup.round_number
              );
              setFixtures(roundFixtures);
            })
            .catch(() => setFixtures([]));
        } catch (err) {
          const message = String(err);
          if (message.includes("round_not_found")) {
            const allFixtures = await getFixtures().catch(() => []);
            setAllFixtures(allFixtures);
            if (allFixtures.length) {
              const roundNumbers = Array.from(
                new Set(allFixtures.map((fixture) => fixture.round_number))
              ).sort((a, b) => a - b);
              const nextRound = roundNumbers[0] ?? null;
              if (nextRound) {
                setCurrentRound(nextRound);
                setFixtures(allFixtures.filter((fixture) => fixture.round_number === nextRound));
                setRoundMissing(false);
                setRoundStatus(null);
                setMarketPriceDelta(null);
              } else {
                setRoundMissing(true);
                setCurrentRound(null);
                setFixtures([]);
                setRoundStatus(null);
                setMarketPriceDelta(null);
              }
            } else {
              setRoundMissing(true);
              setCurrentRound(null);
              setFixtures([]);
              setRoundStatus(null);
              setMarketPriceDelta(null);
            }
            setLineupSlots(buildDefaultSlots());
            setSavedLineupSnapshot(null);
          } else {
            throw err;
          }
        }
      } finally {
        setLoading(false);
      }
    };

    load().catch(() => {
      setNeedsTeamName(false);
      setNeedsFavoriteTeam(false);
      setIsNewTeam(false);
      setTeamLoaded(true);
      setSavedLineupSnapshot(null);
    });
  }, [token, userEmail, setSquad, setLineupSlots, setCurrentRound, setCaptainId, setViceCaptainId]);

  const handleResetLineup = () => {
    if (roundStatus !== "Pendiente") {
      return;
    }
    const emptySlots = buildDefaultSlots();
    setLineupSlots(emptySlots);
    setCaptainId(null);
    setViceCaptainId(null);
    setSaveErrors([]);
    try {
      if (currentRound) {
        localStorage.setItem(
          draftKey,
          JSON.stringify({
            roundNumber: currentRound,
            slots: emptySlots,
            captainId: null,
            viceCaptainId: null
          })
        );
      } else {
        localStorage.removeItem(draftKey);
      }
    } catch {
      // ignore storage errors
    }
    if (!token || !currentRound) return;
    saveLineup(token, emptySlots, currentRound, null, null, true)
      .then(() => {
        setSaveMessage("XI restablecido");
      })
      .catch((err) => {
        setSaveErrors([String(err)]);
      });
  };

  useEffect(() => {
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  useEffect(() => {
    getRounds().then(setRoundsInfo).catch(() => setRoundsInfo([]));
  }, []);

  useEffect(() => {
    if (!currentRound) return;
    const info = roundsInfo.find((round) => round.round_number === currentRound);
    if (info) {
      setRoundStatus(
        info.status ? info.status : info.is_closed ? "Cerrada" : "Pendiente"
      );
    }
  }, [currentRound, roundsInfo]);

  useEffect(() => {
    getHealth()
      .then((data) => setAppEnv(data.env || "local"))
      .catch(() => setAppEnv("local"));
  }, []);

  useEffect(() => {
    if (!teamLoaded) {
      setNameGateOpen(false);
      setFavoriteGateOpen(false);
      return;
    }
    if (needsFavoriteTeam) {
      setFavoriteGateOpen(true);
      setNameGateOpen(false);
      return;
    }
    const shouldShowWelcome = isNewTeam && needsTeamName && !welcomeSeen;
    if (shouldShowWelcome) {
      setNameGateOpen(false);
      setFavoriteGateOpen(false);
      return;
    }
    if (needsTeamName && welcomeSeen) {
      setNameGateOpen(true);
      setFavoriteGateOpen(false);
      return;
    }
    setNameGateOpen(false);
    setFavoriteGateOpen(false);
  }, [teamLoaded, isNewTeam, needsTeamName, needsFavoriteTeam, welcomeSeen]);

  const welcomeKey = useMemo(() => {
    const safeEmail = userEmail && userEmail.trim() ? userEmail.trim() : "anon";
    return `fantasy_welcome_seen_${safeEmail}`;
  }, [userEmail]);
  const favoriteDeferredKey = useMemo(() => {
    const safeEmail = userEmail && userEmail.trim() ? userEmail.trim() : "anon";
    return `fantasy_favorite_deferred_${safeEmail}`;
  }, [userEmail]);

  useEffect(() => {
    if (!token) return;
    const stored = localStorage.getItem(welcomeKey);
    setWelcomeSeen(stored === "1");
  }, [token, welcomeKey]);

  useEffect(() => {
    if (needsFavoriteTeam) {
      setWelcomeOpen(false);
      return;
    }
    if (isNewTeam && teamLoaded && needsTeamName && !welcomeSeen) {
      setWelcomeOpen(true);
    } else {
      setWelcomeOpen(false);
    }
  }, [teamLoaded, isNewTeam, needsTeamName, needsFavoriteTeam, welcomeSeen]);

  useEffect(() => {
    if (!token || roundMissing || !currentRound) return;
    const sanitizedSlots = sanitizeLineupSlots(lineupSlots);
    const payload = {
      roundNumber: currentRound,
      slots: sanitizedSlots,
      captainId,
      viceCaptainId
    };
    safeSaveDraft(draftKey, payload);
  }, [token, roundMissing, currentRound, lineupSlots, captainId, viceCaptainId, draftKey]);

  useEffect(() => {
    if (!loading && squad.length > 0 && lineupSlots.length === 0) {
      setLineupSlots(buildDefaultSlots());
    }
  }, [loading, squad.length, lineupSlots.length, setLineupSlots]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  const handleDragStart = (event: any) => {
    const playerId = event.active.data.current?.playerId as number | undefined;
    setActivePlayerId(playerId || null);
  };

  const resolveRoleForPlayer = (playerId: number | null | undefined) => {
    if (!playerId) return null;
    const player = squadMap.get(playerId);
    return player ? player.position : null;
  };

  const applyPlayerToSlot = (slot: LineupSlot, playerId: number | null) => {
    if (!playerId) {
      return { ...slot, player_id: null, player: null };
    }
    const role = resolveRoleForPlayer(playerId);
    return role
      ? { ...slot, player_id: playerId, role, player: null }
      : { ...slot, player_id: playerId, player: null };
  };

  const handleDragEnd = (event: any) => {
    setActivePlayerId(null);
    const { active, over } = event;
    if (!over) return;

    const playerId = active.data.current?.playerId as number | undefined;
    const fromIndex = active.data.current?.slotIndex as number | undefined;
    const toIndex = over.data.current?.slotIndex as number | undefined;
    if (playerId === undefined || toIndex === undefined) {
      return;
    }

    if (fromIndex === undefined || fromIndex < 0) {
      setLineupSlots((prevSlots) =>
        prevSlots.map((slot) => {
          if (slot.player_id === playerId) {
            return applyPlayerToSlot(slot, null);
          }
          if (slot.slot_index === toIndex) {
            return applyPlayerToSlot(slot, playerId);
          }
          return slot;
        })
      );
      return;
    }

    if (fromIndex === toIndex) {
      return;
    }

    setLineupSlots((prevSlots) =>
      prevSlots.map((slot) => {
        if (slot.slot_index === fromIndex) {
          const toSlot = prevSlots.find((s) => s.slot_index === toIndex);
          return applyPlayerToSlot(slot, toSlot?.player_id ?? null);
        }
        if (slot.slot_index === toIndex) {
          const fromSlot = prevSlots.find((s) => s.slot_index === fromIndex);
          return applyPlayerToSlot(slot, fromSlot?.player_id ?? null);
        }
        return slot;
      })
    );
  };

  const activePlayer = activePlayerId ? squadMap.get(activePlayerId) : undefined;

  const handleSlotClick = (slot: LineupSlot) => {
    setSelectedSlot(slot);
    if (slot.is_starter) {
      setStarterPickerOpen(true);
      setSheetOpen(false);
    } else {
      setSheetOpen(true);
      setStarterPickerOpen(false);
    }
  };

  const closeSelection = () => {
    setSelectedSlot(null);
    setSheetOpen(false);
    setStarterPickerOpen(false);
  };

  const handleRemovePlayer = () => {
    if (!selectedSlot) return;
    setLineupSlots(
      lineupSlots.map((slot) =>
        slot.slot_index === selectedSlot.slot_index ? applyPlayerToSlot(slot, null) : slot
      )
    );
    setSelectedSlot(applyPlayerToSlot(selectedSlot, null));
    if (sheetOpen) {
      setSheetOpen(false);
    }
    if (starterPickerOpen) {
      setStarterPickerOpen(false);
    }
  };

  const handleCaptain = () => {
    if (!selectedSlot?.player_id) return;
    if (!selectedSlot.is_starter) {
      setSaveErrors(["captain_not_in_starting_xi"]);
      return;
    }
    setCaptainId(selectedSlot.player_id);
    if (viceCaptainId === selectedSlot.player_id) {
      setViceCaptainId(null);
    }
    if (sheetOpen) {
      setSheetOpen(false);
    }
    if (starterPickerOpen) {
      setStarterPickerOpen(false);
    }
  };

  const handleViceCaptain = () => {
    if (!selectedSlot?.player_id) return;
    if (!selectedSlot.is_starter) {
      setSaveErrors(["vice_captain_not_in_starting_xi"]);
      return;
    }
    setViceCaptainId(selectedSlot.player_id);
    if (captainId === selectedSlot.player_id) {
      setCaptainId(null);
    }
    if (sheetOpen) {
      setSheetOpen(false);
    }
    if (starterPickerOpen) {
      setStarterPickerOpen(false);
    }
  };

  const handleAssignPlayer = (playerId: number, sourceSlotIndex?: number) => {
    if (!selectedSlot) return;
    const targetIndex = selectedSlot.slot_index;
    setLineupSlots((prevSlots) => {
      const targetSlot = prevSlots.find((slot) => slot.slot_index === targetIndex);
      const outgoingId = targetSlot?.player_id ?? null;
      return prevSlots.map((slot) => {
        if (slot.slot_index === targetIndex) {
          return applyPlayerToSlot(slot, playerId);
        }
        if (sourceSlotIndex !== undefined && slot.slot_index === sourceSlotIndex) {
          return applyPlayerToSlot(slot, outgoingId);
        }
        if (sourceSlotIndex === undefined && slot.player_id === playerId) {
          return applyPlayerToSlot(slot, null);
        }
        return slot;
      });
    });
    setSelectedSlot((prev) => (prev ? applyPlayerToSlot(prev, playerId) : prev));
    if (sheetOpen) {
      setSheetOpen(false);
    }
    if (starterPickerOpen) {
      setStarterPickerOpen(false);
    }
  };

  const handleRevertLineupChanges = () => {
    if (!canRevertLineup || !savedLineupSnapshot) return;
    const revertedSlots: LineupSlot[] = savedLineupSnapshot.slots.map((slot) => ({
      ...slot,
      player: null
    }));
    setLineupSlots(revertedSlots);
    setCaptainId(savedLineupSnapshot.captainId ?? null);
    setViceCaptainId(savedLineupSnapshot.viceCaptainId ?? null);
    setSaveErrors(null);
    setSaveMessage("Cambios descartados");
    if (savedLineupSnapshot.roundNumber) {
      safeSaveDraft(draftKey, {
        roundNumber: savedLineupSnapshot.roundNumber,
        slots: revertedSlots,
        captainId: savedLineupSnapshot.captainId ?? null,
        viceCaptainId: savedLineupSnapshot.viceCaptainId ?? null
      });
    }
  };

  const handleSave = async () => {
    if (nameGateOpen) return;
    if (roundMissing) {
      setSaveErrors(["rounds_not_configured"]);
      return;
    }
    if (roundStatus === "Cerrada") {
      setSaveErrors(["round_closed"]);
      return;
    }
    if (!token) return;
    setSaveErrors(null);
    setSaveMessage(null);
    const localErrors = [...new Set(validateLineup(lineupSlots, squad))];
    if (localErrors.length > 0) {
      setSaveErrors(localErrors);
      return;
    }
    try {
      const result = await saveLineup(
        token,
        lineupSlots,
        currentRound || undefined,
        captainId,
        viceCaptainId
      );
      if (result?.message) {
        setSaveMessage(result.message);
      } else {
        setSaveMessage("XI guardado correctamente");
      }
      setSavedLineupSnapshot(
        buildLineupSnapshot(
          currentRound ?? null,
          lineupSlots,
          captainId ?? null,
          viceCaptainId ?? null
        )
      );
    } catch (err) {
      setSaveErrors([String(err)]);
    }
  };

  const handleRoundSelect = async (roundNumber: number) => {
    if (!token || roundNumber === currentRound) return;
    if (!availableRounds.includes(roundNumber)) return;
    setLoading(true);
    setSaveErrors(null);
    try {
      const [team, lineup] = await Promise.all([
        getTeam(token, roundNumber),
        getLineup(token, roundNumber)
      ]);
      setSquad(
        team.squad || [],
        team.budget_cap,
        team.budget_used,
        team.budget_left
      );
      setMarketPriceDelta(
        typeof team.market_price_delta === "number" ? team.market_price_delta : null
      );
      const resolvedRoundNumber =
        typeof lineup.round_number === "number" && lineup.round_number > 0
          ? lineup.round_number
          : roundNumber;
      setCurrentRound(resolvedRoundNumber);
      const lineupCaptainId = lineup.captain_player_id ?? null;
      const lineupViceCaptainId = lineup.vice_captain_player_id ?? null;
      const squadById = new Map(
        (team.squad || []).map((player) => [player.player_id, player])
      );
      const normalizedSlots = normalizeLineupSlots(
        lineup.slots || [],
        squadById,
        Boolean(lineup.is_closed)
      );
      setLineupSlots(normalizedSlots);
      setCaptainId(lineupCaptainId);
      setViceCaptainId(lineupViceCaptainId);
      setSavedLineupSnapshot(
        buildLineupSnapshot(
          resolvedRoundNumber,
          normalizedSlots,
          lineupCaptainId,
          lineupViceCaptainId
        )
      );
      setRoundMissing(false);
      const info = roundsInfo.find((round) => round.round_number === resolvedRoundNumber);
      setRoundStatus(
        info?.status ? info.status : lineup.is_closed ? "Cerrada" : "Pendiente"
      );
      setFixtures(allFixtures.filter((fixture) => fixture.round_number === resolvedRoundNumber));
    } catch (err) {
      setSaveErrors([String(err)]);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return <AuthPanel />;
  }

  if (loading && lineupSlots.length === 0) {
    return <p className="text-sm text-muted">Cargando...</p>;
  }

  const starters = lineupSlots
    .filter((slot) => slot.is_starter)
    .sort((a, b) => a.slot_index - b.slot_index);
  const bench = lineupSlots
    .filter((slot) => !slot.is_starter)
    .sort((a, b) => a.slot_index - b.slot_index);

  const startersByRole = {
    F: starters.filter((slot) => slot.role === "F"),
    M: starters.filter((slot) => slot.role === "M"),
    D: starters.filter((slot) => slot.role === "D"),
    G: starters.filter((slot) => slot.role === "G")
  };

  const benchCandidates = bench
    .filter((slot) => slot.player_id)
    .map((slot) => {
      const player =
        (slot.player_id ? squadMap.get(slot.player_id) : undefined) || slot.player;
      return player ? { slot, player } : null;
    })
    .filter((item): item is { slot: LineupSlot; player: Player } => item !== null);

  const isTestEnv = appEnv === "test";
  const sizeClass = isTestEnv ? "h-9 w-9" : "h-12 w-12";
  const badgeClass = "h-[25%] w-[25%]";
  const canPrevRound = roundIndex > 0;
  const canNextRound = roundIndex >= 0 && roundIndex < availableRounds.length - 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Fantasy Liga 1 2026</h1>
          <p className="text-xs text-muted">
            Ronda actual : {currentRound ?? "-"}
            {roundDateRange ? ` (Del ${roundDateRange.min} al ${roundDateRange.max})` : ""}
            {roundStatus ? ` - ${roundStatus}` : ""}
          </p>
        </div>
      </div>
      {roundStatus === "Pendiente" && nextFixture ? (
        <div className="flex items-center justify-between rounded-2xl border border-accent/40 bg-accent/10 px-3 py-2 text-xs">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-[0.15em] text-muted">Haz tu XI inicial</span>
            <span className="text-sm font-semibold text-ink">
              Próximo partido:{" "}
              {(() => {
                const raw = nextFixture.kickoff_at ? String(nextFixture.kickoff_at).trim() : "";
                if (!raw) return `Ronda ${currentRound ?? ""}`;
                const normalized = raw.replace("T", " ").trim();
                const [datePart, timePart] = normalized.split(" ");
                const [year, month, day] = (datePart || "").split("-");
                const time = timePart ? timePart.slice(0, 5) : "";
                if (!year || !month || !day) return normalized;
                return `${day}/${month}/${year.slice(2)}${time ? `, ${time}` : ""}`;
              })()}
            </span>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full bg-accent px-3 py-1 text-[10px] font-semibold text-black">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-black/10">
              {nextFixture.home_team_id ? (
                <img
                  src={`/images/teams/${nextFixture.home_team_id}.png`}
                  alt=""
                  className="h-4 w-4 object-contain"
                  onError={(event) => {
                    (event.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                />
              ) : (
                <span className="text-[9px]">-</span>
              )}
            </span>
            <span>vs</span>
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-black/10">
              {nextFixture.away_team_id ? (
                <img
                  src={`/images/teams/${nextFixture.away_team_id}.png`}
                  alt=""
                  className="h-4 w-4 object-contain"
                  onError={(event) => {
                    (event.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                />
              ) : (
                <span className="text-[9px]">-</span>
              )}
            </span>
          </span>
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs">
          <button
            type="button"
            onClick={() => {
              if (canPrevRound && roundIndex > 0) {
                handleRoundSelect(availableRounds[roundIndex - 1]);
              }
            }}
            disabled={!canPrevRound}
            className="rounded-lg border border-white/10 px-2 py-1 text-ink disabled:opacity-40"
          >
            {"<"}
          </button>
          <span className="text-muted">Ronda {currentRound ?? "-"}</span>
          <button
            type="button"
            onClick={() => {
              if (canNextRound && roundIndex >= 0) {
                handleRoundSelect(availableRounds[roundIndex + 1]);
              }
            }}
            disabled={!canNextRound}
            className="rounded-lg border border-white/10 px-2 py-1 text-ink disabled:opacity-40"
          >
            {">"}
          </button>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-muted">
          Puntos equipo:{" "}
          <span className="font-semibold text-ink">
            {teamRoundPointsDisplay}
          </span>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-muted">
          <button
            type="button"
            onClick={() => setDeltaOpen(true)}
            className="inline-flex items-center gap-2 font-semibold text-ink"
            aria-label="Ver detalle delta"
          >
            {"\u25B3"} precio:
          </button>
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-semibold ${marketPriceDeltaToneClass}`}
          >
            <span>{marketPriceDeltaArrow}</span>
            <span>{marketPriceDeltaDisplay}</span>
          </span>
        </div>
      </div>
      {roundMissing ? (
        <div className="glass rounded-2xl border border-white/10 p-4 text-sm text-muted">
          No hay rondas configuradas. Carga rondas y partidos desde Admin para habilitar el XI.
        </div>
      ) : null}
      <StickyTopBar budgetUsed={budgetUsed} budgetLeft={budgetLeft} />

      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Titulares</h2>
          <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-emerald-700/55 via-emerald-900/45 to-black/35 p-4">
            <div className="pointer-events-none absolute inset-4 rounded-2xl border border-white/10" />
            <div className="pointer-events-none absolute left-4 right-4 top-1/2 h-px bg-white/10" />
            <div className="pointer-events-none absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10" />
            <div className="relative z-10 flex min-h-[520px] flex-col justify-between gap-6 py-3">
            <PitchRow
              label="Ataque"
              slots={startersByRole.F}
              squadMap={squadMap}
              opponentByTeamId={opponentByTeamId}
              onSelect={handleSlotClick}
              sizeClass={sizeClass}
              badgeClass={badgeClass}
              captainId={captainId}
              viceCaptainId={viceCaptainId}
              showPoints={roundStatus === "Cerrada"}
            />
            <PitchRow
              label="Medio"
              slots={startersByRole.M}
              squadMap={squadMap}
              opponentByTeamId={opponentByTeamId}
              onSelect={handleSlotClick}
              sizeClass={sizeClass}
              badgeClass={badgeClass}
              captainId={captainId}
              viceCaptainId={viceCaptainId}
              showPoints={roundStatus === "Cerrada"}
            />
            <PitchRow
              label="Defensa"
              slots={startersByRole.D}
              squadMap={squadMap}
              opponentByTeamId={opponentByTeamId}
              onSelect={handleSlotClick}
              sizeClass={sizeClass}
              badgeClass={badgeClass}
              captainId={captainId}
              viceCaptainId={viceCaptainId}
              showPoints={roundStatus === "Cerrada"}
            />
            <PitchRow
              label="Arquero"
              slots={startersByRole.G}
              squadMap={squadMap}
              opponentByTeamId={opponentByTeamId}
              onSelect={handleSlotClick}
              sizeClass={sizeClass}
              badgeClass={badgeClass}
              captainId={captainId}
              viceCaptainId={viceCaptainId}
              showPoints={roundStatus === "Cerrada"}
            />
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Suplentes</h2>
          <div className="grid grid-cols-4 gap-2">
            {bench.map((slot) => {
              const player =
                (slot.player_id ? squadMap.get(slot.player_id) : undefined) ||
                (slot.player ?? undefined);
              return (
                <LineupSlotCard
                  key={slot.slot_index}
                  slot={slot}
                  player={player}
                  isCaptain={Boolean(player && captainId === player.player_id)}
                  isViceCaptain={Boolean(player && viceCaptainId === player.player_id)}
                  opponent={player ? opponentByTeamId.get(player.team_id) : undefined}
                  onClick={() => handleSlotClick(slot)}
                  compact
                />
              );
            })}
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Plantel</h2>
            <p className="text-xs text-muted">{availablePlayers.length} disponibles</p>
          </div>
          {squad.length === 0 ? (
            <p className="text-sm text-muted">Guarda tu equipo desde Mercado para cargar jugadores.</p>
          ) : availablePlayers.length === 0 ? (
            <p className="text-sm text-muted">Todos los jugadores estan asignados a XI o banca.</p>
          ) : (
            <div className="grid grid-cols-5 gap-2">
              {sortedAvailablePlayers.map((player) => (
                <DraggablePlayer
                  key={player.player_id}
                  player={player}
                  slotIndex={-1}
                  variant="square"
                  className="w-full"
                />
              ))}
            </div>
          )}
        </section>

        <DragOverlay>
          {activePlayer ? (
            <div className="rounded-2xl bg-black/40 p-2 shadow-xl">
              <PlayerAvatarSquare
                playerId={activePlayer.player_id}
                teamId={activePlayer.team_id}
                className={isTestEnv ? "h-12 w-12" : "h-14 w-14"}
                rounded
              />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      <div className="glass rounded-2xl p-4">
        <p className="text-xs text-muted">Capitan</p>
        <p className="text-sm text-ink">
          {captainId && squadMap.get(captainId) ? squadMap.get(captainId)?.name : "No asignado"}
        </p>
        <p className="mt-2 text-xs text-muted">Vicecapitan</p>
        <p className="text-sm text-ink">
          {viceCaptainId && squadMap.get(viceCaptainId)
            ? squadMap.get(viceCaptainId)?.name
            : "No asignado"}
        </p>
        <p className="mt-3 text-[11px] text-muted">
          El capitan triplica su puntaje; si no juega, el vicecapitan recibe el bonus.
        </p>
        {roundStatus === "Pendiente" ? (
          <div className="mt-4">
            <button
              onClick={() => setResetConfirmOpen(true)}
              className="w-full rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white"
            >
              Restablecer XI titular
            </button>
          </div>
        ) : null}
      </div>

      {resetConfirmOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm rounded-2xl border border-white/10 p-4">
            <p className="text-sm font-semibold text-ink">{"\u00BFEst\u00E1s seguro?"}</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <button
                onClick={() => {
                  handleResetLineup();
                  setResetConfirmOpen(false);
                }}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white"
              >
                Si
              </button>
              <button
                onClick={() => setResetConfirmOpen(false)}
                className="rounded-xl bg-white/10 px-4 py-2 text-sm font-semibold text-ink"
              >
                No
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <BottomSheet
        open={deltaOpen}
        onClose={() => setDeltaOpen(false)}
        title="Detalle de delta de precio"
      >
        <div className="max-h-[70vh] space-y-3 overflow-auto pr-1 text-xs text-muted">
          {squad.length === 0 ? (
            <p>Sin jugadores para mostrar.</p>
          ) : (
            squad
              .slice(0, 15)
              .sort((a, b) => (a.position || "").localeCompare(b.position || "") || a.player_id - b.player_id)
              .map((player) => (
                <div
                  key={player.player_id}
                  className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <PlayerFace playerId={player.player_id} sizeClass="h-9 w-9" />
                    <div>
                      <p className="text-sm font-semibold text-ink">
                        {player.short_name || player.shortName || player.name}
                      </p>
                      <p className="text-[10px] uppercase text-muted">{player.position}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] text-muted">Δ</p>
                    <p
                      className={
                        "text-sm font-semibold " +
                        (typeof player.price_delta === "number"
                          ? player.price_delta > 0
                            ? "text-emerald-200"
                            : player.price_delta < 0
                              ? "text-red-200"
                              : "text-ink"
                          : "text-muted")
                      }
                    >
                      {typeof player.price_delta === "number"
                        ? `${player.price_delta > 0 ? "+" : player.price_delta < 0 ? "-" : ""}${Math.abs(
                            player.price_delta
                          ).toFixed(1)}`
                        : "--"}
                    </p>
                  </div>
                </div>
              ))
          )}
        </div>
      </BottomSheet>

      <FabMenu
        onSave={handleSave}
        onRevert={handleRevertLineupChanges}
        isLineupSaved={isLineupSaved}
        canRevert={canRevertLineup}
        indicatorLabel={lineupIndicatorLabel}
        indicatorTone={lineupIndicatorTone}
        saveEnabled={lineupSaveEnabled}
      />

      {saveMessage ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Listo</p>
              <button
                onClick={() => setSaveMessage(null)}
                className="text-xs text-muted"
                aria-label="Cerrar"
              >
                X
              </button>
            </div>
            <div className="mt-3 rounded-xl border border-emerald-400/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
              {saveMessage}
            </div>
            <button
              onClick={() => setSaveMessage(null)}
              className="mt-4 w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
            >
              Entendido
            </button>
          </div>
        </div>
      ) : null}

      <WelcomeSlideshow
        open={welcomeOpen}
        onComplete={() => {
          localStorage.setItem(welcomeKey, "1");
          setWelcomeSeen(true);
          setWelcomeOpen(false);
          setPostWelcomeRedirect(true);
          if (needsTeamName) {
            setNameGateOpen(true);
          }
        }}
      />

      <FavoriteTeamGate
        open={favoriteGateOpen}
        selectedTeamId={favoriteTeamId}
        onSelect={(teamId) => setFavoriteTeamId(teamId)}
        error={favoriteError}
        onClose={() => {
          if (!needsFavoriteTeam) {
            setFavoriteGateOpen(false);
          }
        }}
        onSkip={() => {
          localStorage.setItem(favoriteDeferredKey, "1");
          setFavoriteTeamId(null);
          setNeedsFavoriteTeam(false);
          setFavoriteGateOpen(false);
        }}
        onSave={async () => {
          if (!token || !favoriteTeamId) return;
          setFavoriteError(null);
          try {
            await updateFavoriteTeam(token, favoriteTeamId);
            localStorage.removeItem(favoriteDeferredKey);
            setNeedsFavoriteTeam(false);
            setFavoriteGateOpen(false);
            if (postWelcomeRedirect) {
              setPostWelcomeRedirect(false);
              router.push("/market");
            }
          } catch {
            setFavoriteError("No se pudo guardar el equipo favorito.");
          }
        }}
      />

      <TeamNameGate
        open={nameGateOpen}
        teamName={teamName}
        onTeamNameChange={setTeamName}
        error={teamNameError}
        onClose={() => {
          setNameGateOpen(false);
        }}
        onSave={async () => {
          if (!token) return;
          const trimmedName = teamName.trim();
          if (!trimmedName) {
            setTeamNameError("Nombre requerido.");
            return;
          }
          setTeamNameError(null);
          try {
            await createTeam(token, trimmedName);
            setTeamName(trimmedName);
            setNeedsTeamName(false);
            setIsNewTeam(false);
            setNameGateOpen(false);
            if (postWelcomeRedirect) {
              setPostWelcomeRedirect(false);
              router.push("/market");
            }
          } catch {
            setTeamNameError("No se pudo guardar el nombre.");
          }
        }}
      />

      {saveErrors ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-sm rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Alertas</p>
              <button
                onClick={() => setSaveErrors(null)}
                className="text-xs text-muted"
                aria-label="Cerrar"
              >
                X
              </button>
            </div>
            <div className="mt-3 space-y-2 text-xs">
              {saveErrors.map((error) => {
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
              onClick={() => setSaveErrors(null)}
              className="mt-4 w-full rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
            >
              Entendido
            </button>
          </div>
        </div>
      ) : null}

      {starterPickerOpen && selectedSlot && selectedSlot.is_starter ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-4">
          <div className="glass w-full max-w-md rounded-2xl border border-white/10 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Seleccion de titular</p>
              <button onClick={closeSelection} className="text-xs text-muted" aria-label="Cerrar">
                X
              </button>
            </div>
            <div className="mt-3 max-h-[60vh] space-y-3 overflow-y-auto pr-1">
              {selectedPlayer ? (
                <div className="space-y-2">
                  <PlayerCard player={selectedPlayer} compact />
                  <PlayerFantasyDetails
                    player={selectedPlayer}
                    teamName={teamNameById.get(selectedPlayer.team_id)}
                    matches={playerMatches}
                    loadingMatches={playerMatchesLoading}
                  />
                  {playerMatchesError ? (
                    <p className="text-[11px] text-warning">{playerMatchesError}</p>
                  ) : null}
                </div>
              ) : (
                <p className="text-xs text-muted">Slot vacio.</p>
              )}

              {selectedSlot.player_id ? (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <p className="text-[10px] uppercase text-muted">Reemplazar con banca</p>
                    {benchCandidates.length ? (
                      benchCandidates.map(({ slot, player }) => (
                        <button
                          key={slot.slot_index}
                          onClick={() => handleAssignPlayer(player.player_id, slot.slot_index)}
                          className="w-full text-left"
                        >
                          <PlayerCard player={player} compact />
                        </button>
                      ))
                    ) : (
                      <p className="text-xs text-muted">Sin jugadores en banca.</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <p className="text-[10px] uppercase text-muted">Reemplazar con plantel</p>
                    {availablePlayersSorted.length ? (
                      availablePlayersSorted.map((player) => (
                        <button
                          key={player.player_id}
                          onClick={() => handleAssignPlayer(player.player_id)}
                          className="w-full text-left"
                        >
                          <PlayerCard player={player} compact />
                        </button>
                      ))
                    ) : (
                      <p className="text-xs text-muted">Sin jugadores disponibles.</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <p className="text-[10px] uppercase text-muted">Agregar jugador disponible</p>
                    {availablePlayersSorted.length ? (
                      availablePlayersSorted.map((player) => (
                        <button
                          key={player.player_id}
                          onClick={() => handleAssignPlayer(player.player_id)}
                          className="w-full text-left"
                        >
                          <PlayerCard player={player} compact />
                        </button>
                      ))
                    ) : (
                      <p className="text-xs text-muted">Sin jugadores disponibles.</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <p className="text-[10px] uppercase text-muted">Agregar desde banca</p>
                    {benchCandidates.length ? (
                      benchCandidates.map(({ slot, player }) => (
                        <button
                          key={slot.slot_index}
                          onClick={() => handleAssignPlayer(player.player_id, slot.slot_index)}
                          className="w-full text-left"
                        >
                          <PlayerCard player={player} compact />
                        </button>
                      ))
                    ) : (
                      <p className="text-xs text-muted">Sin jugadores en banca.</p>
                    )}
                  </div>
                </div>
              )}
            </div>
            {selectedSlot.player_id ? (
              <div className="mt-4 flex gap-2">
                <button
                  onClick={handleRemovePlayer}
                  className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-xs text-ink"
                >
                  Quitar
                </button>
                <button
                  onClick={handleCaptain}
                  className="flex-1 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-black"
                >
                  Fijar Capitan
                </button>
                <button
                  onClick={handleViceCaptain}
                  className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-xs text-ink"
                >
                  Fijar Vice
                </button>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      <BottomSheet
        open={sheetOpen}
        onClose={closeSelection}
        title={selectedPlayer ? selectedPlayer.name : "Slot"}
      >
        {selectedSlot ? (
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-ink">
                {selectedSlot.is_starter ? "Seleccion de titular" : "Seleccion de suplente"}
              </p>
              <button onClick={closeSelection} className="text-xs text-muted" aria-label="Cerrar">
                X
              </button>
            </div>
            {selectedPlayer ? (
              <div className="space-y-2">
                <PlayerCard player={selectedPlayer} />
                <PlayerFantasyDetails
                  player={selectedPlayer}
                  teamName={teamNameById.get(selectedPlayer.team_id)}
                  matches={playerMatches}
                  loadingMatches={playerMatchesLoading}
                />
                {playerMatchesError ? (
                  <p className="text-[11px] text-warning">{playerMatchesError}</p>
                ) : null}
                {selectedSlot.is_starter && selectedOpponent ? (
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <span>Rival:</span>
                    <span className="flex h-[14px] w-[14px] items-center justify-center">
                      <img
                        src={`/images/teams/${selectedOpponent.teamId}.png`}
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
            ) : (
              <p className="text-sm text-muted">Slot vacio</p>
            )}

            {selectedSlot.is_starter ? (
              selectedSlot.player_id ? (
                <div className="space-y-2">
                <p className="text-xs uppercase text-muted">Reemplazar con banca</p>
                  {benchCandidates.length ? (
                    benchCandidates.map(({ slot, player }) => (
                      <button
                        key={slot.slot_index}
                        onClick={() => handleAssignPlayer(player.player_id, slot.slot_index)}
                        className="w-full text-left"
                      >
                        <PlayerCard player={player} compact />
                      </button>
                    ))
                  ) : (
                    <p className="text-xs text-muted">Sin jugadores en banca.</p>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <p className="text-xs uppercase text-muted">Agregar jugador disponible</p>
                    {availablePlayersSorted.length ? (
                      availablePlayersSorted.map((player) => (
                        <button
                          key={player.player_id}
                          onClick={() => handleAssignPlayer(player.player_id)}
                          className="w-full text-left"
                        >
                          <PlayerCard player={player} compact />
                        </button>
                      ))
                    ) : (
                      <p className="text-xs text-muted">Sin jugadores disponibles.</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs uppercase text-muted">Agregar desde banca</p>
                    {benchCandidates.length ? (
                      benchCandidates.map(({ slot, player }) => (
                        <button
                          key={slot.slot_index}
                          onClick={() => handleAssignPlayer(player.player_id, slot.slot_index)}
                          className="w-full text-left"
                        >
                          <PlayerCard player={player} compact />
                        </button>
                      ))
                    ) : (
                      <p className="text-xs text-muted">Sin jugadores en banca.</p>
                    )}
                  </div>
                </div>
              )
            ) : selectedSlot.player_id ? (
              <div className="space-y-2">
                <p className="text-xs uppercase text-muted">Reemplazar con plantel</p>
                {availablePlayersSorted.length ? (
                  availablePlayersSorted.map((player) => (
                    <button
                      key={player.player_id}
                      onClick={() => handleAssignPlayer(player.player_id)}
                      className="w-full text-left"
                    >
                      <PlayerCard player={player} compact />
                    </button>
                  ))
                ) : (
                  <p className="text-xs text-muted">Sin jugadores disponibles.</p>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-xs uppercase text-muted">Agregar jugador disponible</p>
                {availablePlayersSorted.length ? (
                  availablePlayersSorted.map((player) => (
                    <button
                      key={player.player_id}
                      onClick={() => handleAssignPlayer(player.player_id)}
                      className="w-full text-left"
                    >
                      <PlayerCard player={player} compact />
                    </button>
                  ))
                ) : (
                  <p className="text-xs text-muted">Sin jugadores disponibles.</p>
                )}
              </div>
            )}

            {selectedSlot.player_id ? (
              <div className="flex gap-2">
                <button
                  onClick={handleRemovePlayer}
                  className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
                >
                  Quitar
                </button>
                <button
                  onClick={handleCaptain}
                  className="flex-1 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
                >
                  Fijar Capitan
                </button>
                <button
                  onClick={handleViceCaptain}
                  className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
                >
                  Fijar Vice
                </button>
              </div>
            ) : null}
            <button
              onClick={closeSelection}
              className="w-full rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
            >
              Retornar
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted">Selecciona un slot</p>
            <button
              onClick={closeSelection}
              className="w-full rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
            >
              Retornar
            </button>
          </div>
        )}
      </BottomSheet>
    </div>
  );
}


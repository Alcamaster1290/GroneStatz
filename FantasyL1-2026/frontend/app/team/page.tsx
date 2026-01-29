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

import AuthPanel from "@/components/AuthPanel";
import BottomSheet from "@/components/BottomSheet";
import DraggablePlayer from "@/components/DraggablePlayer";
import FabMenu from "@/components/FabMenu";
import LineupSlotCard from "@/components/LineupSlotCard";
import PlayerCard from "@/components/PlayerCard";
import PlayerAvatarSquare from "@/components/PlayerAvatarSquare";
import StickyTopBar from "@/components/StickyTopBar";
import TeamNameGate from "@/components/TeamNameGate";
import WelcomeSlideshow from "@/components/WelcomeSlideshow";
import { createTeam, getFixtures, getHealth, getLineup, getTeam, getTeams, saveLineup } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";
import { Fixture, LineupSlot, Player } from "@/lib/types";
import { validateLineup, validateSquad } from "@/lib/validation";

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
  roundNumber,
  teamName,
  fixtures
}: {
  player: Player;
  roundNumber: number | null;
  teamName?: string;
  fixtures: Fixture[];
}) {
  const displayName = player.short_name || player.shortName || player.name;
  const isKeeper = player.position === "G";
  const points =
    typeof player.points_round === "number" ? player.points_round.toFixed(1) : "--";
  const primaryStatLabel = isKeeper ? "Atajadas" : "Goles";
  const primaryStatValue = isKeeper ? player.saves ?? 0 : player.goals ?? 0;
  const secondaryStatLabel = isKeeper ? "Goles recibidos" : "Asistencias";
  const secondaryStatValue = isKeeper
    ? player.goals_conceded ?? 0
    : player.assists ?? 0;
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
          <p className="text-[10px] uppercase text-muted">
            Puntaje ronda {roundNumber ?? "-"}
          </p>
          <p className="text-sm font-semibold text-ink">
            {roundNumber ? `${points}` : "--"}
          </p>
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

function PitchSlot({
  slot,
  player,
  opponent,
  onClick,
  sizeClass,
  badgeClass,
  isCaptain,
  isViceCaptain
}: {
  slot: LineupSlot;
  player?: Player;
  opponent?: { teamId: number; name?: string };
  onClick?: () => void;
  sizeClass: string;
  badgeClass: string;
  isCaptain: boolean;
  isViceCaptain: boolean;
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
  viceCaptainId
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
}) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">{label}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {slots.map((slot) => {
            const player = slot.player_id ? squadMap.get(slot.player_id) : undefined;
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
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>(
    []
  );
  const [roundStatus, setRoundStatus] = useState<string | null>(null);
  const [appEnv, setAppEnv] = useState<string>("local");
  const [roundMissing, setRoundMissing] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [needsTeamName, setNeedsTeamName] = useState(false);
  const [teamLoaded, setTeamLoaded] = useState(false);
  const [nameGateOpen, setNameGateOpen] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [welcomeSeen, setWelcomeSeen] = useState(false);
  const [teamNameError, setTeamNameError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

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
        setSquad(team.squad || []);
        const savedName = team.name || "";
        setTeamName(savedName);
        setNeedsTeamName(!savedName.trim());
        setTeamLoaded(true);

        try {
          const lineup = await getLineup(token);
          setCurrentRound(lineup.round_number);
          const lineupCaptainId = lineup.captain_player_id ?? null;
          const lineupViceCaptainId = lineup.vice_captain_player_id ?? null;
          const squadById = new Map(
            (team.squad || []).map((player) => [player.player_id, player])
          );
          const normalizedSlots = (lineup.slots || []).map((slot) => {
            if (slot.player_id) {
              const player = squadById.get(slot.player_id);
              if (player) {
                return { ...slot, role: player.position };
              }
            }
            return slot;
          });
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
          setRoundMissing(false);
          setRoundStatus("Pendiente");
          getFixtures()
            .then((allFixtures) => {
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
            if (allFixtures.length) {
              const roundNumbers = Array.from(
                new Set(allFixtures.map((fixture) => fixture.round_number))
              ).sort((a, b) => a - b);
              const nextRound = roundNumbers[0] ?? null;
              if (nextRound) {
                setCurrentRound(nextRound);
                setFixtures(allFixtures.filter((fixture) => fixture.round_number === nextRound));
                setRoundMissing(false);
                setRoundStatus("Cerrada");
              } else {
                setRoundMissing(true);
                setCurrentRound(null);
                setFixtures([]);
                setRoundStatus(null);
              }
            } else {
              setRoundMissing(true);
              setCurrentRound(null);
              setFixtures([]);
              setRoundStatus(null);
            }
            setLineupSlots(buildDefaultSlots());
          } else {
            throw err;
          }
        }
      } finally {
        setLoading(false);
      }
    };

    load().catch(() => {
      setTeamLoaded(true);
    });
    }, [token, userEmail, setSquad, setLineupSlots, setCurrentRound, setCaptainId, setViceCaptainId]);

  useEffect(() => {
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  useEffect(() => {
    getHealth()
      .then((data) => setAppEnv(data.env || "local"))
      .catch(() => setAppEnv("local"));
  }, []);

  useEffect(() => {
    if (teamLoaded && needsTeamName) {
      setNameGateOpen(!welcomeOpen);
    } else {
      setNameGateOpen(false);
    }
  }, [teamLoaded, needsTeamName, welcomeOpen]);

  const welcomeKey = useMemo(() => {
    const safeEmail = userEmail && userEmail.trim() ? userEmail.trim() : "anon";
    return `fantasy_welcome_seen_${safeEmail}`;
  }, [userEmail]);

  useEffect(() => {
    if (!token) return;
    const stored = localStorage.getItem(welcomeKey);
    setWelcomeSeen(stored === "1");
  }, [token, welcomeKey]);

  useEffect(() => {
    if (teamLoaded && needsTeamName && !welcomeSeen) {
      setWelcomeOpen(true);
    } else {
      setWelcomeOpen(false);
    }
  }, [teamLoaded, needsTeamName, welcomeSeen]);

  useEffect(() => {
    if (!token || roundMissing || !currentRound) return;
    const payload = {
      roundNumber: currentRound,
      slots: lineupSlots,
      captainId,
      viceCaptainId
    };
    localStorage.setItem(draftKey, JSON.stringify(payload));
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
      return { ...slot, player_id: null };
    }
    const role = resolveRoleForPlayer(playerId);
    return role ? { ...slot, player_id: playerId, role } : { ...slot, player_id: playerId };
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
            return { ...slot, player_id: null };
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
        slot.slot_index === selectedSlot.slot_index ? { ...slot, player_id: null } : slot
      )
    );
    setSelectedSlot({ ...selectedSlot, player_id: null });
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
          return { ...slot, player_id: null };
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

  const handleSave = async () => {
    if (nameGateOpen) return;
    if (roundMissing) {
      setSaveErrors(["rounds_not_configured"]);
      return;
    }
    if (!token) return;
    setSaveErrors(null);
    setSaveMessage(null);
    const localErrors = [
      ...new Set([...validateSquad(squad), ...validateLineup(lineupSlots, squad)])
    ];
    if (localErrors.length > 0) {
      setSaveErrors(localErrors);
      return;
    }
    try {
      await saveLineup(
        token,
        lineupSlots,
        currentRound || undefined,
        captainId,
        viceCaptainId
      );
      setSaveMessage("XI guardado correctamente");
    } catch (err) {
      setSaveErrors([String(err)]);
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
      const player = squadMap.get(slot.player_id as number);
      return player ? { slot, player } : null;
    })
    .filter((item): item is { slot: LineupSlot; player: Player } => item !== null);
  const selectedPlayer = selectedSlot?.player_id
    ? squadMap.get(selectedSlot.player_id)
    : undefined;
  const selectedOpponent = selectedPlayer
    ? opponentByTeamId.get(selectedPlayer.team_id)
    : undefined;

  const isTestEnv = appEnv === "test";
  const sizeClass = isTestEnv ? "h-12 w-12" : "h-24 w-24";
  const badgeClass = "h-[25%] w-[25%]";

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
            />
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Suplentes</h2>
          <div className="grid grid-cols-4 gap-2">
            {bench.map((slot) => (
              <LineupSlotCard
                key={slot.slot_index}
                slot={slot}
                player={slot.player_id ? squadMap.get(slot.player_id) : undefined}
                isCaptain={Boolean(slot.player_id && captainId === slot.player_id)}
                isViceCaptain={Boolean(slot.player_id && viceCaptainId === slot.player_id)}
                opponent={
                  slot.player_id && squadMap.get(slot.player_id)
                    ? opponentByTeamId.get(
                        (squadMap.get(slot.player_id) as Player).team_id
                      )
                    : undefined
                }
                onClick={() => handleSlotClick(slot)}
                compact
              />
            ))}
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
                className={isTestEnv ? "h-14 w-14" : "h-20 w-20"}
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
      </div>

      <FabMenu onSave={handleSave} />

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
          setNameGateOpen(true);
        }}
      />

      <TeamNameGate
        open={nameGateOpen}
        teamName={teamName}
        onTeamNameChange={setTeamName}
        error={teamNameError}
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
            setNameGateOpen(false);
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
                    roundNumber={currentRound}
                    teamName={teamNameById.get(selectedPlayer.team_id)}
                    fixtures={fixtures}
                  />
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
        onClose={() => setSheetOpen(false)}
        title={selectedSlot?.player_id ? squadMap.get(selectedSlot.player_id)?.name : "Slot"}
      >
        {selectedSlot ? (
          <div className="space-y-4">
            {selectedPlayer ? (
              <div className="space-y-2">
                <PlayerCard player={selectedPlayer} />
                <PlayerFantasyDetails
                  player={selectedPlayer}
                  roundNumber={currentRound}
                  teamName={teamNameById.get(selectedPlayer.team_id)}
                  fixtures={fixtures}
                />
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
              onClick={() => setSheetOpen(false)}
              className="w-full rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
            >
              Retornar
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted">Selecciona un slot</p>
            <button
              onClick={() => setSheetOpen(false)}
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

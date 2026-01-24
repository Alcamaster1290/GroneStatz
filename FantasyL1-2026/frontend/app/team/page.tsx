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
import StickyTopBar from "@/components/StickyTopBar";
import { getFixtures, getHealth, getLineup, getTeam, getTeams, saveLineup } from "@/lib/api";
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
    `/images/players/${playerId}.png`,
    `/images/players/${playerId}.jpg`,
    `/images/players/${playerId}.jpeg`,
    `/images/players/${playerId}.webp`
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

function PitchSlot({
  slot,
  player,
  opponent,
  onClick,
  sizeClass,
  badgeClass
}: {
  slot: LineupSlot;
  player?: Player;
  opponent?: { teamId: number; name?: string };
  onClick?: () => void;
  sizeClass: string;
  badgeClass: string;
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
          (isOver ? "ring-2 ring-accent " : "") +
          (isDragging ? "opacity-60" : "")
        }
      >
        <div className="relative">
          {player ? (
            <>
              <PlayerFace playerId={player.player_id} sizeClass={sizeClass} />
              <TeamBadge teamId={player.team_id} sizeClass={badgeClass} />
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
  badgeClass
}: {
  label: string;
  slots: LineupSlot[];
  squadMap: Map<number, Player>;
  opponentByTeamId: Map<number, { teamId: number; name?: string }>;
  onSelect: (slot: LineupSlot) => void;
  sizeClass: string;
  badgeClass: string;
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

  const [loading, setLoading] = useState(false);
  const [activePlayerId, setActivePlayerId] = useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<LineupSlot | null>(null);
  const [saveErrors, setSaveErrors] = useState<string[] | null>(null);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [teams, setTeams] = useState<{ id: number; name_short?: string; name_full?: string }[]>(
    []
  );
  const [appEnv, setAppEnv] = useState<string>("local");

  const squadMap = useMemo(
    () => new Map(squad.map((player) => [player.player_id, player])),
    [squad]
  );
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

  useEffect(() => {
    const stored = localStorage.getItem("fantasy_token");
    if (!token && stored) {
      setToken(stored);
    }
  }, [token, setToken]);

  useEffect(() => {
    if (!token) return;

    const load = async () => {
      setLoading(true);
      try {
        const team = await getTeam(token);
        setSquad(team.squad || []);

        const lineup = await getLineup(token);
        setCurrentRound(lineup.round_number);
        const squadById = new Map((team.squad || []).map((player) => [player.player_id, player]));
        const normalizedSlots = (lineup.slots || []).map((slot) => {
          if (slot.player_id) {
            const player = squadById.get(slot.player_id);
            if (player) {
              return { ...slot, role: player.position };
            }
          }
          return slot;
        });
        setLineupSlots(normalizedSlots);
        getFixtures(lineup.round_number)
          .then(setFixtures)
          .catch(() => setFixtures([]));
      } finally {
        setLoading(false);
      }
    };

    load().catch(() => undefined);
  }, [token, setSquad, setLineupSlots, setCurrentRound]);

  useEffect(() => {
    getTeams().then(setTeams).catch(() => undefined);
  }, []);

  useEffect(() => {
    getHealth()
      .then((data) => setAppEnv(data.env || "local"))
      .catch(() => setAppEnv("local"));
  }, []);

  useEffect(() => {
    if (!loading && squad.length > 0 && lineupSlots.length === 0) {
      setLineupSlots(buildDefaultSlots());
    }
  }, [loading, squad.length, lineupSlots.length, setLineupSlots]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

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
    setSheetOpen(true);
  };

  const handleRemovePlayer = () => {
    if (!selectedSlot) return;
    setLineupSlots(
      lineupSlots.map((slot) =>
        slot.slot_index === selectedSlot.slot_index ? { ...slot, player_id: null } : slot
      )
    );
    setSheetOpen(false);
  };

  const handleCaptain = () => {
    if (!selectedSlot?.player_id) return;
    setCaptainId(selectedSlot.player_id);
    setSheetOpen(false);
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
    setSheetOpen(false);
  };

  const handleSave = async () => {
    if (!token) return;
    setSaveErrors(null);
    const localErrors = [
      ...new Set([...validateSquad(squad), ...validateLineup(lineupSlots, squad)])
    ];
    if (localErrors.length > 0) {
      setSaveErrors(localErrors);
      return;
    }
    try {
      await saveLineup(token, lineupSlots, currentRound || undefined);
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
          <h1 className="text-xl font-semibold">Equipo</h1>
          <p className="text-xs text-muted">Ronda {currentRound ?? "-"}</p>
        </div>
      </div>
      <StickyTopBar budgetUsed={budgetUsed} budgetLeft={budgetLeft} />

      <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Titulares</h2>
          <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-emerald-900/40 via-emerald-950/40 to-black/30 p-4">
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
              />
              <PitchRow
                label="Medio"
                slots={startersByRole.M}
                squadMap={squadMap}
                opponentByTeamId={opponentByTeamId}
                onSelect={handleSlotClick}
                sizeClass={sizeClass}
                badgeClass={badgeClass}
              />
              <PitchRow
                label="Defensa"
                slots={startersByRole.D}
                squadMap={squadMap}
                opponentByTeamId={opponentByTeamId}
                onSelect={handleSlotClick}
                sizeClass={sizeClass}
                badgeClass={badgeClass}
              />
              <PitchRow
                label="Arquero"
                slots={startersByRole.G}
                squadMap={squadMap}
                opponentByTeamId={opponentByTeamId}
                onSelect={handleSlotClick}
                sizeClass={sizeClass}
                badgeClass={badgeClass}
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

        <DragOverlay>{activePlayer ? <PlayerCard player={activePlayer} /> : null}</DragOverlay>
      </DndContext>

      <div className="glass rounded-2xl p-4">
        <p className="text-xs text-muted">Capitan</p>
        <p className="text-sm text-ink">
          {captainId && squadMap.get(captainId) ? squadMap.get(captainId)?.name : "No asignado"}
        </p>
      </div>

      <FabMenu onSave={handleSave} />

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
            <div className="mt-3 space-y-2 text-xs text-warning">
              {saveErrors.map((error) => (
                <p key={error}>{error}</p>
              ))}
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

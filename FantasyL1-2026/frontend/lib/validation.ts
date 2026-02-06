import { LineupSlot, Player } from "./types";

export function validateSquad(players: Player[], budgetCap: number = 100): string[] {
  const errors: string[] = [];
  if (players.length !== 15) errors.push("squad_must_have_15_players");
  const ids = players.map((p) => p.player_id);
  if (new Set(ids).size !== ids.length) errors.push("squad_has_duplicate_players");

  const positionCounts = players.reduce(
    (acc, p) => {
      acc[p.position] = (acc[p.position] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  if ((positionCounts.G || 0) !== 2) errors.push("squad_must_have_2_goalkeepers");
  const d = positionCounts.D || 0;
  const m = positionCounts.M || 0;
  const f = positionCounts.F || 0;
  if (d < 3 || d > 6) errors.push("squad_defenders_out_of_range");
  if (m < 3 || m > 6) errors.push("squad_midfielders_out_of_range");
  if (f < 1 || f > 3) errors.push("squad_forwards_out_of_range");

  const clubCounts = players.reduce((acc, p) => {
    acc[p.team_id] = (acc[p.team_id] || 0) + 1;
    return acc;
  }, {} as Record<number, number>);
  if (Object.values(clubCounts).some((count) => count > 3)) {
    errors.push("max_3_players_per_team");
  }

  const budgetUsed = players.reduce((sum, p) => sum + p.price_current, 0);
  if (budgetUsed - budgetCap > 1e-6) errors.push("budget_exceeded");

  return errors;
}

export function validateLineup(slots: LineupSlot[], squad: Player[]): string[] {
  const errors: string[] = [];
  if (slots.length !== 15) errors.push("lineup_must_have_15_slots");

  const slotIndexes = slots.map((s) => s.slot_index);
  if (new Set(slotIndexes).size !== slots.length) errors.push("lineup_slot_index_duplicate");

  const starters = slots.filter((s) => s.is_starter);
  const bench = slots.filter((s) => !s.is_starter);
  if (starters.length !== 11 || bench.length !== 4) {
    errors.push("lineup_requires_11_starters_and_4_bench");
  }

  if (slots.some((s) => s.player_id === null)) {
    errors.push("lineup_has_empty_slots");
  }

  const playerIds = slots.map((s) => s.player_id).filter(Boolean) as number[];
  if (new Set(playerIds).size !== playerIds.length) {
    errors.push("lineup_has_duplicate_players");
  }

  const squadMap = new Map(squad.map((p) => [p.player_id, p]));
  if (playerIds.some((id) => !squadMap.has(id))) {
    errors.push("lineup_players_not_in_squad");
  }

  const starterPositions = starters.reduce(
    (acc, slot) => {
      const player = slot.player_id ? squadMap.get(slot.player_id) : undefined;
      if (player) {
        acc[player.position] = (acc[player.position] || 0) + 1;
      }
      return acc;
    },
    {} as Record<string, number>
  );

  if ((starterPositions.G || 0) < 1) errors.push("lineup_starters_need_goalkeeper");
  if ((starterPositions.G || 0) > 1) errors.push("lineup_starters_max_1_goalkeeper");
  if ((starterPositions.D || 0) < 1) errors.push("lineup_starters_need_defender");
  if ((starterPositions.M || 0) < 1) errors.push("lineup_starters_need_midfielder");
  if ((starterPositions.F || 0) < 1) errors.push("lineup_starters_need_forward");
  if ((starterPositions.F || 0) > 4) errors.push("lineup_starters_max_4_forwards");

  return errors;
}

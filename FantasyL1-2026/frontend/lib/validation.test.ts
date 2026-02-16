import { validateSquad, validateLineup } from './validation';
import { Player, LineupSlot, Position } from './types';

// Helper to create a mock player
const createMockPlayer = (
  id: number,
  position: Position,
  teamId: number = 1,
  price: number = 5.0
): Player => ({
  player_id: id,
  name: `Player ${id}`,
  position,
  team_id: teamId,
  price_current: price,
});

const createValidSquad = (): Player[] => {
  const players: Player[] = [];
  let id = 1;
  // 2 G
  players.push(createMockPlayer(id++, 'G', 1));
  players.push(createMockPlayer(id++, 'G', 2));
  // 5 D
  for(let i=0; i<5; i++) players.push(createMockPlayer(id++, 'D', i+3));
  // 5 M
  for(let i=0; i<5; i++) players.push(createMockPlayer(id++, 'M', i+8));
  // 3 F
  for(let i=0; i<3; i++) players.push(createMockPlayer(id++, 'F', i+13));
  return players;
};

const createValidLineup = (squad: Player[]): LineupSlot[] => {
  const slots: LineupSlot[] = [];

  // Standard 4-4-2 formation
  // Starters: 1 G, 4 D, 4 M, 2 F
  // Bench: 1 G, 1 D, 1 M, 1 F

  const g = squad.filter(p => p.position === 'G');
  const d = squad.filter(p => p.position === 'D');
  const m = squad.filter(p => p.position === 'M');
  const f = squad.filter(p => p.position === 'F');

  let slotIndex = 1;

  // Starters
  slots.push({ slot_index: slotIndex++, is_starter: true, role: 'G', player_id: g[0].player_id });

  for(let i=0; i<4; i++) slots.push({ slot_index: slotIndex++, is_starter: true, role: 'D', player_id: d[i].player_id });
  for(let i=0; i<4; i++) slots.push({ slot_index: slotIndex++, is_starter: true, role: 'M', player_id: m[i].player_id });
  for(let i=0; i<2; i++) slots.push({ slot_index: slotIndex++, is_starter: true, role: 'F', player_id: f[i].player_id });

  // Bench
  slots.push({ slot_index: slotIndex++, is_starter: false, role: 'G', player_id: g[1].player_id });
  slots.push({ slot_index: slotIndex++, is_starter: false, role: 'D', player_id: d[4].player_id });
  slots.push({ slot_index: slotIndex++, is_starter: false, role: 'M', player_id: m[4].player_id });
  slots.push({ slot_index: slotIndex++, is_starter: false, role: 'F', player_id: f[2].player_id });

  return slots;
};

describe('validateSquad', () => {
  it('should return no errors for a valid squad', () => {
    const squad = createValidSquad();
    const errors = validateSquad(squad, 100);
    expect(errors).toEqual([]);
  });

  it('should return error if squad size is not 15', () => {
    const squad = createValidSquad().slice(0, 14);
    const errors = validateSquad(squad, 100);
    expect(errors).toContain('squad_must_have_15_players');
  });

  it('should return error for duplicate players', () => {
    const squad = createValidSquad();
    squad[1] = { ...squad[0] }; // Duplicate the first player
    const errors = validateSquad(squad, 100);
    expect(errors).toContain('squad_has_duplicate_players');
  });

  it('should validate goalkeeper count', () => {
    // 1 G, extra F
    const squad = createValidSquad();
    squad[1].position = 'F';
    // Now: 1 G, 5 D, 5 M, 4 F.
    // Errors: G count != 2, F > 3.
    const errors = validateSquad(squad, 100);
    expect(errors).toContain('squad_must_have_2_goalkeepers');
    expect(errors).toContain('squad_forwards_out_of_range');
  });

  it('should validate defender count', () => {
    // 2 D, extra M (so 2 G, 2 D, 8 M, 3 F)
    const squad = createValidSquad();
    squad[2].position = 'M';
    squad[3].position = 'M';
    squad[4].position = 'M';
    const errors = validateSquad(squad, 100);
    expect(errors).toContain('squad_defenders_out_of_range');
    expect(errors).toContain('squad_midfielders_out_of_range');
  });

  it('should validate team limits', () => {
    const squad = createValidSquad();
    // Set 4 players to team 1
    squad[0].team_id = 1;
    squad[1].team_id = 1;
    squad[2].team_id = 1;
    squad[3].team_id = 1;
    const errors = validateSquad(squad, 100);
    expect(errors).toContain('max_3_players_per_team');
  });

  it('should validate budget', () => {
    const squad = createValidSquad();
    // Make everyone expensive
    squad.forEach(p => p.price_current = 10); // 15 * 10 = 150 > 100
    const errors = validateSquad(squad, 100);
    expect(errors).toContain('budget_exceeded');
  });
});

describe('validateLineup', () => {
  it('should return no errors for a valid lineup', () => {
    const squad = createValidSquad();
    const lineup = createValidLineup(squad);
    const errors = validateLineup(lineup, squad);
    expect(errors).toEqual([]);
  });

  it('should return error if lineup has empty slots', () => {
    const squad = createValidSquad();
    const lineup = createValidLineup(squad);
    lineup[0].player_id = null;
    const errors = validateLineup(lineup, squad);
    expect(errors).toContain('lineup_has_empty_slots');
  });

  it('should return error if lineup has duplicate players', () => {
    const squad = createValidSquad();
    const lineup = createValidLineup(squad);
    // Use the player from slot 0 in slot 1 as well
    lineup[1].player_id = lineup[0].player_id;
    const errors = validateLineup(lineup, squad);
    expect(errors).toContain('lineup_has_duplicate_players');
  });

  it('should return error if lineup player is not in squad', () => {
    const squad = createValidSquad();
    const lineup = createValidLineup(squad);
    // Set a non-existent player ID
    lineup[0].player_id = 999;
    const errors = validateLineup(lineup, squad);
    expect(errors).toContain('lineup_players_not_in_squad');
  });

  it('should validate starters composition (No GK)', () => {
    const squad = createValidSquad();
    const lineup = createValidLineup(squad);

    // Identify a starter GK slot and a bench F slot
    const starterGK = lineup.find(s => s.is_starter && squad.find(p => p.player_id === s.player_id)?.position === 'G');
    const benchF = lineup.find(s => !s.is_starter && squad.find(p => p.player_id === s.player_id)?.position === 'F');

    if (starterGK && benchF) {
       // Swap them: put F in starter, G in bench
       const temp = starterGK.player_id;
       starterGK.player_id = benchF.player_id;
       benchF.player_id = temp;
    }

    const errors = validateLineup(lineup, squad);
    expect(errors).toContain('lineup_starters_need_goalkeeper');
  });

  it('should validate max forwards in starters', () => {
    const squad = createValidSquad();
    const lineup = createValidLineup(squad);

    // Pick 5 starters
    const starterIds = lineup.filter(s => s.is_starter).map(s => s.player_id).slice(0, 5);

    // Change their position to 'F' in the squad
    starterIds.forEach(id => {
        const p = squad.find(player => player.player_id === id);
        if (p) p.position = 'F';
    });

    const errors = validateLineup(lineup, squad);
    expect(errors).toContain('lineup_starters_max_4_forwards');
  });
});

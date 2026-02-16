import { validateSquad, validateLineup } from './validation';
import { Player, LineupSlot, Position } from './types';
import assert from 'assert';

console.log('Running validation tests...');

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
  selected_count: 0,
  selected_percent: 0,
  goals: 0,
  assists: 0,
  minutesplayed: 0,
  saves: 0,
  fouls: 0,
  yellow_cards: 0,
  red_cards: 0
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

// --- Test Suite ---
let passed = 0;
let failed = 0;

function runTest(name: string, fn: () => void) {
  try {
    fn();
    console.log(`✅ PASS: ${name}`);
    passed++;
  } catch (e: any) {
    console.error(`❌ FAIL: ${name}`);
    console.error(e.message);
    failed++;
  }
}

// validateSquad Tests
runTest('validateSquad: should return no errors for a valid squad', () => {
  const squad = createValidSquad();
  const errors = validateSquad(squad, 100);
  assert.deepStrictEqual(errors, []);
});

runTest('validateSquad: should return error if squad size is not 15', () => {
  const squad = createValidSquad().slice(0, 14);
  const errors = validateSquad(squad, 100);
  assert.ok(errors.includes('squad_must_have_15_players'));
});

runTest('validateSquad: should return error for duplicate players', () => {
  const squad = createValidSquad();
  squad[1] = { ...squad[0] };
  const errors = validateSquad(squad, 100);
  assert.ok(errors.includes('squad_has_duplicate_players'));
});

runTest('validateSquad: should validate goalkeeper count', () => {
  const squad = createValidSquad();
  squad[1].position = 'F';
  const errors = validateSquad(squad, 100);
  assert.ok(errors.includes('squad_must_have_2_goalkeepers'));
  assert.ok(errors.includes('squad_forwards_out_of_range'));
});

runTest('validateSquad: should validate defender count', () => {
  const squad = createValidSquad();
  squad[2].position = 'M';
  squad[3].position = 'M';
  squad[4].position = 'M';
  const errors = validateSquad(squad, 100);
  assert.ok(errors.includes('squad_defenders_out_of_range'));
  assert.ok(errors.includes('squad_midfielders_out_of_range'));
});

runTest('validateSquad: should validate team limits', () => {
  const squad = createValidSquad();
  squad[0].team_id = 1;
  squad[1].team_id = 1;
  squad[2].team_id = 1;
  squad[3].team_id = 1;
  const errors = validateSquad(squad, 100);
  assert.ok(errors.includes('max_3_players_per_team'));
});

runTest('validateSquad: should validate budget', () => {
  const squad = createValidSquad();
  squad.forEach(p => p.price_current = 10);
  const errors = validateSquad(squad, 100);
  assert.ok(errors.includes('budget_exceeded'));
});

// validateLineup Tests
runTest('validateLineup: should return no errors for a valid lineup', () => {
  const squad = createValidSquad();
  const lineup = createValidLineup(squad);
  const errors = validateLineup(lineup, squad);
  assert.deepStrictEqual(errors, []);
});

runTest('validateLineup: should return error if lineup has empty slots', () => {
  const squad = createValidSquad();
  const lineup = createValidLineup(squad);
  lineup[0].player_id = null;
  const errors = validateLineup(lineup, squad);
  assert.ok(errors.includes('lineup_has_empty_slots'));
});

runTest('validateLineup: should return error if lineup has duplicate players', () => {
  const squad = createValidSquad();
  const lineup = createValidLineup(squad);
  lineup[1].player_id = lineup[0].player_id;
  const errors = validateLineup(lineup, squad);
  assert.ok(errors.includes('lineup_has_duplicate_players'));
});

runTest('validateLineup: should return error if lineup player is not in squad', () => {
  const squad = createValidSquad();
  const lineup = createValidLineup(squad);
  lineup[0].player_id = 999;
  const errors = validateLineup(lineup, squad);
  assert.ok(errors.includes('lineup_players_not_in_squad'));
});

runTest('validateLineup: should validate starters composition (No GK)', () => {
  const squad = createValidSquad();
  const lineup = createValidLineup(squad);

  const starterGK = lineup.find(s => s.is_starter && squad.find(p => p.player_id === s.player_id)?.position === 'G');
  const benchF = lineup.find(s => !s.is_starter && squad.find(p => p.player_id === s.player_id)?.position === 'F');

  if (starterGK && benchF) {
     const temp = starterGK.player_id;
     starterGK.player_id = benchF.player_id;
     benchF.player_id = temp;
  }

  const errors = validateLineup(lineup, squad);
  assert.ok(errors.includes('lineup_starters_need_goalkeeper'));
});

runTest('validateLineup: should validate max forwards in starters', () => {
  const squad = createValidSquad();
  const lineup = createValidLineup(squad);

  const starterIds = lineup.filter(s => s.is_starter).map(s => s.player_id).slice(0, 5);
  starterIds.forEach(id => {
      const p = squad.find(player => player.player_id === id);
      if (p) p.position = 'F';
  });

  const errors = validateLineup(lineup, squad);
  assert.ok(errors.includes('lineup_starters_max_4_forwards'));
});

console.log(`\nTests Completed: ${passed} Passed, ${failed} Failed.`);
if (failed > 0) process.exit(1);

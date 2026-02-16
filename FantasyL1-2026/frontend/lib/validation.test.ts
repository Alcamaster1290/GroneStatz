import { validateLineup } from './validation';
import { Player, LineupSlot, Position } from './types';

describe('validateLineup', () => {
  // Helper to create a dummy player
  const createPlayer = (id: number, position: Position, team_id: number = 1): Player => ({
    player_id: id,
    name: `Player ${id}`,
    position,
    team_id,
    price_current: 5,
    is_injured: false,
    goals: 0,
    assists: 0,
    saves: 0,
    fouls: 0,
    yellow_cards: 0,
    red_cards: 0,
  } as Player);

  // Helper to create a slot
  const createSlot = (index: number, is_starter: boolean, role: Position, player_id: number | null): LineupSlot => ({
    slot_index: index,
    is_starter,
    role,
    player_id,
  });

  const generateValidLineup = () => {
    // 1 GK, 4 D, 4 M, 2 F starters
    // 1 GK, 1 D, 1 M, 1 F bench
    const players: Player[] = [
      createPlayer(1, 'G'),
      createPlayer(2, 'D'), createPlayer(3, 'D'), createPlayer(4, 'D'), createPlayer(5, 'D'),
      createPlayer(6, 'M'), createPlayer(7, 'M'), createPlayer(8, 'M'), createPlayer(9, 'M'),
      createPlayer(10, 'F'), createPlayer(11, 'F'),
      // Bench
      createPlayer(12, 'G'), createPlayer(13, 'D'), createPlayer(14, 'M'), createPlayer(15, 'F'),
    ];

    const slots: LineupSlot[] = [
      createSlot(0, true, 'G', 1),
      createSlot(1, true, 'D', 2), createSlot(2, true, 'D', 3), createSlot(3, true, 'D', 4), createSlot(4, true, 'D', 5),
      createSlot(5, true, 'M', 6), createSlot(6, true, 'M', 7), createSlot(7, true, 'M', 8), createSlot(8, true, 'M', 9),
      createSlot(9, true, 'F', 10), createSlot(10, true, 'F', 11),
      // Bench
      createSlot(11, false, 'G', 12), createSlot(12, false, 'D', 13), createSlot(13, false, 'M', 14), createSlot(14, false, 'F', 15),
    ];

    return { players, slots };
  };

  it('should return no errors for a valid lineup', () => {
    const { players, slots } = generateValidLineup();
    const errors = validateLineup(slots, players);
    expect(errors).toHaveLength(0);
  });

  it('should return error if slots length is not 15', () => {
    const { players, slots } = generateValidLineup();
    const truncatedSlots = slots.slice(0, 14);
    const errors = validateLineup(truncatedSlots, players);
    expect(errors).toContain('lineup_must_have_15_slots');
  });

  it('should return error if duplicate slot indexes exist', () => {
    const { players, slots } = generateValidLineup();
    slots[1].slot_index = 0; // Duplicate index 0
    const errors = validateLineup(slots, players);
    expect(errors).toContain('lineup_slot_index_duplicate');
  });

  it('should return error if not 11 starters and 4 bench', () => {
    const { players, slots } = generateValidLineup();
    // Move one starter to bench
    slots[10].is_starter = false;
    const errors = validateLineup(slots, players);
    expect(errors).toContain('lineup_requires_11_starters_and_4_bench');
  });

  it('should return error if empty slots exist', () => {
    const { players, slots } = generateValidLineup();
    slots[0].player_id = null;
    const errors = validateLineup(slots, players);
    expect(errors).toContain('lineup_has_empty_slots');
  });

  it('should return error if duplicate players exist', () => {
    const { players, slots } = generateValidLineup();
    slots[1].player_id = 1; // Duplicate player 1
    const errors = validateLineup(slots, players);
    expect(errors).toContain('lineup_has_duplicate_players');
  });

  it('should return error if player not in squad', () => {
    const { players, slots } = generateValidLineup();
    slots[0].player_id = 999; // Player 999 not in squad
    const errors = validateLineup(slots, players);
    expect(errors).toContain('lineup_players_not_in_squad');
  });

  describe('Formation Constraints', () => {
    it('should return error if no goalkeeper starter', () => {
        const { players, slots } = generateValidLineup();
        // Swap starter GK (id 1) with bench D (id 13)
        // Make starter slot 0 a Defender (using player 13)
        // Make bench slot 11 a GK (using player 1)

        // Note: validateLineup checks the player's position from the squad, not the slot role.
        // So we need to put a non-GK player in the starter GK slot.

        // Let's replace the GK starter (player 1) with a Defender (player 13)
        slots[0].player_id = 13; // Player 13 is D
        slots[11].player_id = 1; // Player 1 is G (moved to bench)

        // We now have 5 D starters, 0 G starters.
        const errors = validateLineup(slots, players);
        expect(errors).toContain('lineup_starters_need_goalkeeper');
    });

    it('should return error if more than 1 goalkeeper starter', () => {
        const { players, slots } = generateValidLineup();
        // We need another GK in the squad to test this properly without duplicating players.
        // Let's change player 2 (D) to be a GK.
        players[1].position = 'G';
        // Now slot 1 (which holds player 2) is a starter holding a GK.
        // Slot 0 (player 1) is also a GK.
        // So we have 2 GKs starting.

        const errors = validateLineup(slots, players);
        expect(errors).toContain('lineup_starters_max_1_goalkeeper');
    });

    it('should return error if no defender starter', () => {
         const { players, slots } = generateValidLineup();
         // Change all defender starters to Midfielders
         // Players 2,3,4,5 are D.
         // Let's change their position in the squad to M
         players[1].position = 'M';
         players[2].position = 'M';
         players[3].position = 'M';
         players[4].position = 'M';

         const errors = validateLineup(slots, players);
         expect(errors).toContain('lineup_starters_need_defender');
    });

    it('should return error if no midfielder starter', () => {
        const { players, slots } = generateValidLineup();
        // Change all M starters to F
        // Players 6,7,8,9 are M.
        players[5].position = 'F';
        players[6].position = 'F';
        players[7].position = 'F';
        players[8].position = 'F';

        const errors = validateLineup(slots, players);
        expect(errors).toContain('lineup_starters_need_midfielder');
   });

   it('should return error if no forward starter', () => {
        const { players, slots } = generateValidLineup();
        // Change all F starters to M
        // Players 10, 11 are F.
        players[9].position = 'M';
        players[10].position = 'M';

        const errors = validateLineup(slots, players);
        expect(errors).toContain('lineup_starters_need_forward');
   });

   it('should return error if more than 4 forwards starter', () => {
        const { players, slots } = generateValidLineup();
        // We have 2 F starters (10, 11).
        // Need 5 F starters to trigger error.
        // Let's change 3 Defenders (2,3,4) to F.
        players[1].position = 'F';
        players[2].position = 'F';
        players[3].position = 'F';

        // Total F starters: 2 (original) + 3 (converted) = 5.

        const errors = validateLineup(slots, players);
        expect(errors).toContain('lineup_starters_max_4_forwards');
   });
  });
});

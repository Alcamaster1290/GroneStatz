import { create } from "zustand";

import { LineupSlot, MarketFiltersState, Player } from "./types";

type StoreState = {
  token: string | null;
  userEmail: string | null;
  squad: Player[];
  lineupSlots: LineupSlot[];
  currentRound: number | null;
  validationErrors: string[];
  budgetUsed: number;
  budgetLeft: number;
  captainId: number | null;
  viceCaptainId: number | null;
  marketFilters: MarketFiltersState;
  marketDraftSquad: Player[];
  marketDraftBackup: Player[];
  marketDraftLoaded: boolean;
  setToken: (token: string | null) => void;
  setUserEmail: (email: string | null) => void;
  setSquad: (squad: Player[]) => void;
  setLineupSlots: (slots: LineupSlot[] | ((prev: LineupSlot[]) => LineupSlot[])) => void;
  setCurrentRound: (round: number | null) => void;
  setValidationErrors: (errors: string[]) => void;
  setCaptainId: (playerId: number | null) => void;
  setViceCaptainId: (playerId: number | null) => void;
  setMarketFilters: (filters: MarketFiltersState) => void;
  setMarketDraftSquad: (squad: Player[] | ((prev: Player[]) => Player[])) => void;
  setMarketDraftBackup: (squad: Player[]) => void;
  setMarketDraftLoaded: (loaded: boolean) => void;
};

const computeBudget = (squad: Player[]) => {
  const budgetUsed = squad.reduce((sum, player) => sum + (player.bought_price ?? player.price_current), 0);
  const rawLeft = 100 - budgetUsed;
  const budgetLeft = Math.abs(rawLeft) < 1e-6 ? 0 : rawLeft;
  return { budgetUsed, budgetLeft };
};

const normalizeSquad = (squad: Player[]) => {
  const seen = new Set<number>();
  const unique: Player[] = [];
  for (const player of squad) {
    if (seen.has(player.player_id)) continue;
    seen.add(player.player_id);
    unique.push(player);
    if (unique.length >= 15) break;
  }
  return unique;
};

export const useFantasyStore = create<StoreState>((set) => ({
  token: null,
  userEmail: null,
  squad: [],
  lineupSlots: [],
  currentRound: null,
  validationErrors: [],
  budgetUsed: 0,
  budgetLeft: 100,
  captainId: null,
  viceCaptainId: null,
  marketFilters: {
    positions: [],
    minPrice: "",
    maxPrice: "",
    query: "",
    teamId: ""
  },
  marketDraftSquad: [],
  marketDraftBackup: [],
  marketDraftLoaded: false,
  setToken: (token) => set({ token }),
  setUserEmail: (userEmail) => set({ userEmail }),
  setSquad: (squad) => {
    const normalized = normalizeSquad(squad);
    const { budgetUsed, budgetLeft } = computeBudget(normalized);
    set({ squad: normalized, budgetUsed, budgetLeft });
  },
  setLineupSlots: (lineupSlots) =>
    set((state) => ({
      lineupSlots: typeof lineupSlots === "function" ? lineupSlots(state.lineupSlots) : lineupSlots
    })),
  setCurrentRound: (currentRound) => set({ currentRound }),
  setValidationErrors: (validationErrors) => set({ validationErrors }),
  setCaptainId: (captainId) => set({ captainId }),
  setViceCaptainId: (viceCaptainId) => set({ viceCaptainId }),
  setMarketFilters: (marketFilters) => set({ marketFilters }),
  setMarketDraftSquad: (marketDraftSquad) =>
    set((state) => ({
      marketDraftSquad: normalizeSquad(
        typeof marketDraftSquad === "function"
          ? marketDraftSquad(state.marketDraftSquad)
          : marketDraftSquad
      )
    })),
  setMarketDraftBackup: (marketDraftBackup) => set({ marketDraftBackup }),
  setMarketDraftLoaded: (marketDraftLoaded) => set({ marketDraftLoaded })
}));

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
  const budgetLeft = 100 - budgetUsed;
  return { budgetUsed, budgetLeft };
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
    query: ""
  },
  marketDraftSquad: [],
  marketDraftBackup: [],
  marketDraftLoaded: false,
  setToken: (token) => set({ token }),
  setUserEmail: (userEmail) => set({ userEmail }),
  setSquad: (squad) => {
    const { budgetUsed, budgetLeft } = computeBudget(squad);
    set({ squad, budgetUsed, budgetLeft });
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
      marketDraftSquad:
        typeof marketDraftSquad === "function"
          ? marketDraftSquad(state.marketDraftSquad)
          : marketDraftSquad
    })),
  setMarketDraftBackup: (marketDraftBackup) => set({ marketDraftBackup }),
  setMarketDraftLoaded: (marketDraftLoaded) => set({ marketDraftLoaded })
}));

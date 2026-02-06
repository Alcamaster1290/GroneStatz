import { create } from "zustand";

import { LineupSlot, MarketFiltersState, Player } from "./types";

type StoreState = {
  token: string | null;
  userEmail: string | null;
  squad: Player[];
  lineupSlots: LineupSlot[];
  currentRound: number | null;
  validationErrors: string[];
  budgetCap: number;
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
  setSquad: (squad: Player[], budgetCap?: number) => void;
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

const roundToTenth = (value: number) => Math.round(value * 10) / 10;

const computeBudget = (squad: Player[], budgetCap: number) => {
  const budgetUsedRaw = squad.reduce(
    (sum, player) => sum + (player.bought_price ?? player.price_current),
    0
  );
  const budgetUsed = roundToTenth(budgetUsedRaw);
  const rawLeft = roundToTenth(budgetCap - budgetUsed);
  const budgetLeft = Math.abs(rawLeft) < 0.05 ? 0 : rawLeft;
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
  budgetCap: 100,
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
  setSquad: (squad, budgetCap) =>
    set((state) => {
      const normalized = normalizeSquad(squad);
      const nextCap =
        typeof budgetCap === "number" && Number.isFinite(budgetCap)
          ? roundToTenth(budgetCap)
          : state.budgetCap;
      const { budgetUsed, budgetLeft } = computeBudget(normalized, nextCap);
      return { squad: normalized, budgetCap: nextCap, budgetUsed, budgetLeft };
    }),
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

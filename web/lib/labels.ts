/** Bandas de importancia para ganar el torneo (las aprobadas en la maqueta): derrotas que aún puede permitirse el equipo. */
export const BAND_NAMES = ["Asegurado", "Baja", "Media", "Alta", "Crítica", "Fuera de alcance"] as const;
export const BAND_COLORS = ["#0a84ff", "#34c759", "#ffcc00", "#ff9500", "#ff3b30", "#8e8e93"] as const;
export const BAND_HINTS = ["umbral alcanzado", "puede perder 3 o más", "puede perder 2", "puede perder 1", "no puede perder", "ni llega a 37 pts"] as const;

export const LEVEL_ORDER = ["Candidato", "Competitivo", "Promedio", "Descenso"] as const;
export const POSITION_LABEL: Record<string, string> = { G: "Arquero", D: "Defensa", M: "Mediocampista", F: "Delantero" };
export const RESULT_LABEL: Record<string, string> = { G: "Ganó", E: "Empató", P: "Perdió" };

/** Un equipo con tantos metros más arriba que su sede habitual cambia el partido: se resalta desde 1.500 m. */
export const HIGH_ALTITUDE_DIFF = 1500;
export const MID_ALTITUDE_DIFF = 500;

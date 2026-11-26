/**
 * Geometría de la cancha en coordenadas Opta (100 × 100), verificadas con el código de Streamlit
 * (docs/recursos-dashboard/coordenadas-y-orientacion.md):
 * - Tiros: `x` es la distancia a la línea de fondo del arco que se ataca (0 = línea de gol), igual para local y visita; `y` de 0 a 100, centro 50.
 * - Heatmap: `x` va en dirección de ataque (0 = arco propio, 100 = arco rival).
 */
export const OPTA = {
  spot: 11.5,
  box: { depth: 17, y0: 21.1, y1: 78.9 },
  six: { depth: 5.8, y0: 36.8, y1: 63.2 },
  goal: { y0: 44.2, y1: 55.8 },
} as const;

/** La media cancha ofensiva llega a x = 50. */
export const HALF = 50;

/** Un tiro sobre una media cancha con el arco arriba: `y` reparte el ancho y `x` la distancia al arco. */
export function shotToHalfPitch(x: number, y: number, width: number, height: number): { cx: number; cy: number } {
  const lateral = Math.min(Math.max(y, 0), 100) / 100;
  const depth = Math.min(Math.max(x, 0), HALF) / HALF;
  return { cx: lateral * width, cy: depth * height };
}

/** Celda de la cuadrícula del heatmap sobre la cancha completa, atacando hacia la derecha. */
export function heatCell(ix: number, iy: number, cols: number, rows: number, width: number, height: number): { x: number; y: number; width: number; height: number } {
  const cellWidth = width / cols;
  const cellHeight = height / rows;
  return { x: ix * cellWidth, y: iy * cellHeight, width: cellWidth, height: cellHeight };
}

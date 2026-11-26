import { HALF, OPTA, heatCell, shotToHalfPitch } from "./pitch";

describe("shotToHalfPitch", () => {
  it("pone el punto de penal en el centro del ancho y a 11,5 de la línea de gol", () => {
    const { cx, cy } = shotToHalfPitch(OPTA.spot, 50, 340, 262.5);
    expect(cx).toBeCloseTo(170);
    expect(cy).toBeCloseTo((11.5 / HALF) * 262.5);
  });
  it("un tiro pegado a la línea de gol queda arriba y uno lejano abajo", () => {
    expect(shotToHalfPitch(1, 50, 100, 100).cy).toBeLessThan(shotToHalfPitch(40, 50, 100, 100).cy);
  });
  it("no se sale del área dibujada", () => {
    const { cx, cy } = shotToHalfPitch(80, 120, 100, 100);
    expect(cx).toBeLessThanOrEqual(100);
    expect(cy).toBeLessThanOrEqual(100);
  });
});

describe("heatCell", () => {
  it("la columna 0 es el arco propio y la última el arco rival, de izquierda a derecha", () => {
    const first = heatCell(0, 0, 20, 20, 400, 200);
    const last = heatCell(19, 0, 20, 20, 400, 200);
    expect(first.x).toBe(0);
    expect(last.x + last.width).toBeCloseTo(400);
    expect(first.width).toBeCloseTo(20);
    expect(first.height).toBeCloseTo(10);
  });
});

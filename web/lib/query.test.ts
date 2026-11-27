import { href, nextDirection } from "./query";

describe("href", () => {
  it("arma la URL con los parámetros que tienen valor y omite los vacíos", () => {
    expect(href("/liga/2026/Clausura", { cond: "local", valores: undefined, orden: "shots", dir: "", fecha: null })).toBe("/liga/2026/Clausura?cond=local&orden=shots");
  });
  it("devuelve la ruta sola cuando no hay parámetros", () => {
    expect(href("/liga/2026/Clausura", {})).toBe("/liga/2026/Clausura");
  });
  it("codifica los valores", () => {
    expect(href("/x", { q: "a b" })).toBe("/x?q=a%20b");
  });
});

describe("nextDirection", () => {
  it("la primera vez que se elige una columna ordena de mayor a menor", () => {
    expect(nextDirection("pts", "shots", "desc")).toBe("desc");
  });
  it("al pulsar la columna ya ordenada invierte el sentido", () => {
    expect(nextDirection("shots", "shots", "desc")).toBe("asc");
    expect(nextDirection("shots", "shots", "asc")).toBe("desc");
  });
});

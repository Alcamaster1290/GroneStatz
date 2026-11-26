import { formatDate, idFromSlug, meters, pct, signedMeters, slug } from "./format";

describe("pct", () => {
  it("usa coma decimal y un espacio antes del %", () => {
    expect(pct(0.18367, 1)).toBe("18,4 %");
    expect(pct(0.5, 0)).toBe("50 %");
  });
  it("devuelve un guion cuando no hay dato", () => {
    expect(pct(null)).toBe("—");
    expect(pct(undefined)).toBe("—");
  });
});

describe("formatDate", () => {
  it("muestra la fecha y la hora tal como vienen, que ya son hora de Lima", () => {
    expect(formatDate("2026-01-30T20:15:00")).toBe("30 ene 2026 · 20:15");
  });
  it("tolera la fecha sin dato", () => {
    expect(formatDate(null)).toBe("sin fecha");
  });
});

describe("slug e idFromSlug", () => {
  it("arma el slug sin tildes y recupera el id", () => {
    expect(slug(2307, "Alianza Atlético")).toBe("2307-alianza-atletico");
    expect(idFromSlug("2307-alianza-atletico")).toBe(2307);
  });
  it("acepta un id solo y rechaza lo que no empieza por número", () => {
    expect(idFromSlug("2311")).toBe(2311);
    expect(idFromSlug("alianza")).toBeNull();
  });
});

describe("meters", () => {
  it("separa miles con punto", () => {
    expect(meters(3254)).toBe("3.254 m");
    expect(meters(144)).toBe("144 m");
    expect(meters(null)).toBe("—");
  });
  it("signedMeters marca el signo con el menos tipográfico", () => {
    expect(signedMeters(3110)).toBe("+3.110 m");
    expect(signedMeters(-88)).toBe("−88 m");
    expect(signedMeters(0)).toBe("0 m");
  });
});

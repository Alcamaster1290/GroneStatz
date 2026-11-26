import sys, io, hashlib
from pathlib import Path
import pandas as pd
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(r"C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz")
G = REPO / "gronestats/images/teams"; F = REPO / "FantasyL1-2026/frontend/public/images/teams"
base = REPO / "gronestats/data/Liga 1 Peru"
names = {}
for s in (2022, 2023, 2024, 2025, 2026):
    t = pd.read_parquet(base / str(s) / "dashboard/current/teams.parquet")
    for r in t.itertuples(): names[int(r.team_id)] = str(r.short_name)
rows = []
for p in sorted(G.glob("*.png"), key=lambda p: p.stem):
    with Image.open(p) as im:
        im.load(); w, h = im.size; a = im.convert("RGBA")
        corners = [a.getpixel(c)[3] for c in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
        bbox = a.getchannel("A").getbbox(); fill = ((bbox[2] - bbox[0]) / w, (bbox[3] - bbox[1]) / h) if bbox else (0, 0)
        rows.append(dict(id=p.stem, equipo=names.get(int(p.stem), "(sin equipo)") if p.stem.isdigit() else p.stem, w=w, h=h, modo=im.mode,
                         kb=round(p.stat().st_size / 1024), alfa=sum(1 for c in corners if c == 0) >= 3, ocupa_ancho=round(fill[0], 2), ocupa_alto=round(fill[1], 2)))
d = pd.DataFrame(rows)
print(f"escudos: {len(d)} | idénticos en las 2 carpetas: {all((F / (x + '.png')).exists() and (F / (x + '.png')).read_bytes() == (G / (x + '.png')).read_bytes() for x in d.id)}")
print("resolución de origen (lado mayor): min=%d mediana=%d máx=%d" % (d[['w', 'h']].max(axis=1).min(), d[['w', 'h']].max(axis=1).median(), d[['w', 'h']].max(axis=1).max()))
print("distribución de tamaños:", d.groupby(["w", "h"]).size().sort_values(ascending=False).head(8).to_dict())
print("no cuadrados:", int((d.w != d.h).sum()), "| fondo transparente (>=3 esquinas):", int(d.alfa.sum()), "de", len(d), "| peso total: %.1f MB" % (d.kb.sum() / 1024))
print("\nescudos de menor resolución:"); print(d.assign(lado=d[["w", "h"]].max(axis=1)).sort_values("lado").head(8)[["id", "equipo", "w", "h", "kb", "alfa"]].to_string(index=False))
print("\nescudos con fondo opaco:", d[~d.alfa][["id", "equipo", "w", "h"]].to_string(index=False) if (~d.alfa).any() else "ninguno")

# ---- prueba de derivados: reducir SIEMPRE desde el original (nunca ampliar), con alfa premultiplicado (Pillow lo hace con LANCZOS)
SIZES = [16, 24, 32, 48, 64, 96, 128, 192, 256]
tot = {s: 0 for s in SIZES}; capped = 0
for r in d.itertuples():
    with Image.open(G / f"{r.id}.png") as im:
        im = im.convert("RGBA"); side = max(im.size)
        for s in SIZES:
            if s > side: capped += 1; continue
            k = s / side; out = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
            buf = io.BytesIO(); out.save(buf, "PNG", optimize=True); tot[s] += buf.tell()
print("\npeso total de derivados PNG por tamaño (KB, todos los escudos):", {s: round(v / 1024) for s, v in tot.items()})
print("combinaciones (escudo×tamaño) que NO se generan por superar la resolución de origen:", capped, "de", len(d) * len(SIZES))
d.to_pickle(Path(r"C:\Users\Alvaro\AppData\Local\Temp\claude\C--Users-Alvaro\7aa9f7eb-a5d4-4175-a966-e3e7260a7f9a\scratchpad\crests.pkl"))

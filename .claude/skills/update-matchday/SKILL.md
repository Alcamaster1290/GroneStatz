---
name: update-matchday
description: >
  Actualiza los datos de la última jornada jugada de Liga 1 Peru 2026:
  extrae stats de SofaScore via ScraperFC, corre el pipeline de GroneStats,
  y sincroniza los parquets al backend Fantasy. Invocable con /update-matchday.
---

# Update Matchday — Flujo completo de actualización post-jornada

## Contexto del Pipeline

El flujo de datos sigue esta cadena:

```
SofaScore API (via ScraperFC)
  → gronestats/data/Liga 1 Peru/2026/raw/details/xlsx/Sofascore_{match_id}.xlsx
  → gronestats/data/Liga 1 Peru/2026/raw/master/clean/Partidos_Liga 1 Peru_2026_limpio.xlsx
  → python -m gronestats.processing.pipeline run --season 2026
  → gronestats/data/Liga 1 Peru/2026/fantasy/current/*.parquet
  → Backend: ingest_parquets_to_duckdb + sync_duckdb_to_postgres
```

## Instrucciones de Ejecución

Ejecuta los siguientes pasos EN ORDEN. Reporta progreso entre cada paso.

### Paso 1: Identificar partidos faltantes

Determina qué match_ids ya fueron procesados y cuáles faltan:

```python
# Partidos ya extraídos (tienen XLSX en raw/details/xlsx/)
import glob
from pathlib import Path

raw_dir = Path("gronestats/data/Liga 1 Peru/2026/raw/details/xlsx")
existing_ids = {
    int(p.stem.replace("Sofascore_", ""))
    for p in raw_dir.glob("Sofascore_*.xlsx")
}

# Partidos en el master (todos los programados/jugados)
import pandas as pd
master_path = Path("gronestats/data/Liga 1 Peru/2026/raw/master/clean/Partidos_Liga 1 Peru_2026_limpio.xlsx")
master = pd.read_excel(master_path)
all_ids = set(master["match_id"].dropna().astype(int))

# Partidos con score (ya finalizados) que no tienen XLSX
finished = master.loc[master["home_score"].notna() & master["away_score"].notna()]
finished_ids = set(finished["match_id"].dropna().astype(int))
missing_ids = sorted(finished_ids - existing_ids)
```

Reporta cuántos partidos faltan y cuáles son (con nombres de equipos si es posible).

### Paso 2: Extraer datos de SofaScore

Para cada `match_id` faltante, ejecuta la extracción usando ScraperFC.
El notebook de referencia es `notebooks/active/nb_05_extraer_partido_por_match_id.ipynb`.

La extracción debe generar un archivo `Sofascore_{match_id}.xlsx` con estas hojas:
- **Player Stats**: stats de jugadores (player_id, minutesplayed, goals, assists, saves, fouls, etc.)
- **Team Stats**: stats de equipo
- **Average Positions**: posiciones promedio
- **Heatmaps**: datos de heatmap (opcional)
- **Shotmap**: tiros al arco (opcional)
- **Match Momentum**: momentum del partido (opcional)

Script de extracción por partido:

```python
import ScraperFC as sfc
import pandas as pd
from pathlib import Path

sofascore = sfc.Sofascore()
output_dir = Path("gronestats/data/Liga 1 Peru/2026/raw/details/xlsx")

def extract_match(match_id: str | int) -> Path:
    match_id = str(match_id)
    output_path = output_dir / f"Sofascore_{match_id}.xlsx"

    match_dict = sofascore.get_match_dict(match_id)

    # Player Stats
    try:
        player_stats = sofascore.scrape_player_match_stats(match_id)
    except Exception:
        player_stats = pd.DataFrame()

    # Team Stats
    try:
        team_stats = sofascore.scrape_team_match_stats(match_id)
    except Exception:
        team_stats = pd.DataFrame()

    # Average Positions
    try:
        avg_positions = sofascore.scrape_player_average_positions(match_id)
    except Exception:
        avg_positions = pd.DataFrame()

    # Shotmap
    try:
        shotmap = sofascore.scrape_match_shots(match_id)
    except Exception:
        shotmap = pd.DataFrame()

    # Momentum
    try:
        momentum = sofascore.scrape_match_momentum(match_id)
    except Exception:
        momentum = pd.DataFrame()

    # Heatmaps
    try:
        heatmaps_raw = sofascore.scrape_heatmaps(match_id)
        if isinstance(heatmaps_raw, dict):
            rows = []
            for pid, points in heatmaps_raw.items():
                for pt in (points or []):
                    rows.append({"player_id": pid, "x": pt.get("x"), "y": pt.get("y")})
            heatmaps = pd.DataFrame(rows)
        elif isinstance(heatmaps_raw, pd.DataFrame):
            heatmaps = heatmaps_raw
        else:
            heatmaps = pd.DataFrame()
    except Exception:
        heatmaps = pd.DataFrame()

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        if not player_stats.empty:
            player_stats.to_excel(writer, sheet_name="Player Stats", index=False)
        if not team_stats.empty:
            team_stats.to_excel(writer, sheet_name="Team Stats", index=False)
        if not avg_positions.empty:
            avg_positions.to_excel(writer, sheet_name="Average Positions", index=False)
        if not heatmaps.empty:
            heatmaps.to_excel(writer, sheet_name="Heatmaps", index=False)
        if not shotmap.empty:
            shotmap.to_excel(writer, sheet_name="Shotmap", index=False)
        if not momentum.empty:
            momentum.to_excel(writer, sheet_name="Match Momentum", index=False)

    return output_path
```

Ejecuta `extract_match(match_id)` para cada partido faltante. Añade pausa de 3-5 segundos entre partidos para evitar rate limiting.

### Paso 3: Actualizar el Master Clean

Si hay partidos nuevos que no están en el master (nuevos match_ids de la jornada), actualiza el archivo master:

```python
# Solo si hay match_ids nuevos no presentes en master
# Usa sofascore.get_match_dicts() o get_match_dict() para obtener info del partido
# y añade filas al master con: match_id, round_number, home_id, away_id, home, away,
# home_score, away_score, fecha, estadio, ciudad, status
```

### Paso 4: Ejecutar el pipeline de GroneStats

```bash
python -m gronestats.processing.pipeline run --league "Liga 1 Peru" --season 2026 --only-missing --publish-target fantasy
```

Esto procesa los nuevos XLSX, construye staging → curated → fantasy parquets.

### Paso 5: Sincronizar al Backend

Opción A — Si `watch_parquets.py` está corriendo, los cambios se detectan automáticamente.

Opción B — Ejecutar manualmente:

```bash
cd FantasyL1-2026
python scripts/watch_parquets.py --run-on-start
```

Opción C — Llamar al endpoint admin:

```bash
curl -X POST http://localhost:8000/api/admin/rebuild_catalog -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### Paso 6: Cargar player stats al Fantasy (opcional)

Si necesitas cargar las estadísticas de jugadores match-by-match al sistema de puntos:

```python
# Generar payload para POST /api/admin/player-stats
# Formato: {"round_number": N, "items": [{"match_id": ..., "player_id": ..., ...}]}
```

El notebook `nb_05_extraer_partido_por_match_id.ipynb` ya genera el formato `admin_stats_df` listo para usar.

### Paso 7: Verificación

Confirma que:
1. Los nuevos XLSX existen en `gronestats/data/Liga 1 Peru/2026/raw/details/xlsx/`
2. El pipeline terminó sin errores
3. `gronestats/data/Liga 1 Peru/2026/fantasy/current/player_match.parquet` tiene las filas nuevas
4. Los datos se sincronizaron al backend (verificar via API o DB)

## Notas Importantes

- **ScraperFC** debe estar instalado en el entorno (`pip install ScraperFC`)
- El scraper usa la API pública de SofaScore; puede fallar por rate limiting
- Añade delays entre llamadas (3-5s por partido)
- Si un partido no tiene datos aún en SofaScore (no se jugó), omítelo
- El pipeline con `--only-missing` solo procesa lo nuevo sin re-procesar lo existente
- Los match_ids de Liga 1 Peru 2026 están en el rango 153xxxxx-157xxxxx

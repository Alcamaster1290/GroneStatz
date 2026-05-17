# GroneStatz Monorepo

Monorepo de datos y producto para Liga 1 Perú. El repositorio concentra dos aplicaciones conectadas por bundles publicados por temporada:

- `gronestats/`: pipeline analítico y dashboard Streamlit.
- `FantasyL1-2026/`: backend FastAPI y frontend Next.js del fantasy.

## Estado actual

- El pipeline productivo es `python -m gronestats.processing.pipeline`.
- El dashboard consume solo `gronestats/data/Liga 1 Peru/<season>/dashboard/current`.
- Fantasy consume solo `gronestats/data/Liga 1 Peru/<season>/fantasy/current`.
- `raw`, `staging` y `curated` siguen existiendo para operación local, pero ya no forman parte del contrato publicado del repo.
- El código reemplazado por el pipeline vive en `gronestats/processing/legacy/`.

## Layout de datos

Por temporada:

- `gronestats/data/Liga 1 Peru/<season>/raw/`
- `gronestats/data/Liga 1 Peru/<season>/staging/`
- `gronestats/data/Liga 1 Peru/<season>/curated/`
- `gronestats/data/Liga 1 Peru/<season>/dashboard/current|releases/`
- `gronestats/data/Liga 1 Peru/<season>/fantasy/current|releases/`

Bundles publicados:

- `dashboard/current`: `matches`, `teams`, `players`, `player_match`, `player_totals_full_season`, `team_stats`, `average_positions`, `heatmap_points`, `shot_events`, `match_momentum`, `player_identity`
- `fantasy/current`: `matches`, `teams`, `players`, `players_fantasy`, `player_match`, `player_totals`, `player_team`, `player_transfer`, `team_stats`

## Flujo operativo

Pipeline completo:

```powershell
py -3.11 -m gronestats.processing.pipeline run --league "Liga 1 Peru" --season 2026 --mode full --publish-target all
```

Validación de una temporada publicada:

```powershell
py -3.11 -m gronestats.processing.pipeline validate --league "Liga 1 Peru" --season 2026 --target all
```

Wrapper PowerShell:

```powershell
.\scripts\gronestats\run_gronestats_pipeline.ps1 -Season 2026 -Mode incremental -OnlyMissing
```

## Dashboard

Entry point:

- `gronestats/dashboard/app.py`

Ejecutar:

```powershell
py -3.11 -m streamlit run gronestats/dashboard/app.py
```

El dashboard descubre automáticamente las temporadas publicadas y navega sobre `dashboard/current`.

## Fantasy

El backend usa por defecto el bundle publicado en:

- `gronestats/data/Liga 1 Peru/<SEASON_YEAR>/fantasy/current`

Documentación específica:

- `docs/gronestats/data_pipeline_plan.md`
- `docs/fantasy/README.md`
- `FantasyL1-2026/README.md`

## Legacy y compatibilidad

- `gronestats/processing/legacy/` contiene scripts históricos que siguen disponibles por compatibilidad.
- Las rutas antiguas en `gronestats/processing/*.py` quedaron como wrappers con aviso de deprecación.
- `scripts/run_etl_liga1_2025.py` también quedó como wrapper y redirige al pipeline.

## Tests

```powershell
py -3.11 -m pytest tests
```

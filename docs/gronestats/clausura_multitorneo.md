# Clausura 2026 y datos multi-torneo

Cómo se obtienen, limpian y modelan los datos del **Clausura 2026** (y del resto del Apertura) con el mismo pipeline que ya alimentaba el Apertura. Documentado el 2026-10-22.

## Idea central

El pipeline `gronestats` **ya era multi-torneo**: 2024 y 2025 se publicaron con Apertura, Clausura y (2025) Grand Final dentro de una sola temporada. Para 2026 no hace falta una carpeta ni un season nuevos:

- SofaScore expone ambos torneos bajo el mismo `unique-tournament` **406** y la misma temporada `"2026"` (id **88529**).
- `matches.parquet` trae la columna `tournament` (`Liga 1, Apertura` / `Liga 1, Clausura`). `round_number` **reinicia en cada torneo**, así que la ronda 1 aparece dos veces.
- La clave única de un partido es `match_id`. `player_match`, `team_stats`, `average_positions`, `shot_events` y `match_momentum` se vinculan por `match_id` y no llevan ronda ni torneo.
- El warehouse (`Liga 1 Peru/warehouse/gronestats.duckdb`) se particiona por `season_year`, no por torneo: al reconstruir 2026 se reemplazan todas sus filas.
- El dashboard ya distingue torneos (`gronestats/dashboard/config.py`: `TOURNAMENT_LABELS`, `TOURNAMENT_ORDER`, etiquetas tipo `Apertura · R1`) y existe un test de que la ronda 1 de ambos no se mezcla (`tests/test_dashboard_metrics.py`).

## Cadena de datos

```
SofaScore ── sofascore_session.get_json (Chrome persistente) ──┐
                                                               v
data_loader_unprep  ->  Partidos_Liga 1 Peru_2026{,_limpio}.xlsx   (+ copia en master_data/)
pipeline run:
  extract-master   ->  2026/raw/master/{raw,clean}/
  bootstrap-raw    ->  2026/raw/details/xlsx/Sofascore_<id>.xlsx   (solo los que faltan)
  build-staging    ->  2026/staging/*_raw.parquet
  build-curated    ->  2026/curated/*.parquet           (11 tablas)
  build-warehouse  ->  warehouse/gronestats.duckdb
  validate         ->  2026/raw/runs/<run_id>/validation.json
  publish          ->  2026/{dashboard,fantasy}/{releases/<run_id>,current}
```

Cada fase y su esquema están en `gronestats/processing/pipeline.py` (`PHASES`, línea ~38) y `canonical_warehouse.py`. El detalle por partido son seis hojas: Team Stats, Player Stats, Average Positions, Shotmap, Match Momentum y Heatmaps.

## Cómo replicar para un torneo nuevo o una jornada

```powershell
py -3.11 -m gronestats.scripts.update_matchday --season 2026 --refresh-master --skip-sync --publish-target all
```

o, paso a paso, lo de la skill `update-matchday` (`.claude/skills/update-matchday/SKILL.md`). Resumen:

1. `data_loader_unprep -l "Liga 1 Peru" -y 2026 --skip-details` reescribe el master con **toda** la temporada (no filtra por torneo; hoy no hace falta).
2. `pipeline run --season 2026 --mode full --publish-target all` **sin** `--only-missing`.
3. Revisar `validation.json` y los conteos.

## Qué hubo que arreglar para que el scraper funcionara (2026-10)

El flujo documentado fallaba por completo, porque SofaScore endureció su protección:

| Problema | Síntoma | Solución |
|---|---|---|
| `api.sofascore.com` rechaza al navegador automatizado | `{"error":{"code":403,"reason":"Forbidden"}}`; ScraperFC lanza `KeyError: 'seasons'` | pedir `https://www.sofascore.com/api/v1/...` |
| Rutas con `/` final (ScraperFC las usa en `/seasons/`) | 403 | quitar la barra final (`api_path`) |
| Un Chrome nuevo por petición (el transporte original) | `403 challenge` tras unas peticiones | **una sola sesión** calentada en la home, `fetch` desde la página |
| `/seasons` rechaza `fetch` pero acepta navegación | `challenge` constante | alternativa: abrir la URL como página y leer el JSON |

Código: `gronestats/processing/sofascore_session.py` (nuevo), usado por `data_loader_unprep.py` y `optional_sheet_backfill.py`. Test: `tests/test_sofascore_session.py`. El navegador es visible (headless da 403); no cerrar la ventana mientras corre.

Otras correcciones:

- `gronestats/scripts/update_matchday.py`: nuevo `--refresh-master`; el paso final ya no usa `watch_parquets.py` (bucle infinito que dejaba el script colgado) sino `ingest_to_duckdb.py` y `sync_duckdb_to_postgres.py`.
- `gronestats/scripts/extract_matches.py`: usaba `ScraperFC.Sofascore()` sin parche y fallaba en silencio; ahora usa `build_sofascore_client()`.
- La skill `update-matchday` tenía tres errores: `--only-missing` no hace incremental ni refresca el master, el paso 3 omitía las columnas `match_url` y `tournament`, y la opción B bloqueaba.
- Test nuevo en `tests/test_fantasy_export.py`: el bundle conserva Apertura y Clausura con rondas repetidas y suma los totales del jugador entre torneos.

## Gotchas conocidos

- `--only-missing` en `extract-master` **no sobrescribe** `raw/master/clean/...limpio.xlsx` si existe: el Clausura no entra si lo usas tras refrescar el master.
- Mantén un único `.xlsx` en `raw/master/clean/` (`latest_master_clean_path` toma el más reciente).
- Un partido suspendido o pendiente aparece en el master sin marcador y `clean_scores` lo descarta del archivo `_limpio`; las rondas con 10 partidos incluyen reprogramados.
- `players_fantasy.price` se calcula con el total acumulado de **toda** la temporada (Apertura + Clausura), no por torneo.
- `0_Teams.xlsx` tiene 21 equipos; el torneo usa 18. Si sube un equipo nuevo hay que añadirlo ahí (`build_teams_curated`).
- `DEFAULT_SEASON_YEAR` del dashboard sigue en 2025 (`gronestats/dashboard/config.py:8`); `REGULAR_SEASON_MAX_ROUND = 20` alcanza (Apertura llega a la ronda 17).
- El test `test_validate_dataset_contract_allows_current_season_partial_sofascore` depende de que el año UTC sea 2026.
- Cada partido son ~35 llamadas a SofaScore (un heatmap por jugador): ~1 minuto por partido.

## Resultado de la corrida del 2026-10-22

_(se completa al terminar la corrida)_

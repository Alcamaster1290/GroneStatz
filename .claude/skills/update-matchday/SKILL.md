---
name: update-matchday
description: >
  Actualiza los datos de Liga 1 Peru 2026 (Apertura y Clausura): refresca la lista de
  partidos desde SofaScore, scrapea los detalles que faltan, corre el pipeline de GroneStats
  y publica los parquets. Invocable con /update-matchday.
---

# Update Matchday — Flujo de actualización post-jornada (Apertura + Clausura)

## Contexto del pipeline

Apertura y Clausura son torneos hijos de **la misma temporada 2026** en SofaScore
(unique-tournament `406`, season `"2026"`, id 88529). Viven juntos en todas las tablas:
la columna `tournament` vale `Liga 1, Apertura` o `Liga 1, Clausura`, y `round_number`
**reinicia en cada torneo** (la ronda 1 existe dos veces). La clave única de un partido es
`match_id`. No hay carpetas por torneo.

```
SofaScore (via ScraperFC + sesión de Chrome persistente)
  → data_loader_unprep        → gronestats/data/Liga 1 Peru/Partidos_Liga 1 Peru_2026{,_limpio}.xlsx
  → pipeline: extract-master  → 2026/raw/master/{raw,clean}/
  → pipeline: bootstrap-raw   → 2026/raw/details/xlsx/Sofascore_{match_id}.xlsx   (scrapea los que faltan)
  → pipeline: build-staging → build-curated → build-warehouse → validate → publish
  → 2026/{dashboard,fantasy}/current/*.parquet   (releases anteriores quedan en .../releases/)
```

Usar siempre **Python 3.11** (`py -3.11`): es el único con ScraperFC, botasaurus y duckdb.

## Camino recomendado (un solo comando)

```powershell
py -3.11 -m gronestats.scripts.update_matchday --season 2026 --refresh-master --skip-sync --publish-target all
```

Hace, en orden: (0) refresca el master de toda la temporada, (2) corre el pipeline **sin**
`--only-missing`, que es lo que hace entrar partidos nuevos. `bootstrap-raw` scrapea solo los
workbooks que no existen. Con `--refresh-master` se omite `extract_matches` (redundante).

`--skip-extract` solo omite `extract_matches`: el pipeline sigue scrapeando todo workbook que falte en `bootstrap-raw`. Para reprocesar lo ya descargado **sin tocar SofaScore** (por ejemplo tras refrescar el master, cuando faltan muchos detalles), ejecutar el pipeline directamente con `--no-scrape`:

```powershell
py -3.11 -m gronestats.processing.pipeline run --league "Liga 1 Peru" --season 2026 --mode full --publish-target all --no-scrape
```

`--no-scrape` omite la llamada al scraper y no borra los workbooks incompletos; los partidos sin detalle quedan como advertencias de validación.

## Scrapeo por tandas con parada ante bloqueos (recomendado)

`gronestats.processing.sofascore_batches` pide a SofaScore por tandas pequeñas y se detiene solo ante el primer bloqueo (cualquier error que no sea un 404; un 404 es dato ausente en origen). Cada partido queda en `<temporada>/raw/scrape_ledger.jsonl` y todo es reanudable. Para una jornada nueva, **después de refrescar el master**:

```powershell
py -3.11 -m gronestats.processing.sofascore_batches details  --season 2026   # 7 llamadas por partido, sin heatmaps
py -3.11 -m gronestats.processing.sofascore_batches heatmaps --season 2026   # ~41 llamadas por partido, tandas de 3 con pausa de 45 s
py -3.11 -m gronestats.processing.sofascore_batches momentum --season 2026   # 1 llamada por partido (un 404 queda como «vacío»)
py -3.11 -m gronestats.processing.sofascore_batches team-stats|average-positions|shotmap --season 2026   # solo si el pipeline avisa que falta alguna hoja; una llamada por partido
py -3.11 -m gronestats.processing.sofascore_batches lineups --season 2026   # formación declarada y 11 titulares de cada partido (una llamada por partido) -> raw/lineups.jsonl
py -3.11 -m gronestats.analysis.formations --out docs/recursos-dashboard/datos-de-apoyo/formaciones   # cruza la formación declarada con las posiciones de los titulares
py -3.11 -m gronestats.processing.pipeline run --league "Liga 1 Peru" --season 2026 --mode full --publish-target all --no-scrape
```

- Añadir `--dry-run` para ver el plan sin llamar a SofaScore y `--limit N` para probar con pocos partidos.
- `details` solo pide partidos **sin workbook** (uno incompleto no se vuelve a pedir ni se borra) y omite los que el listado no marca como `finished`.
- 2022 y 2023 no tienen maestro propio: `fixtures --season 2022` baja el listado (fecha, estado y estadio, ~13 llamadas) y `apply-fixtures` lo vuelca en `0_Matches.xlsx` sin red. No usar las coordenadas de sede de SofaScore: algunas vienen con latitud y longitud invertidas.

## Pasos manuales equivalentes

1. **Refrescar el master** (trae Apertura y Clausura completos, no filtra por torneo):
   ```powershell
   py -3.11 -m gronestats.processing.data_loader_unprep -l "Liga 1 Peru" -y 2026 --skip-details
   ```
   Pasar siempre `-y 2026` (el valor por defecto es 2024). Revisar el resultado: valores de
   `tournament`, rango de `round_number` por torneo, `match_id` sin duplicados, partidos sin
   marcador (suspendidos o pendientes).
2. **Pipeline** — sin `--only-missing`:
   ```powershell
   py -3.11 -m gronestats.processing.pipeline run --league "Liga 1 Peru" --season 2026 --mode full --publish-target all
   ```
   - `--only-missing` **no** pisa `raw/master/clean/...limpio.xlsx` si ya existe, así que los
     partidos nuevos del master no entrarían. Úsalo solo si el master no cambió.
   - `--only-missing` tampoco hace el proceso incremental; para eso es `--mode incremental`.
   - Deja un solo `.xlsx` en `raw/master/clean/` (`latest_master_clean_path` toma el más reciente).
3. **Hojas opcionales** (shotmap, momentum, heatmaps) si el run las reporta como warnings:
   `gronestats/processing/backfill_optional_sheets.py` (ver `docs/gronestats/shotmap_momentum_backfill.md`).
4. **Verificar** `2026/raw/runs/<run_id>/validation.json` (`status: passed`, sin `blocking_errors`).

## Sincronizar con la app Fantasy (opcional)

La app de producción está caída (ver `docs/fantasy/RUNBOOK_RECUPERACION.md`). Si hay backend
disponible, los pasos son one-shot, **no** usar `watch_parquets.py` (es un bucle infinito):

```powershell
python FantasyL1-2026\scripts\ingest_to_duckdb.py
python FantasyL1-2026\scripts\sync_duckdb_to_postgres.py
```

Con `SYNC_SKIP_PRUNE_MISSING_PLAYERS=true`, `SYNC_PRESERVE_EXISTING_PRICE_CURRENT=true` y
`SYNC_PRESERVE_EXISTING_BASE_STATS=true`. La app aún asume una sola temporada por año: el
Clausura no está soportado allí (ver el apéndice del runbook).

## Notas importantes

- **SofaScore bloquea clientes automatizados** (`403 Forbidden` / `403 challenge`): rechaza
  `api.sofascore.com`, las rutas con `/` final y un navegador nuevo por petición. El transporte
  `gronestats/processing/sofascore_session.py` mantiene **una sesión de Chrome visible** (se abre
  una ventana; no cerrarla), la calienta en www.sofascore.com y consulta `/api/v1/...` con
  `fetch`. Reintenta y recalienta ante `challenge`. Variables: `GRONESTATS_SOFASCORE_HEADLESS`,
  `GRONESTATS_SOFASCORE_ATTEMPTS`, `GRONESTATS_SOFASCORE_MIN_INTERVAL`.
- Nunca usar `ScraperFC.Sofascore()` crudo ni `extract_matches.py` sin ese transporte: sin él
  fallan en silencio y generan workbooks vacíos (el scraper borra los menores de 15 KB).
- Un partido nuevo solo se scrapea si el master tiene `match_url` (lo trae el refresco).
- Cada partido son ~35 llamadas (incluye un heatmap por jugador): contar varios minutos por
  jornada completa. Es reanudable: lo ya scrapeado se omite.
- `validate` es estricto con las temporadas pasadas y laxo con la actual (modo parcial); desde
  2027 la temporada 2026 pasará a ser estricta.
- Releases publicados: `2026/{dashboard,fantasy}/releases/<run_id>`; `current` se intercambia de
  forma atómica, por lo que volver atrás es reapuntar a un release anterior.

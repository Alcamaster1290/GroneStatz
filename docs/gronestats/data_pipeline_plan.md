# Plan de Pipeline de Datos para GroneStatz

## Objetivo

Pasar de un flujo parcialmente manual basado en notebooks y utilidades Streamlit a un pipeline reproducible, incremental y validable que garantice que el dashboard final siempre consuma un dataset consistente.

El proveedor operativo sigue siendo SofaScore, aunque varios conceptos y coordenadas vienen con semantica tipo Opta. Por eso el pipeline debe:

- preservar el dato crudo tal como llega de SofaScore;
- estandarizar columnas y tipos en una capa intermedia;
- publicar una capa curada estable para el dashboard;
- registrar calidad, cobertura y fecha de actualizacion por corrida.

## Flujo actual

### 1. Extraccion de calendario y maestro

Hoy el flujo existe en los notebooks `nb_01` y `nb_02`, y ya esta parcialmente automatizado en [data_loader_unprep.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/data_loader_unprep.py).

Salida actual:

- `gronestats/data/{liga}/Partidos_{liga}_{year}.xlsx`
- `gronestats/data/{liga}/Partidos_{liga}_{year}_limpio.xlsx`
- `gronestats/data/master_data/Partidos_{liga}_{year}_limpio.xlsx`

### 2. Extraccion de detalle por partido

Hoy el flujo vive en `nb_03` y tambien en [data_loader_unprep.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/data_loader_unprep.py).

Salida actual por partido:

- `gronestats/data/Liga 1 Peru/2025/Sofascore_{match_id}.xlsx`

Hojas relevantes:

- `Team Stats`
- `Player Stats`
- `Average Positions`
- `Shotmap`
- `Match Momentum`
- `Heatmaps`

### 3. Construccion de parquets base

Hoy este paso depende de [st_create_parquets.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/st_create_parquets.py), que mezcla logica de transformacion con UI Streamlit y exporta via boton.

Salida actual:

- `matches.parquet`
- `teams.parquet`
- `players.parquet`
- `player_match.parquet`
- `player_totals.parquet`
- `players_fantasy.parquet`
- `player_team.parquet`
- `player_transfer.parquet`
- `team_stats.parquet`

### 4. Normalizacion para dashboard

Hoy este paso vive en [normalize_parquets.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/normalize_parquets.py).

Salida actual:

- `gronestats/data/Liga 1 Peru/2025/parquets/normalized/*.parquet`

### 5. Construccion de capas posicionales

Hoy este paso vive en [build_positional_parquets.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/build_positional_parquets.py).

Salida actual:

- `average_positions.parquet`
- `heatmap_points.parquet`

### 6. Consumo final del dashboard

El dashboard consume directamente [config.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/dashboard/config.py) y [data.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/dashboard/data.py) desde:

- `gronestats/data/Liga 1 Peru/2025/parquets/normalized`

## Problemas detectados

### Problema 1. La logica productiva esta repartida entre notebooks, scripts y una app Streamlit de transformacion

Eso dificulta reproducibilidad, ejecucion desatendida e incrementalidad.

### Problema 2. No existe una frontera clara entre raw, staging y curated

Hoy conviven:

- maestro limpio en Excel;
- cientos de workbooks `Sofascore_{match_id}.xlsx`;
- parquets base;
- parquets normalizados para dashboard.

La separacion funcional existe, pero no esta explicitada como contrato de pipeline.

### Problema 3. La exportacion de parquets base depende de accion manual

`st_create_parquets.py` contiene la logica central, pero esta acoplada a una UI. Eso no es ideal para correr desde tarea programada o CI.

### Problema 4. Riesgo de desalineacion temporal entre artefactos

En el estado actual, `matches.parquet` fue actualizado el `23/03/2026`, mientras varios parquets base como `players.parquet`, `player_match.parquet` y `team_stats.parquet` siguen con fecha `21/01/2026`. Eso indica que el pipeline puede quedar parcialmente refrescado.

### Problema 5. Faltan validaciones de cobertura

No hay una puerta explicita que asegure, por ejemplo:

- que cada `match_id` del maestro limpio tenga workbook detalle;
- que cada workbook tenga hojas minimas;
- que `player_match` y `team_stats` cubran el mismo universo de partidos que `matches`;
- que `average_positions` y `heatmap_points` reflejen cobertura real y no silencios.

### Problema 6. El dashboard recompone metricas porque no confia del todo en algunas capas

En [data.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/dashboard/data.py) se descarta `player_totals` para el dashboard regular-season y se recalcula a partir de `player_match`. Eso es una señal correcta: la capa curada todavia no esta modelada con un contrato orientado a dashboard.

## Arquitectura objetivo

La organizacion recomendada es de 4 capas.

### Capa A. Raw ingest

Responsabilidad:

- guardar exactamente lo extraido de SofaScore;
- no reinterpretar semantica;
- permitir reingestion y auditoria.

Artefactos propuestos:

- `gronestats/data/sofascore/2025/master/raw/partidos.xlsx`
- `gronestats/data/sofascore/2025/master/clean/partidos_limpio.xlsx`
- `gronestats/data/sofascore/2025/details/xlsx/Sofascore_{match_id}.xlsx`
- `gronestats/data/sofascore/2025/runs/ingest_manifest.jsonl`

Campos extra recomendados en el manifest:

- `run_id`
- `provider`
- `season`
- `match_id`
- `source_url`
- `scraped_at`
- `status`
- `file_size_kb`
- `missing_sheets`

### Capa B. Staging

Responsabilidad:

- aplanar workbooks y tipar columnas;
- preservar nombres crudos y tambien aliases estables;
- agregar metadatos tecnicos de procedencia.

Artefactos propuestos:

- `matches_raw.parquet`
- `team_stats_raw.parquet`
- `player_stats_raw.parquet`
- `average_positions_raw.parquet`
- `heatmaps_raw.parquet`
- `shotmap_raw.parquet`
- `momentum_raw.parquet`

Columnas tecnicas obligatorias en toda tabla staging:

- `provider`
- `season`
- `match_id`
- `source_file`
- `source_sheet`
- `ingested_at`
- `run_id`

### Capa C. Curated domain

Responsabilidad:

- convertir staging en entidades estables del dominio GroneStatz;
- aplicar reglas de limpieza y normalizacion;
- dejar contratos listos para el dashboard y para otros consumidores.

Artefactos propuestos:

- `matches.parquet`
- `teams.parquet`
- `players.parquet`
- `player_match.parquet`
- `team_stats.parquet`
- `average_positions.parquet`
- `heatmap_points.parquet`
- `shot_events.parquet`
- `match_momentum.parquet`
- `player_identity.parquet`
- `data_quality_report.json`

Notas:

- `shot_events.parquet` y `match_momentum.parquet` no son obligatorios para el dashboard actual, pero deben existir como capa lista para futuras vistas.
- `player_totals.parquet` no deberia ser una fuente primaria del dashboard; debe ser un derivado de `player_match`.

### Capa D. Dashboard mart

Responsabilidad:

- publicar solo lo que el dashboard necesita;
- garantizar consistencia de corte temporal;
- facilitar rollback.

Artefactos propuestos:

- `gronestats/data/Liga 1 Peru/2025/dashboard/current/*.parquet`
- `gronestats/data/Liga 1 Peru/2025/dashboard/releases/{release_id}/*.parquet`

Contrato:

- el dashboard solo lee `dashboard/current`;
- la publicacion a `current` solo ocurre si las validaciones de calidad pasaron.

## Contratos de datos recomendados

### Contrato 1. `matches`

Debe ser la tabla eje.

Columnas minimas:

- `match_id`
- `season`
- `tournament`
- `round_number`
- `home_id`
- `away_id`
- `home`
- `away`
- `home_score`
- `away_score`
- `fecha`
- `fecha_dt`
- `status`
- `source_provider`
- `last_updated_at`

### Contrato 2. `player_match`

Una fila por jugador por partido.

Columnas minimas:

- `match_id`
- `player_id`
- `team_id`
- `name`
- `position`
- `minutesplayed`
- `goals`
- `assists`
- `saves`
- `fouls`
- `yellowcards`
- `redcards`
- `penaltywon`
- `penaltysave`
- `penaltyconceded`
- `rating`
- `source_provider`

Regla:

- `player_totals` se deriva siempre desde aqui.

### Contrato 3. `team_stats`

Una fila por `KEY` estadistico y partido.

Columnas minimas:

- `match_id`
- `GROUP`
- `KEY`
- `name`
- `HOMEVALUE`
- `AWAYVALUE`
- `HOMETOTAL`
- `AWAYTOTAL`
- `RENDERTYPE`
- `source_provider`

Regla:

- no renombrar agresivamente `KEY`;
- preservar el valor crudo para no perder semantica SofaScore/Opta.

### Contrato 4. `average_positions`

Una fila por jugador y partido.

Columnas minimas:

- `match_id`
- `player_id`
- `team_id`
- `team_name`
- `name`
- `position`
- `shirt_number`
- `average_x`
- `average_y`
- `points_count`
- `is_starter`

### Contrato 5. `heatmap_points`

Una fila por punto de calor.

Columnas minimas:

- `match_id`
- `player_id`
- `team_id`
- `team_name`
- `name`
- `x`
- `y`

## Orquestacion recomendada

La recomendacion es un entrypoint unico por CLI, no por notebook ni por Streamlit.

Ejemplo:

```text
python -m gronestats.processing.pipeline run --league "Liga 1 Peru" --season 2025 --stage all
```

Substages sugeridos:

1. `extract-master`
2. `extract-details`
3. `build-staging`
4. `build-curated`
5. `build-dashboard`
6. `validate`
7. `publish`

Opciones utiles:

- `--only-missing`
- `--since-round`
- `--since-match-id`
- `--force`
- `--skip-scrape`
- `--dry-run`

## Validaciones obligatorias antes de publicar

### Cobertura

- todo `match_id` en maestro limpio debe existir en `matches.parquet`;
- todo `match_id` finalizado debe tener workbook detalle o quedar en reporte de faltantes;
- `player_match`, `team_stats`, `average_positions` y `heatmap_points` deben reportar cobertura por partido.

### Integridad referencial

- todo `player_match.match_id` debe existir en `matches.match_id`;
- todo `player_match.team_id` debe existir en `teams.team_id` o quedar marcado como excepcion;
- todo `average_positions.player_id` debe existir en `players.player_id` o en `player_match.player_id`.

### Calidad semantica

- `home_id != away_id`;
- `home_score` y `away_score` no negativos;
- `average_x`, `average_y`, `x`, `y` dentro del rango esperado del proveedor;
- `minutesplayed` entre 0 y 130;
- `position` dentro del set esperado o marcado como raw fallback.

### Frescura

- todos los parquets publicados en una release deben compartir el mismo `release_id`;
- no se publica si `matches` fue reconstruido pero `player_match` no.

## Propuesta de reorganizacion de codigo

### Mantener

- [data_loader_unprep.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/data_loader_unprep.py) como base de scraping incremental;
- [normalize_parquets.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/normalize_parquets.py) como referencia de tipado;
- [build_positional_parquets.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/build_positional_parquets.py) como transformacion especializada.

### Refactorizar

- extraer de [st_create_parquets.py](/abs/path/c:/Users/Alvaro/Proyectos/Proyecto%20Gronestats/GroneStatz/gronestats/processing/st_create_parquets.py) toda la logica de transformacion hacia modulos puros sin Streamlit;
- dejar `st_create_parquets.py` solo como visor o eliminarlo de la ruta productiva.

### Crear

- `gronestats/processing/pipeline.py`
- `gronestats/processing/jobs/extract_master.py`
- `gronestats/processing/jobs/extract_details.py`
- `gronestats/processing/jobs/build_staging.py`
- `gronestats/processing/jobs/build_curated.py`
- `gronestats/processing/jobs/build_dashboard.py`
- `gronestats/processing/jobs/validate_release.py`
- `gronestats/processing/contracts.py`

## Flujo recomendado de ejecucion

### Corrida completa

1. extraer maestro anual;
2. scrapear detalles faltantes;
3. aplanar workbooks a staging parquet;
4. construir curated parquet;
5. construir dashboard release;
6. ejecutar validaciones;
7. publicar `dashboard/current`.

### Corrida incremental diaria

1. refrescar maestro;
2. detectar `match_id` nuevos o actualizados;
3. scrapear solo faltantes o partidos recientes;
4. reconstruir staging solo de esos partidos;
5. regenerar curated afectado;
6. regenerar dashboard release;
7. validar y publicar.

## Automatizacion recomendada

Por la naturaleza del scraping de SofaScore, la opcion mas pragmatica no es GitHub-hosted CI sino:

- `Task Scheduler` en Windows si el scraping se corre en tu maquina;
- o un self-hosted runner si luego quieres CI real.

Frecuencia sugerida:

- maestro: 1 vez al dia;
- detalles: cada 2 a 4 horas en fechas de jornada;
- publicacion dashboard: despues de pasar validaciones.

## Roadmap de implementacion

### Fase 1. Consolidar la ruta productiva

- mover la logica de `st_create_parquets.py` a funciones puras;
- crear CLI unica `pipeline.py`;
- dejar notebooks como exploratorios, no productivos.

### Fase 2. Agregar staging y manifests

- aplanar cada workbook a tablas staging;
- agregar `run_id`, `source_file`, `source_sheet`, `ingested_at`;
- guardar reportes de cobertura.

### Fase 3. Publicacion transaccional del dashboard

- generar release en carpeta versionada;
- validar;
- hacer switch atomico a `dashboard/current`.

### Fase 4. Observabilidad

- reporte HTML o JSON de calidad;
- conteo de partidos faltantes;
- diferencias entre corrida anterior y actual.

## Decision practica para GroneStatz

La mejor decision inmediata no es reescribir todo, sino formalizar el pipeline existente en esta secuencia:

1. usar `data_loader_unprep.py` como extractor oficial;
2. sacar de `st_create_parquets.py` la transformacion a un builder CLI;
3. mantener `normalize_parquets.py` y `build_positional_parquets.py` como etapas separadas;
4. publicar el dashboard solo desde una carpeta `dashboard/current` generada por release.

Con eso eliminas el mayor riesgo actual: que el dashboard lea una mezcla de artefactos generados en fechas distintas.

## Siguiente implementacion recomendada

El siguiente paso concreto deberia ser:

1. crear `pipeline.py` como orquestador;
2. extraer de `st_create_parquets.py` las funciones puras a `jobs/build_curated.py`;
3. agregar `validate_release.py` con chequeos de cobertura e integridad;
4. hacer que el dashboard lea `dashboard/current` en lugar de `parquets/normalized` directo.

# GroneStats web v1: plan de implementación

> **Para quien ejecute:** usar `superpowers:executing-plans` (ejecución en la misma sesión). Los pasos usan casillas `- [ ]`.

**Meta:** que `python -m gronestats.api` y `npm run dev` en `web/` muestren en el navegador local la v1 del diseño `docs/superpowers/specs/2026-11-26-gronestats-web-design.md`, con los datos reales de 2022-2026.

**Arquitectura:** un constructor de bundle (`gronestats/web_bundle`) junta los bundles publicados por temporada con las salidas de análisis (xG, importancia, probabilidad, formaciones, tablas oficiales) en un release de parquet entre temporadas, con esquema y manifiesto. Una API FastAPI de solo lectura sirve ese release con DuckDB. Una app Next.js 14 (`web/`) renderiza en el servidor, con SVG sin librerías de gráficos.

**Tecnología:** Python 3.11 (pandas, pyarrow, duckdb, FastAPI, uvicorn), Node 22, Next.js 14.2, React 18, TypeScript 5.5, Tailwind 3.4, Jest.

## Alcance de esta entrega

**Entra:** bundle `web` con esquema y validación; API con los endpoints de Liga, Equipo, Jugador, Partido y Estado; web con las páginas `/liga`, `/equipos`, `/jugadores`, `/partidos` y `/estado`; pruebas de Python y de las utilidades de la web; arranque local.

**No entra todavía (queda como «próximamente» en pantalla o en el plan siguiente):**
- La fase `build-analytics` dentro del pipeline: el constructor lee las salidas de análisis ya generadas (`docs/recursos-dashboard/datos-de-apoyo/`), no las recalcula.
- Tablas de la ficha que aún no existen como código: `player_percentiles`, `player_similarity`, `heatmap_density`, `teammate_synergy`, `team_match_style`. En su lugar el heatmap se agrega en la API y las pestañas Estilo, Contextos y Compañeros muestran «próximamente».
- Tarjetas Open Graph, despliegue (Compose, Caddy, rsync), `scripts/check` y pre-push, Playwright, `mypy`/`ruff`.
- Standings por fecha con sanciones: los ajustes oficiales se aplican solo a la última fecha de cada torneo.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `gronestats/web_bundle/schema.py` | contrato: tablas, columnas, claves y `SCHEMA_VERSION` |
| `gronestats/web_bundle/validate.py` | `validate_bundle(dir)`: tablas, columnas y claves únicas |
| `gronestats/web_bundle/build.py` | `build_web_bundle(...)` y CLI `python -m gronestats.web_bundle.build` |
| `gronestats/data/Liga 1 Peru/known_gaps.csv` | huecos permanentes explicados (versionado) |
| `gronestats/api/store.py` | `Release`: DuckDB en memoria con vistas sobre los parquet de `current` |
| `gronestats/api/queries.py` | una función por endpoint; devuelve diccionarios |
| `gronestats/api/app.py` | `create_app()`, rutas, recarga interna, archivos estáticos de imágenes |
| `gronestats/api/__main__.py` | `python -m gronestats.api` (uvicorn en 127.0.0.1:8000) |
| `tests/fixtures/web_inputs.py` | genera entradas sintéticas (bundles por temporada y salidas de análisis) |
| `tests/test_web_bundle.py`, `tests/test_api.py` | pruebas del constructor y de la API sobre el bundle de juguete |
| `web/lib/api.ts`, `web/lib/format.ts`, `web/lib/pitch.ts` | cliente de la API, formato y geometría de la cancha |
| `web/components/*.tsx` | `Crest`, `PlayerPhoto`, `StandingsTable`, `TitleChart`, `MatchStrip`, `ShotMap`, `Heatmap`, `Header` |
| `web/app/**/page.tsx` | páginas de servidor |
| `scripts/smoke_web.py` | comprueba que cada página responde 200 y trae su contenido clave |

## Contratos

**Bundle** (`SCHEMA_VERSION = "1.0.0"`; `tournament` ∈ `Apertura`, `Clausura`, `Acumulada`):

| Tabla | Clave | Columnas |
|---|---|---|
| `matches` | match_id | season, tournament, round_number, match_id, status, home_id, away_id, home_score, away_score, date, estadio, ciudad, arbitro |
| `teams` | team_id | team_id, name, full_name, color, level, stadium, department, region |
| `players` | player_id | player_id, name, short_name, position, team_id, photo |
| `player_match` | season, match_id, player_id | season, match_id, player_id, team_id, position, minutesplayed, goals, assists, yellowcards, redcards, saves, rating |
| `shot_events` | season, match_id, shot_id | season, match_id, shot_id, player_id, team_id, is_home, shot_type, situation, body_part, minute, x, y, is_goal, xg |
| `heatmap_points` | (sin clave) | season, match_id, player_id, team_id, x, y |
| `lineups` | season, match_id, side | season, match_id, side, team_id, formation, expected, counted, consistent, defenders_ok |
| `match_importance` | season, match_id, team_id | season, tournament, match_id, round_number, team_id, matches_before, points_before, matches_remaining, threshold_used, points_needed, lives, band, band_name |
| `title_probability` | season, tournament, team_id, k | season, tournament, match_id, team_id, k, p_title, points, rating |
| `standings` | season, tournament, round_number, team_id | season, tournament, round_number, team_id, pos, pj, pg, pe, pp, gf, gc, dg, pts |
| `venues` | estadio, ciudad | estadio, ciudad, altitud_msnm, precision, fuente |
| `model_runs` | model, version | model, version, trained_on, params, metrics |
| `data_coverage` | season, kind | season, kind, expected, present, missing |
| `known_gaps` | (sin clave) | season, kind, scope, reason, source |
| `release_log` | release_id | release_id, built_at, matches, data_as_of |

`manifest.json`: `release_id`, `schema_version`, `built_at`, `data_as_of`, `tables` (filas por tabla), `ledger` (intentos de scrapeo por modo y estado, por temporada) y `models`.

**API** (`/v1`, JSON; toda respuesta lleva `release_id`):
- `GET /release`, `GET /status`, `GET /seasons`, `GET /teams?season=`
- `GET /seasons/{s}/standings?tournament=&round=`
- `GET /teams/{id}/seasons/{s}/matches`, `GET /teams/{id}/seasons/{s}/title-race?tournament=`, `GET /teams/{id}/seasons/{s}/players`
- `GET /matches/{id}`, `GET /players/{id}?season=`, `GET /players/{id}/shots?season=`, `GET /players/{id}/heatmap?season=`
- `POST /internal/reload` (solo desde localhost), `GET /assets/players/{archivo}` y `GET /assets/teams/{archivo}`

**Coordenadas (verificadas, `coordenadas-y-orientacion.md`):** en `shot_events`, `x` es la distancia a la línea de fondo del arco que se ataca (0 = línea de gol) y vale igual para local y visita; `y` va de 0 a 100 centrado en 50. En `heatmap_points`, `x` va en dirección de ataque (0 = arco propio, 100 = arco rival).

---

### Tarea 1: dependencias y esquema del bundle

**Archivos:** crear `gronestats/web_bundle/__init__.py`, `schema.py`, `validate.py`, `requirements-web.txt`; probar en `tests/test_web_bundle.py`.

- [ ] **Paso 1:** instalar `fastapi` y `uvicorn` con `py -3.11 -m pip install fastapi uvicorn` y anotarlos en `requirements-web.txt` junto a `duckdb`, `pandas`, `pyarrow`, `httpx`.
- [ ] **Paso 2:** escribir en `tests/test_web_bundle.py` pruebas de `validate_bundle`: un bundle sin una tabla falla con su nombre; una columna faltante falla con su nombre; una clave duplicada falla; un bundle correcto devuelve lista vacía de errores.
- [ ] **Paso 3:** ejecutar `py -3.11 -m pytest tests/test_web_bundle.py -q`; debe fallar por importación.
- [ ] **Paso 4:** implementar `schema.py` (`SCHEMA_VERSION`, `TABLES: dict[str, TableSpec]` con `columns` y `key`) y `validate.py` (`validate_bundle(path) -> list[str]`).
- [ ] **Paso 5:** ejecutar las pruebas; deben pasar. Commit `feat(web-bundle): schema and validation`.

### Tarea 2: constructor del bundle

**Archivos:** crear `gronestats/web_bundle/build.py`, `tests/fixtures/web_inputs.py`, `gronestats/data/Liga 1 Peru/known_gaps.csv`; ampliar `tests/test_web_bundle.py`; añadir `gronestats/data/Liga 1 Peru/web/` a `.gitignore`.

- [ ] **Paso 1:** en `tests/fixtures/web_inputs.py`, `make_web_inputs(root) -> WebInputs` crea dos temporadas sintéticas (4 equipos, 6 partidos por torneo, tiros, heatmap, momentum, estadísticas) y las salidas de análisis con las columnas reales, y devuelve las rutas.
- [ ] **Paso 2:** pruebas del constructor sobre esas entradas: el release pasa `validate_bundle`; `matches.tournament` solo trae `Apertura` y `Clausura`; `teams.level` queda completo aunque la temporada original no lo traiga; `standings` trae una fila por equipo y fecha y el último `pts` coincide con la suma de los partidos; `shot_events.xg` no es nulo; `data_coverage` cuenta partidos esperados y presentes; el manifiesto trae `schema_version`.
- [ ] **Paso 3:** ejecutar; deben fallar.
- [ ] **Paso 4:** implementar `build_web_bundle(data_dir, analytics_dir, reference_dir, out_dir, seasons)` y el CLI (`--data-dir`, `--analytics-dir`, `--reference-dir`, `--out`). Escribe `releases/<release_id>/` y cambia `current` (copia atómica: escribe en `current.tmp` y renombra).
- [ ] **Paso 5:** crear `known_gaps.csv` con los huecos ya documentados (6 administrativos del Apertura 2023, Clausura 2023 sin los 2 cruces de Municipal, 5 anulados de Binacional en el Clausura 2025, 33 partidos de ADT Tarma sin estadio, 20 alineaciones con 10 titulares, momentum que SofaScore no trae).
- [ ] **Paso 6:** ejecutar las pruebas; deben pasar. Construir el release real con `py -3.11 -m gronestats.web_bundle.build --out "gronestats/data/Liga 1 Peru/web"` y validar con `validate_bundle`. Commit `feat(web-bundle): build a cross-season release`.

### Tarea 3: API

**Archivos:** crear `gronestats/api/{__init__,store,queries,app,__main__}.py`, `tests/test_api.py`.

- [ ] **Paso 1:** pruebas con `fastapi.testclient.TestClient` sobre el bundle de juguete (`create_app(bundle_dir=..., images_dir=...)`): `/v1/release` trae `release_id` y `schema_version`; `/v1/seasons/2026/standings?tournament=Apertura` viene ordenada por `pos` y trae nombre y color; `/v1/teams/{id}/seasons/{s}/matches` trae resultado, rival con su nivel, altitud, formación con `defenders_ok`, importancia y probabilidad antes y después; `/v1/players/{id}` con una temporada sin datos devuelve `null` y `missing_reason` en vez de ceros; un id desconocido devuelve 404; `/internal/reload` responde 403 si no viene de localhost; un release inválido deja el anterior.
- [ ] **Paso 2:** ejecutar; deben fallar.
- [ ] **Paso 3:** implementar `store.Release` (vistas DuckDB sobre `current/*.parquet`, `reload()` atómico que valida versión mayor del esquema), `queries.py` y `app.py`.
- [ ] **Paso 4:** ejecutar las pruebas; deben pasar. Arrancar contra el release real y comprobar a mano `/v1/release`, `/v1/seasons/2026/standings?tournament=Clausura` y `/v1/teams/2311/seasons/2026/matches` con `curl`. Commit `feat(api): read-only FastAPI over the web release`.

### Tarea 4: web, base y utilidades

**Archivos:** crear `web/` (`package.json`, `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts`, `postcss.config.mjs`, `jest.config.js`, `app/layout.tsx`, `app/globals.css`, `lib/api.ts`, `lib/format.ts`, `lib/pitch.ts`, `lib/format.test.ts`, `lib/pitch.test.ts`, `components/Header.tsx`).

- [ ] **Paso 1:** `npm create`-equivalente a mano (sin plantilla interactiva) con las versiones fijadas del stack; `npm install`.
- [ ] **Paso 2:** pruebas Jest de `format.ts` (porcentaje con coma decimal, fecha en hora de Lima, `slug`/`idFromSlug`) y de `pitch.ts` (un tiro con `x` = 11,5 e `y` = 50 cae sobre el punto de penal; el heatmap mantiene la dirección de ataque).
- [ ] **Paso 3:** ejecutar `npm test`; deben fallar.
- [ ] **Paso 4:** implementar las utilidades, el cliente de la API (`getJson` con `next: { tags: ["release"] }`) y el diseño base con tokens claro/oscuro y el pie con el release.
- [ ] **Paso 5:** `npm test` y `npm run build` limpios. Commit `feat(web): Next.js app skeleton and utilities`.

### Tarea 5: web, componentes y páginas

**Archivos:** crear `web/components/{Crest,PlayerPhoto,StandingsTable,TitleChart,MatchStrip,ShotMap,Heatmap}.tsx` y `web/app/{page.tsx,liga/[season]/[tournament]/page.tsx,equipos/[slug]/page.tsx,jugadores/[slug]/page.tsx,partidos/[id]/page.tsx,estado/page.tsx,not-found.tsx}`.

- [ ] **Paso 1:** componentes de servidor con SVG: tabla de posiciones, curvas de probabilidad (una línea por equipo, el elegido resaltado), tira partido a partido (fecha, rival con su nivel en texto, local o visita, altitud en metros, resultado, formación con ⚠ solo si `defenders_ok` es falso, importancia con «n=» y asterisco si se usó el piso de 37), mapa de tiros (media cancha, tamaño según xG) y heatmap en cuadrícula.
- [ ] **Paso 2:** páginas: Liga (tabla y curvas, selector de torneo), Equipo (cabecera con escudo y color, curva, tira, plantel con fotos), Jugador (foto con dorsal de respaldo, totales y tabla por temporada, mapa de tiros, heatmap, paneles «próximamente»), Partido (marcador, formaciones, tiros de ambos equipos, importancia) y Estado (release, cobertura con huecos explicados, modelos).
- [ ] **Paso 3:** `npm run build` limpio. Commit `feat(web): league, team, player, match and status pages`.

### Tarea 6: arranque local y verificación

**Archivos:** crear `scripts/dev_web.py` (arranca API y web), `scripts/smoke_web.py`, `web/README.md`.

- [ ] **Paso 1:** `scripts/smoke_web.py` pide cada página con datos reales (liga 2026 Clausura, un equipo, un jugador con foto, un jugador sin foto, un partido, `/estado`) y comprueba estado 200 y un texto clave.
- [ ] **Paso 2:** arrancar API y web, ejecutar el smoke y revisar capturas (Edge headless) de cada pantalla en claro y en oscuro; corregir lo que salga mal.
- [ ] **Paso 3:** actualizar el estado del spec y la memoria; commit `docs: run instructions and verification`; empujar la rama `feat/web-v1`.

## Revisión contra el spec

- Sección 1 (flujo): el constructor lee salidas de análisis ya generadas; la fase `build-analytics` queda para el plan siguiente.
- Sección 2 (contrato): cubierto salvo las cinco tablas de la ficha aún sin código.
- Sección 3 (API): cubierto salvo `style`, `contexts` y `teammates`.
- Sección 4 (web): cubierto salvo tarjetas OG y revalidación por etiqueta desde el despliegue (el cliente ya etiqueta las peticiones).
- Sección 5 (entrega) y la parte de CI de la 7: fuera de esta entrega.
- Sección 6 (monitor): `data_coverage`, `known_gaps`, `release_log`, `/v1/status` y `/estado`; sin `stale` con umbral (se devuelve `data_as_of`).

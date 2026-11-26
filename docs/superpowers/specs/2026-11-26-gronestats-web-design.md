# GroneStats web: diseño

**Estado:** borrador. Secciones 1 a 3 aprobadas por Alvaro (2026-11-26); sección 4 presentada, a la espera de su OK; secciones 5 a 7 pendientes. Reemplaza el borrador de octubre (`2026-10-26-reingenieria-gronestats-borrador.md`).

## Alcance y decisiones previas

- **v1 es solo análisis:** sin cuentas ni Fantasy (Fantasy se enchufará después como módulo).
- **Backend sin estado:** FastAPI y DuckDB de solo lectura sobre un bundle de servicio.
- **Frontend:** Next.js con SSR (SEO y tarjetas para compartir en X y YouTube), sin Capacitor.
- **Entrega:** VPS con Docker Compose, Caddy y Cloudflare delante; los datos llegan por rsync/SSH tras cada jornada y `current` cambia de forma atómica. Vercel solo para previews.
- **Datos híbridos:** el pipeline, en la PC de Alvaro, precalcula lo pesado; la API solo hace consultas ligeras.
- **Descomposición:** A Datos, B API, C Web, D Entrega, T Transversal.
- **Reglas de trabajo:** las coordenadas y la orientación se verifican con el código local de Streamlit; solo se scrapea lo autorizado; las correcciones manuales viven en CSV versionados con motivo y fuente.
- **Referencias visuales:** `Downloads\gronestatz referencia 1.jpg` y `referencia 2.jpeg` (ficha de jugador, 14 paneles). La v1 hace 10 con datos.

## 1. Flujo de datos (aprobada)

```
sofascore_batches (manual, con registro y guardia de bloqueo)
  → extract-master → bootstrap-raw → build-staging → build-curated → build-warehouse
  → build-analytics (nueva) → validate → publish (bundle atómico)
```

- El scrapeo queda fuera de la corrida automática: se lanza con `sofascore_batches` cada jornada y el pipeline corre con `--no-scrape`.
- `build-analytics` va **después** de `build-warehouse`. Lee solo tablas canónicas del warehouse (`gronestats.duckdb`, con las cinco temporadas 2022-2026, que el xG y el Elo necesitan) y escribe sus resultados en el mismo warehouse, de modo que `validate` y `publish` los tratan como cualquier otra tabla.
- Las alineaciones entran como las demás fuentes: staging, curated y una tabla canónica `lineups`. El análisis no lee archivos crudos.
- Correcciones manuales en git: `resultados_oficiales.csv` (lo aplica `extract-master`) y `ajustes_tabla.csv` (lo aplica el cálculo de tablas).
- Los parámetros de los modelos (coeficientes del xG, parámetros del Elo) son archivos versionados. Una corrida normal los aplica; reajustar es un acto explícito (`--refit`) con su propio informe, por ejemplo al cerrar una temporada. Las probabilidades sí se recalculan en cada corrida porque hay resultados nuevos.
- `validate` suma comprobaciones propias:
  - las probabilidades de título suman 100 % en cada partido;
  - el xG total queda cerca de los goles (alarma de deriva, como la de 2025);
  - las tablas de torneos cerrados coinciden con la referencia oficial, que es un archivo versionado. Lleva documentadas las dos excepciones conocidas (Clausura 2024 y Clausura 2026), donde Wikipedia tiene un gol de diferencia que sus propias tablas acumuladas contradicen.

## 2. Contrato del bundle (aprobada, con ajustes)

Un bundle de servicio nuevo, con `publish-target` propio (`web`), que reúne las cinco temporadas y se construye desde el warehouse. Los bundles `dashboard` y `fantasy` actuales no se tocan (un test de contrato los exige sincronizados con el warehouse). Se publica en `releases/<run_id>/` con `current` como enlace atómico.

**Tablas existentes**, todas con `season` (`shot_events` hoy no la tiene): `matches` (con estado, fecha, estadio y ciudad), `teams`, `players`, `player_match`, `player_totals`, `shot_events`, `heatmap_points`, `average_positions`, `match_momentum`, `team_stats`.

**Tablas nuevas:**

| Tabla | Clave | Contenido |
|---|---|---|
| `shot_events` | + `xg`, `xg_model` | el xG va como columna del tiro |
| `lineups` | season, match, lado | formación declarada; defensas, medios y delanteros esperados y contados como enteros; `defenders_ok`; `consistent` |
| `match_importance` | season, match, equipo | partidos previos y restantes, puntos, umbral usado (37 o 40), derrotas permitidas, banda |
| `title_probability` | season, match, equipo | probabilidad de título, rating Elo, puntos |
| `standings` | season, torneo, fecha, equipo | Apertura, Clausura y Acumulada con los ajustes oficiales |
| `venues` | estadio | altitud en metros, fuente y precisión |
| `model_runs` | modelo, versión | parámetros, temporadas de ajuste, AUC y pérdida, xG total contra goles por temporada |
| `team_match_style` | season, match, equipo | métricas de estilo por partido; la API agrega los bloques de 5 |
| `player_percentiles` | season, jugador, métrica | percentil por grupo de rol |
| `player_similarity` | season, jugador, vecino | jugadores parecidos |
| `heatmap_density` | season, jugador | densidad precalculada del heatmap |
| `teammate_synergy` | season, jugador, compañero | sinergia, con xGD o diferencia de goles |

Las cuatro últimas ya estaban decididas el 25 de noviembre (las calcula el pipeline) y la ficha del jugador las necesita. Ninguna existe todavía como código: su definición (grupos de rol, minutos mínimos, medida de similitud y de sinergia) va al plan de implementación, igual que las métricas de `team_match_style`.

**Reglas del contrato:**
1. **Nombres uniformes.** Hoy el mismo dato se llama `season_year`, `season`, `tour` o `torneo` según el archivo. En el bundle serán `season` y `tournament`, con valores `Apertura` y `Clausura` (y `Acumulada` en `standings`).
2. **Datos de referencia en git**, igual que las correcciones: niveles de competitividad de las cinco temporadas y altitud por estadio.
3. **Un archivo de esquema en el repo** define columnas, tipos, nulos, claves y relaciones. `validate` comprueba el bundle contra él, la API genera sus modelos desde ahí y la web genera su cliente.
4. **`manifest.json` ampliado:** `schema_version` (la API rechaza un bundle con otra versión mayor), versiones de modelo, filas por tabla y cobertura por temporada (partidos con detalle, heatmaps, momentum y alineaciones). Esa cobertura alimenta el monitor de la sección 6.

## 3. API (aprobada, con ajuste)

FastAPI con DuckDB en solo lectura sobre `current`. No guarda estado, no tiene cuentas y no contiene reglas de dominio: esas viven en el pipeline. La API filtra, une y agrega según lo que el usuario elige (ventana de fechas, nivel del rival, altitud).

Endpoints por pantalla, no volcados genéricos de tablas, de modo que cada bloque de la web se arma con una llamada:

| Ruta (`/v1`) | Pantalla | Devuelve |
|---|---|---|
| `/seasons/{s}/standings?tournament=&round=` | Liga | tabla de Apertura, Clausura o Acumulada |
| `/teams/{id}/seasons/{s}/matches` | Liga | tira partido a partido: resultado, rival y su nivel, altitud, formación y ⚠, xG a favor y en contra, importancia, probabilidad |
| `/teams/{id}/seasons/{s}/title-race` | Liga | curva de probabilidad de título |
| `/teams/{id}/style?season=&window=5` | Equipo | bloques de 5 y tendencias; `/contexts` agrupa por rival, altitud e importancia |
| `/players/{id}?season=` | Jugador | ficha por paneles; además `/heatmap`, `/shots` y `/teammates` |
| `/matches/{id}` | Partido | detalle |
| `/release`, `/status` | Estado de datos | release activo, versiones de modelo y cobertura |

- **Releases:** abre `current` al arrancar y comprueba la versión mayor del esquema. El script de despliegue avisa por una ruta interna (solo desde localhost) cuando llega un release nuevo; la API lo abre y lo valida, y si falla sigue sirviendo el anterior. Cada respuesta lleva el `release_id`. El mismo aviso hace que la web revalide su caché (sección 4).
- **Caché:** los datos solo cambian al publicar un release, así que cada respuesta es inmutable dentro de uno. Con `ETag` por release y `Cache-Control`, Cloudflare absorbe casi todo el tráfico.
- **Dato ausente no es cero:** si falta algo en origen (por ejemplo el momentum de 2022) la respuesta trae `null` y `missing_reason: "missing_from_source"`, el mismo estado que usa el registro del scraper.
- **Contrato y pruebas:** OpenAPI sale del esquema de la sección 2 y la web genera su cliente desde ahí. Las pruebas corren contra un bundle de juguete en el repo; una prueba aparte, fuera de CI, usa el release real.

## 4. Web (presentada, pendiente de OK)

- **Stack:** app nueva `web/` con Next.js 14.2 (App Router), React 18, TypeScript y Tailwind 3.4, las mismas versiones que el frontend de Fantasy para copiar piezas sin migrar. Sin Capacitor ni app móvil, y sin monorepo hasta que Fantasy se enchufe.
- **Render:** componentes de servidor que llaman a la API por la red interna de Compose. Las páginas dependen solo del release, así que se cachean y se revalidan por etiqueta cuando el script de despliegue avisa de un release nuevo.
- **Rutas** (con slugs legibles para SEO):

| Ruta | Contenido |
|---|---|
| `/` y `/liga/[temporada]/[torneo]` | tabla, selector de equipo, tira partido a partido, curva de título |
| `/equipos/[slug]` | resumen; `/estilo` (bloques de 5 y tendencias) y `/contextos` (rival, altitud, importancia) |
| `/jugadores/[slug]` | ficha de 10 paneles y pestaña Compañeros |
| `/partidos/[id]` | detalle |
| `/estado` | estado de los datos, público |

- **Gráficos:** SVG dibujado en el servidor (tira, curvas, mapas de tiros, heatmaps con la densidad precalculada). Sin librería de gráficos; JavaScript en el cliente solo para selector, pestañas y tooltips. Las pantallas aprobadas ya están hechas así.
- **Tarjetas para compartir:** cada página principal genera su imagen Open Graph en el servidor (`next/og`), cacheada por release.
- **Reglas visibles de producto:** toda cifra derivada muestra su n; el dato ausente se muestra como «sin dato en origen», no como 0; el nivel del rival va en texto, no en color; el pie lleva el release y la fecha; español de Perú y hora de Lima; tema claro y oscuro; pensada primero para móvil.
- **Marcadores:** ⚠ queda solo para la formación cuyo número de defensas no coincide. La muestra chica (menos de 6 partidos) se atenúa y muestra «n=4», sin símbolo.
- **Paneles «próximamente»:** mapa de ocasiones, take-ons, inicio y fin de pases, zonas defensivas (las 6 hojas del scraper no traen eventos con coordenadas).
- **Fotos y escudos:** dorsales cuando no hay foto (cobertura del 85 % en 2026 y del 37 % al 65 % en 2022-2025); escudos hasta 150 px.

## 5. Entrega (pendiente)

## 6. Monitor de estado de datos (pendiente)

## 7. Transversal y pruebas (pendiente)

## Decisiones abiertas

- Qué cuenta como «tras la fecha N» en `standings` cuando hay partidos aplazados.
- Política de datos en git: el repo ya versiona los libros de Excel y los parquet generados (339 MB en `gronestats/data`), y es público.
- Rotar los secretos de `.env.qa` y `.env.test`, versionados en un repo público.
- Política de fotos y escudos (derechos sin verificar).
- Definición de percentiles por rol, similitud, sinergia, densidad de heatmap y métricas de estilo (plan de implementación).

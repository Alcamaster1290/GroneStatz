# Streamlit actual contra la web v1

Hecho el **2026-11-27** leyendo `gronestats/dashboard` (la versión de abril de 2026: `pages.py`, `views/overview.py`, `seasons.py`, `teams.py`, `players.py`, `matches.py`, `pitch.py` y los filtros de `app.py`) y comparándolo con `web/` (rama `feat/web-v1`).

Leyenda: ✔ igual o mejor · ◐ parcial · ✘ falta · ➕ solo existe en la web.

## Filtros globales

| Streamlit (barra lateral) | Web v1 |
|---|---|
| Temporada | ✔ selector de temporada |
| Torneos (varios a la vez, con Grand Final) | ◐ un torneo a la vez (Apertura, Clausura o Acumulada); la final y los playoffs no están en el bundle |
| Rango de rondas (deslizador) | ◐ una fecha a la vez (F1…F17), no un rango |
| Minutos mínimos | ✘ |

## Pantallas

| Streamlit | Web v1 |
|---|---|
| **Resumen** · acciones rápidas (equipo líder, máximo goleador, partido destacado) | ✘ |
| · tablas de posiciones de Apertura y Clausura | ✔ más completas: por fecha, acumulada con sanciones oficiales (15 de 15 tablas iguales a las oficiales) |
| · líderes por métrica (pestañas) | ✘ |
| · goles por ronda, goles local contra visita, partidos destacados | ✘ |
| **Temporadas** · comparativo consolidado (goles por partido, goleador, release) | ✘ |
| **Equipos** · identidad, forma reciente (chips), partidos recientes | ◐ la tira partido a partido es más rica; sin chips de forma |
| · split local y visita | ✘ |
| · top contribuyentes (G+A cada 90) | ◐ plantel con goles y xG, sin G+A cada 90 |
| · comparación contra el promedio de la liga | ✘ |
| **Jugadores** · tabla con filtros (equipo, posición, minutos) y búsqueda | ✘ no hay índice: solo se llega por el plantel de un equipo |
| · foto y resumen | ✔ foto en el 89,3 % de los jugadores con minutos |
| · mapa del jugador: posición promedio o heatmap, por partido o acumulado | ◐ solo heatmap acumulado de la temporada |
| · percentiles por posición | ✘ |
| · últimos partidos | ✘ (hay historial por temporada) |
| **Partidos** · catálogo con filtros (equipo, condición, resultado) | ✘ no hay índice: solo desde la tira de un equipo |
| · detalle · comparación curada, protagonistas | ✘ |
| · posiciones promedio de ambos equipos | ✘ |
| · mapa de tiros | ✔ con xG propio y tamaño por xG |
| · definiciones sobre el arco | ✘ |
| · momentum por minuto | ✘ |
| · atajadas de arquero | ✘ |
| · estadísticas completas por grupo | ✘ |
| · jugadores de cada lado | ✔ |
| · contexto (partidos recientes de ambos equipos) | ✘ |

## Solo en la web

- Probabilidad de campeonar tras cada partido (Elo con altitud y Monte Carlo) y su curva.
- Importancia de cada partido: derrotas que el equipo aún puede permitirse, con piso de 37 puntos.
- Nivel del rival, altitud de la sede y diferencia con la sede habitual.
- xG propio por tiro, validado dejando una temporada fuera.
- Formación declarada cruzada con los 11 titulares (⚠ si no coincide el número de defensas).
- Tarjetas por equipo y partido.
- Estado de los datos: cobertura, huecos clasificados por el registro de scrapeo, modelos y releases.
- Tablas oficiales con sanciones y partidos adjudicados o anulados.
- URL propias para compartir, renderizado en el servidor, tema claro y oscuro y uso en móvil.

## Qué le falta a la v1, por prioridad

**Prioridad 1: que se pueda explorar.** Es lo que más se nota al venir del Streamlit.
1. **Índice de jugadores con líderes y búsqueda** (`/jugadores`): goles, asistencias, xG, G+A cada 90, filtros por equipo, posición y minutos. Los datos ya están en el bundle (`player_match`, `shot_events`).
2. **Catálogo de partidos** (`/partidos`) con filtros de equipo, condición, resultado y fecha.
3. **Detalle de partido completo.** Publicar `team_stats`, `match_momentum` y `average_positions` en el bundle (ya existen en el warehouse) y añadir las pestañas Estadísticas por grupo, momentum, posiciones promedio y atajadas.
4. **Percentiles por posición** en la ficha del jugador (tabla `player_percentiles` del diseño; hoy sin código en la web, pero el Streamlit ya los calcula en `metrics.py`).

**Prioridad 2: profundidad.**
5. Mapa del jugador por partido y posición promedio (hoy solo heatmap acumulado).
6. Equipo: split local y visita, chips de forma reciente y comparación contra el promedio de la liga.
7. Gráficos de liga (goles por ronda, local contra visita), partidos destacados y comparativo consolidado de temporadas.
8. Filtros de rango de fechas y de minutos mínimos.

**Prioridad 3: lo que ya estaba en el diseño y sigue pendiente.**
9. Estilo de juego, contextos y compañeros; jugadores parecidos.
10. Tarjetas para compartir (Open Graph), fase `build-analytics` en el pipeline, despliegue y CI.

**Decisión pendiente:** la final y los playoffs (el Streamlit muestra «Grand Final»; el bundle de la web solo trae Apertura y Clausura).

---

# Referencia de scouting (captura de Alvaro, 2026-11-27)

Alvaro aclaró que el Streamlit es sobre todo **una referencia del tipo de información que se busca, orientada al scouting con datos, sin perder la parte comercial existente**. La comparación de arriba es contra `gronestats/dashboard` del repo; la captura es de otra app (liga argentina) que no está en el repo, así que lo siguiente sale solo de la imagen. **La «parte comercial» que no se debe perder** (aclarado por Alvaro el 2026-11-27) son las estadísticas y los gráficos típicos de televisión: xG, tiros, tiros al arco, posesión, córners y gráficos simples. La web debe conservar esa capa, sencilla y de lectura rápida, y sumarle por debajo la de scouting.

**Estructura que se ve.** Tres modos: *Clubes y Estadísticas*, *Jugadores y Scouting* y *Simulador Predictivo*. Dentro del primero: *Tablas de Liga*, *Ficha de Club*, *Comparador* y *Buscador de Partidos*. La tabla de liga tiene dos filtros, **Condición** (General, Local, Visitante) y **Valores** (Promedio por partido, Totales acumulados), y las columnas #, escudo, equipo, PJ, PTS, Efec %, GF, GC, DG, Pos %, Tiros, Al Arco, Córners y Atajadas; un selector de club abre su ficha.

**Qué de eso tenemos.** `Team Stats` trae 50 métricas en 7 grupos (Match overview, Shots, Attack, Passes, Defending, Duels, Goalkeeping) más xG, con 306 de 306 partidos en 2026.

| Elemento de la referencia | Con qué se construye | Estado |
|---|---|---|
| PJ, PTS, GF, GC, DG | `standings` y `matches` | ya está en el bundle |
| Efec % | puntos ÷ (3 × PJ) | se calcula |
| Condición local o visitante | `matches` (lado del equipo) | se calcula |
| Pos %, Tiros, Al Arco, Córners, Atajadas | `team_stats`: `ballPossession`, `totalShotsOnGoal`, `shotsOnGoal`, `cornerKicks`, `goalkeeperSaves` | está en el warehouse; falta publicarlo en el bundle |
| Ficha de club | página de equipo actual | parcial |
| Comparador de clubes | las 50 métricas de equipo | datos listos; falta la pantalla |
| Comparador de jugadores | percentiles por rol | falta calcularlos |
| Buscador de partidos | catálogo con filtros | falta |
| Jugadores y Scouting | `player_match`, xG por jugador, edad (`dateofbirth`), posición, fotos (89,3 %) | falta per-90, percentiles por rol, jugadores parecidos, filtros por edad, posición y minutos, y lista corta |
| Simulador predictivo | Elo con altitud y Monte Carlo (ya calcula la probabilidad de título) | falta exponerlo de forma interactiva (resultados hipotéticos) |

**Orden propuesto con este criterio:** (1) tablas de liga con estadísticas y los filtros Condición y Valores; (2) Jugadores y Scouting; (3) Comparador; (4) Buscador de partidos; (5) Simulador.

**Avance (2026-11-27):** el punto 1 está hecho. `/liga/[temporada]/[torneo]` muestra PJ, PTS, Efec %, GF, GC, DG, xG, xGC, Pos %, Tiros, Al arco, Córners, Atajadas, Faltas y tarjetas, con los filtros Condición (general, local, visitante) y Valores (promedio por partido, totales acumulados) y orden por cualquier columna. En «general» usa las posiciones y puntos oficiales (con sanciones); local y visitante se calculan solo con los partidos jugados, sin sanciones. Las estadísticas de equipo vienen de la tabla nueva `team_match_stats` del bundle (esquema 1.2.0).

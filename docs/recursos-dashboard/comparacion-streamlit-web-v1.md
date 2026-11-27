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

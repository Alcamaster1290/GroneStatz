# Recursos para construir el dashboard de GroneStats

Carpeta de apoyo creada el **2026-11-25**: reúne en un solo sitio lo que hace falta para construir el dashboard de forma limpia y profesional sin tener que redescubrirlo. No es código de producción.

## Contenido

| Ruta | Qué hay |
|---|---|
| [`DECISIONES.md`](DECISIONES.md) | Qué se decidió, qué propuse yo sin aprobar, los hallazgos de datos con sus cifras y los pendientes |
| [`plan-datos-faltantes.md`](plan-datos-faltantes.md) | Qué falta de verdad por temporada, qué se resuelve sin red, qué exige SofaScore y por qué ScraperFC no lo evita |
| [`coordenadas-y-orientacion.md`](coordenadas-y-orientacion.md) | Cómo están orientados los tiros y las posiciones, verificado con tu código de Streamlit, y el defecto del pipeline con el formato nuevo de SofaScore |
| [`xg-modelo.md`](xg-modelo.md) | xG propio por tiro (módulo `gronestats/analysis/xg_model.py`): qué repos se pueden reutilizar (licencias), el modelo, la validación y las tablas por jugador |
| [`formacion-declarada.md`](formacion-declarada.md) | Formación declarada por SofaScore para cada equipo y partido (2022-2026) y su cruce con la posición de los 11 titulares |
| [`verificacion-tablas.md`](verificacion-tablas.md) | Comprobación de las tablas de Apertura, Clausura y acumulada 2022-2026 contra Wikipedia y crónicas: dónde coinciden, sanciones de puntos y partidos anulados o adjudicados |
| [`importancia-y-probabilidad.md`](importancia-y-probabilidad.md) | Importancia de cada partido (derrotas permitidas) y probabilidad de campeonar de los 10 torneos de 2022 a 2026 (módulo `gronestats/analysis/title_race.py`), con los límites del umbral fijo |
| [`enlaces.md`](enlaces.md) | Enlaces verificados: galería de mplsoccer, datos y modelos, web, stack y tus repos con estrella |
| [`CHECKLIST-CALIDAD.md`](CHECKLIST-CALIDAD.md) | Lista de comprobación para dar una pantalla por terminada |
| `referencias-visuales/` | Las dos imágenes de referencia de la ficha de jugador (dorada y azul) |
| `datos-de-apoyo/` | `umbral_campeon.csv`, `nivel_competitividad_faltante.csv`, `altitud_estadios.csv` (plantilla por equipo, sustituida por `altitud_estadios_medida.csv`: altitud medida de las 33 sedes de 2022-2026, con fuente), `xg-prototipo/` (xG por tiro, partido y temporada, recalculado con el módulo), `title-race/` (importancia por equipo y partido, probabilidad de campeonar tras cada partido y parámetros del Elo), `pruebas-sofascore/` (resultado de la prueba mínima) y `maestro_2026_pre_refresco_2026-11-26.xlsx` (maestro de 261 partidos anterior al refresco, con los técnicos de entonces) |
| `prototipos/` | Scripts que validaron los números (Elo, importancia, formación, escudos, fotos) |
| `mockups/` | Las maquetas HTML (se abren con doble clic en el navegador) |

Orden de lectura sugerido: `DECISIONES.md` → `referencias-visuales/` → `enlaces.md` → `CHECKLIST-CALIDAD.md`.

## De tus referencias a los recursos

Cada panel de las referencias y dónde mirar. Son sugerencias.

| Panel de la referencia | Dato disponible hoy | Dónde mirar |
|---|---|---|
| Tarjeta del jugador | Sí (foto con avatar de respaldo) | `plot_photo`; `CHECKLIST-CALIDAD.md` (fotos) |
| Tabla de percentiles vs su posición | Sí, desde `player_stats_raw` | A construir en SVG; el bundle publicado hoy no trae las columnas |
| Radar polar de percentiles | Sí | Galerías *radar* y *pizza* de mplsoccer (solo referencia visual) |
| Top 10 por métrica | Sí | Tabla propia |
| Tiempo por posición | Aproximado | `plot_heatmap_positional`, `plot_formations` |
| Más similares | Sí | Generalizar `gronestats/analysis/indice_similaridad.py` |
| Mapa de tiros | Sí (xG propio por construir) | `plot_scatter` |
| Heatmap | 2025: 72.629 puntos; 2026: 398.936 (306 partidos) | `plot_kde`, `plot_hexbin` (precalculado en el pipeline) |
| Dispersión y strip plots con fotos | Sí | `plot_scatter` + `plot_photo` |
| Mapa de ocasiones y take-ons | **No** (faltan eventos) | `plot_lines`, `plot_arrows` (solo referencia) |
| Inicio y fin de pases, zonas defensivas | **No** (faltan eventos) | `plot_heatmap_zones` (solo referencia) |
| Compañeros (red) | Sí, sin pases entre jugadores | `plot_pass_network`, `plot_voronoi`, `plot_delaunay` |
| Figura y estilo del equipo | Sí | `plot_convex_hull`, `plot_formations` |
| Tarjeta para compartir | — | `plot_twitter_powerpoint`, `plot_textured_background` |

## Cosas a tener en cuenta

- **Los prototipos tienen rutas absolutas** a tu equipo y a la carpeta temporal de la sesión (por ejemplo `mock_liga.py` lee `title_probs_120.pkl` del scratchpad). Sirven para entender el cálculo, no para ejecutarlos tal cual.
- **`pantalla-liga.html` se regeneró el 2026-11-26 (v4)** con `prototipos/mock_liga_v4.py`: Liga 1 2026 (Apertura y Clausura), probabilidad tras cada partido, «Fuera de alcance» solo bajo 37 puntos, altitud en metros y xG propio. Es un HTML autocontenido con tema claro y oscuro; se regenera leyendo `datos-de-apoyo/title-race/` y el bundle de 2026. La versión anterior (Apertura 2025) era `prototipos/mock_liga.py`.
- **Las maquetas pesan unos 2,6 MB en total** porque incrustan los escudos en base64. En producción serán archivos aparte.
- **Los mouse-over de las maquetas usan CSS `:has()`** (Chrome 105+, Safari 15.4+, Firefox 121+) y no tienen equivalente táctil todavía.
- **No se hizo ningún commit.** Todo está sin versionar. `.superpowers/` sigue sin estar en `.gitignore`.

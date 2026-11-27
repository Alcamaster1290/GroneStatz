# Enlaces útiles para construir el dashboard

Todos los enlaces se comprobaron el **2026-11-25** (respuesta HTTP 200), salvo donde se indica. «Para qué» es una sugerencia mía según lo que diseñamos, no una norma.

## 1. Gráficas de cancha: mplsoccer (el enlace que pasaste)

Galería principal: <https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/index.html> (27 ejemplos).

> **Cómo encaja en el proyecto.** mplsoccer es Python/matplotlib: **no corre en el navegador**. El dashboard dibuja sus gráficas en SVG dentro de Next.js. mplsoccer sirve para (1) copiar ideas de diseño y de geometría de cancha, (2) **precalcular en el pipeline** (rejillas con `bin_statistic`, densidad KDE, hexbin) y (3) generar **imágenes estáticas** (tarjetas para compartir en X/YouTube).
> **Ojo con versiones:** el entorno local tiene `mplsoccer 1.2.2` y `requirements.txt` fija `1.5.1`. Alinear antes de usarlo.
> **Coordenadas:** mplsoccer documenta el tipo de cancha `opta` (0–100 en ambos ejes). Los datos de SofaScore del proyecto también van de 0 a 100 (`average_x` de 3 a 95, `average_y` de 0 a 100), pero **hay que verificar la orientación** de los ejes antes de dar por hecho que coinciden.

Ejemplos de la galería que encajan con tus referencias y con lo que diseñamos:

| Ejemplo | Enlace | Para qué en GroneStats |
|---|---|---|
| Heatmap | [plot_heatmap](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_heatmap.html) | Rejilla de zonas (mapa de calor con porcentajes, como «Pass Starts» de tus referencias) |
| Heatmap custom zones | [plot_heatmap_zones](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_heatmap_zones.html) | Zonas personalizadas (zonas defensivas, cuando haya eventos) |
| Heatmap Juego de Posición | [plot_heatmap_positional](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_heatmap_positional.html) | Zonas tipo «juego de posición» para tiempo por posición |
| Event distribution using kdeplot | [plot_kde](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_kde.html) | Heatmap suavizado del jugador (`heatmap_points`), precalculado en el pipeline |
| Hexbin plot | [plot_hexbin](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_hexbin.html) | Alternativa al KDE para densidad de toques |
| Scatter | [plot_scatter](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_scatter.html) | Mapa de tiros (goles y no goles) |
| Photos | [plot_photo](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_photo.html) | Fotos de jugadores sobre la cancha (referencia para la red de compañeros) |
| Pass Network | [plot_pass_network](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_pass_network.html) | Estilo visual de la red de compañeros (**nuestros datos no traen pases entre jugadores**; solo sirve de referencia de diseño) |
| Pass plot using lines / arrows | [plot_lines](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_lines.html) · [plot_arrows](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_arrows.html) | Mapa de ocasiones y take-ons (**requiere eventos con coordenadas, que hoy no descargamos**) |
| Pass flow plot | [plot_flow](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_flow.html) | Dirección del juego por zonas (también requiere eventos) |
| Formations | [plot_formations](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_formations.html) | Dibujar formaciones por conteo D-M-F en la pantalla de contexto |
| Plots a Voronoi diagram | [plot_voronoi](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_voronoi.html) | Zonas de influencia del once con posiciones medias |
| Delaunay Tessellation | [plot_delaunay](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_delaunay.html) | Conexiones espaciales entre compañeros (proximidad) |
| Convex Hull | [plot_convex_hull](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_convex_hull.html) | «Figura» del equipo: área que ocupa el once |
| Standardize data | [plot_standardize](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_standardize.html) | Convertir coordenadas entre sistemas |
| Grid | [plot_grid](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_grid.html) | Disposición de varias canchas en un solo panel (como los 6 mapas de tus referencias) |
| Shot freeze frame | [plot_shot_freeze_frame](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_shot_freeze_frame.html) | Solo referencia (necesita datos 360 que no tenemos) |
| Twitter and Powerpoint friendly | [plot_twitter_powerpoint](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_twitter_powerpoint.html) | Tarjetas para compartir en redes |
| Textured background | [plot_textured_background](https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_plots/plot_textured_background.html) | Estilo visual para imágenes de compartir |

Otras galerías y documentación de mplsoccer:

| Recurso | Enlace | Para qué |
|---|---|---|
| Documentación principal | <https://mplsoccer.readthedocs.io/en/latest/> | API: tipos de cancha, `bin_statistic`, `kdeplot` |
| Todas las galerías | <https://mplsoccer.readthedocs.io/en/latest/gallery/index.html> | Índice general |
| Radar | <https://mplsoccer.readthedocs.io/en/latest/gallery/radar/index.html> | Referencia del radar de percentiles |
| Pizza plots | <https://mplsoccer.readthedocs.io/en/latest/gallery/pizza_plots/index.html> | Referencia para el radar polar de tus referencias |
| Bumpy charts | <https://mplsoccer.readthedocs.io/en/latest/gallery/bumpy_charts/index.html> | Evolución de posiciones en la tabla por jornada |
| Configuración de cancha | <https://mplsoccer.readthedocs.io/en/latest/gallery/pitch_setup/index.html> | Dimensiones y tipos de cancha |
| Repositorio | <https://github.com/andrewRowlinson/mplsoccer> | Código y versiones |

## 2. Datos y modelos de fútbol

| Recurso | Enlace | Para qué |
|---|---|---|
| football-docs (nutmeg) | <https://nutmeg.withqwerty.com/football-docs/> | Documentación indexada de proveedores de datos (Opta, StatsBomb, Wyscout, FBref, Understat…). Instalada como MCP en el CLI; notas guardadas en `literatura/` |
| kloppy | <https://kloppy.pysport.org/> | Normalizar datos de eventos entre proveedores |
| socceraction (SPADL, VAEP, xT) | <https://socceraction.readthedocs.io/> | Si algún día hay eventos con coordenadas |
| soccerdata | <https://github.com/probberechts/soccerdata> | Referencia de cómo se obtienen datos abiertos |
| StatsBomb open data | <https://github.com/statsbomb/open-data> | Datos de eventos abiertos para **probar** gráficas de pases y take-ons mientras no existan los nuestros |
| World Football Elo Ratings: método | <https://www.eloratings.net/about> | Base del modelo Elo de la probabilidad de campeonar |
| Tu repo del Mundial 2026 con Elo | <https://github.com/Alcamaster1290/prediccion-mundial-2026-elo> | Tu propio enfoque Elo (en tus estrellas; **aún no lo revisé** para alinear el modelo) |

## 3. Gráficas, accesibilidad y rendimiento en la web

| Recurso | Enlace | Para qué |
|---|---|---|
| D3 | <https://d3js.org/> | Escalas, formas y utilidades para las gráficas en SVG |
| Observable Plot | <https://observablehq.com/plot/> | Alternativa declarativa a D3. **La comprobación devolvió 429 (límite de peticiones), no es un enlace roto; sin verificar** |
| WCAG 2.2: referencia rápida | <https://www.w3.org/WAI/WCAG22/quickref/> | Contraste, texto alternativo, teclado |
| Core Web Vitals | <https://web.dev/articles/vitals> | Presupuesto de rendimiento (LCP, INP, CLS) |
| MDN: `:has()` | <https://developer.mozilla.org/en-US/docs/Web/CSS/:has> | Base de los mouse-over de los mockups |
| MDN: `image-set()` | <https://developer.mozilla.org/en-US/docs/Web/CSS/image-set> | Escudos 1x/2x/3x en CSS |
| MDN: `srcset` | <https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img#srcset> | Escudos y fotos en varios tamaños con `<img>` |

## 4. Stack del proyecto

| Recurso | Enlace |
|---|---|
| Next.js | <https://nextjs.org/docs> |
| Tailwind CSS | <https://tailwindcss.com/docs> |
| DuckDB (Python) | <https://duckdb.org/docs/api/python/overview> |
| FastAPI | <https://fastapi.tiangolo.com/> |
| Caddy | <https://caddyserver.com/docs/> |
| Playwright (pruebas e2e) | <https://playwright.dev/docs/intro> |

## 5. De tus repos con estrella

| Repo | Enlace | Para qué / reservas |
|---|---|---|
| emilkowalski/skills | <https://github.com/emilkowalski/skills> | Pulido de interfaz y animación (MIT). Instalarlo cambia tu configuración: te consulto antes |
| jakubkrehel/skills | <https://github.com/jakubkrehel/skills> | Revisión de interfaz: accesibilidad, tipografía, color, movimiento (MIT) |
| nextlevelbuilder/ui-ux-pro-max-skill | <https://github.com/nextlevelbuilder/ui-ux-pro-max-skill> | Ya está cargado como skill |
| cathrynlavery/diagram-design | <https://github.com/cathrynlavery/diagram-design> | Diagramas de arquitectura para el spec |
| LottieFiles/motion-design-skill | <https://github.com/LottieFiles/motion-design-skill> | Principios de movimiento |
| greensock/GSAP | <https://github.com/greensock/GSAP> | Animación (solo si hace falta; revisar su licencia antes de usarlo) |
| chenglou/pretext | <https://github.com/chenglou/pretext> | Medir texto sin DOM, para que las etiquetas del radar no se solapen. **Su licencia figura como NOASSERTION: revisar antes de usarlo** |
| duckdb/duckdb | <https://github.com/duckdb/duckdb> | Motor de consultas (el repo usa la 0.10.2, ya antigua) |
| UnravelSports/unravelsports | <https://github.com/UnravelSports/unravelsports> | **No aplica**: requiere datos de tracking |

## 6. Modelos de xG y scrapeo (licencias comprobadas el 2026-11-25)

| Recurso | Enlace | Licencia | ¿Copiar código? |
|---|---|---|---|
| Índice de recursos de analítica (el que pasaste) | <https://github.com/eddwebster/football_analytics?tab=readme-ov-file#xg-modeling> | **Ninguna** | No; es un índice |
| soccer_xg (KU Leuven) | <https://github.com/ML-KULeuven/soccer_xg> | Apache-2.0 | Sí, con atribución |
| Tesis de xG de Andrew Rowlinson | <https://github.com/andrewRowlinson/expected-goals-thesis> | MIT | Sí |
| xGils | <https://github.com/christiangilson/xGils> | MIT | Sí |
| ScraperFC | <https://github.com/oseymour/ScraperFC> | **GPL-3.0** | Úsalo como librería; si algún día se distribuye código que lo incluya, revisar las obligaciones de la GPL |

Repos del mismo índice **sin licencia** (solo lectura): `how-to-expected-goals`, `xG_Model_Workflow`, `Expected-Goals-Model`, `Dato-Futbol/xg-model`, `devinpleuler/research`, `CleKraus/soccer_analytics`. Detalle en `xg-modelo.md`.

## 7. Pendiente de buscar (cuando lo pidas)

- **Altitud real de cada estadio** (ver `datos-de-apoyo/altitud_estadios.csv`, columna `altitud_msnm`): no puse cifras de memoria. Se llena con fuentes que verifiquemos juntos.
- **Escudos en alta resolución o vectoriales**: los actuales son de 150 px. Alvaro confirmó (2026-11-26) que tiene los derechos de los escudos y de las imágenes scrapeadas.

## Altitud de estadios (fuentes usadas el 2026-11-26)
Método reproducible detrás de `datos-de-apoyo/altitud_estadios_medida.csv`: coordenadas del estadio y elevación del modelo digital de terreno.
- Nominatim (búsqueda de estadios en OpenStreetMap; política de uso: máximo 1 consulta por segundo y `User-Agent` propio): https://nominatim.openstreetmap.org/ — datos © colaboradores de OpenStreetMap (ODbL).
- Open-Meteo, elevación por coordenadas (modelo Copernicus DEM, resolución de 90 m): https://open-meteo.com/en/docs/elevation-api
- Open-Meteo, geocodificación (elevación de la localidad, usada solo cuando el estadio no está en OpenStreetMap): https://open-meteo.com/en/docs/geocoding-api
- Cifras de prensa usadas solo como contraste: Libero (https://libero.pe/futbol-peruano/liga-1/2023/10/27/cuantos-clubes-altura-habra-en-liga-1-2024-cual-es-estadio-msnm-futbol-peruano-2072385), La República, Futbol Peruano y Wikipedia. Se contradicen entre sí (por ejemplo Cutervo, 2.649 y 2.836 m), por eso no se usan como valor.

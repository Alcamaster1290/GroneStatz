# GroneStats web (v1)

Next.js 14 (App Router, TypeScript, Tailwind) que renderiza en el servidor las pantallas de análisis de la Liga 1 con los datos de la API (`gronestats/api`). Diseño: `docs/superpowers/specs/2026-11-26-gronestats-web-design.md`; plan: `docs/superpowers/plans/2026-11-26-gronestats-web-v1.md`.

## Arrancar todo en local

Desde la raíz del repo, con un solo comando (construye el release si falta, levanta la API y la web y abre el navegador):

```
py -3.11 scripts/dev_web.py
```

Por partes:

```
py -3.11 -m gronestats.web_bundle.build     # release de servicio -> gronestats/data/Liga 1 Peru/web
py -3.11 -m gronestats.api                  # API en 127.0.0.1:8000
cd web && npm install && npm run build && npm run start   # web en 127.0.0.1:3000
py -3.11 scripts/smoke_web.py               # comprueba cada página con datos reales
```

Para desarrollar la web con recarga en caliente: `npm run dev` en lugar de `build` y `start`.

## Pantallas

| Ruta | Contenido |
|---|---|
| `/` | redirige a la liga de la última temporada |
| `/liga/[temporada]/[torneo]` | tabla (Apertura, Clausura o Acumulada, tras cada fecha) y probabilidad de campeonar |
| `/equipos/[slug]?season=&torneo=` | resumen, probabilidad, partido a partido (rival, altitud, xG, formación declarada, importancia), plantel |
| `/jugadores/[slug]?season=` | ficha: totales, mapa de tiros con xG, heatmap, historial por temporada |
| `/partidos/[id]` | marcador, formaciones, tiros de ambos equipos, jugadores |
| `/estado` | cobertura de datos, huecos conocidos, modelos y releases |

Todavía «próximamente»: estilo de juego, contextos, compañeros, percentiles por rol, jugadores parecidos y tarjetas para compartir.

## Variables de entorno (servidor)

| Variable | Por defecto | Para qué |
|---|---|---|
| `GRONESTATS_API_URL` | `http://127.0.0.1:8000` | dirección de la API desde el servidor de Next |
| `GRONESTATS_PUBLIC_API_URL` | la anterior | dirección de la API desde el navegador (fotos y escudos) |
| `NEXT_OUTPUT` | — | `standalone` para construir la imagen de Docker |

## Pruebas

`npm test` (Jest: formato, fechas, slugs y geometría de la cancha), `npm run typecheck` y `scripts/smoke_web.py` con la API y la web en marcha.

## Convenciones del diseño

- Un dato ausente se muestra como «—» o «sin dato», nunca como 0 (las tarjetas, por ejemplo, no vienen en el origen).
- Toda cifra derivada muestra su n; con menos de 6 partidos se atenúa.
- ⚠ solo marca una formación declarada cuyo número de defensas no coincide con el de los 11 titulares.
- El nivel del rival va en texto, no solo en color; los colores de club se mezclan con el color del texto del tema para que no desaparezcan sobre fondo oscuro.
- Coordenadas (`lib/pitch.ts`): en los tiros, `x` es la distancia al arco que se ataca; en el heatmap, `x` va en dirección de ataque.

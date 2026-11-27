# Literatura: football-docs

Notas guardadas el **2026-11-27** a pedido de Alvaro: la documentación de datos de fútbol de **football-docs** (https://nutmeg.withqwerty.com/football-docs/), condensada y ordenada para lo que necesita GroneStats. Alvaro no tenía una carpeta de literatura asignada en el repo, así que vive aquí, junto a `enlaces.md`; si prefieres otra ubicación, se mueve entera.

## Qué es la fuente

- **football-docs**, de *withqwerty* (proyecto *nutmeg*): un índice buscable de documentación de proveedores de datos, herramientas y librerías de fútbol, hecho para agentes de código («como Context7, pero de datos de fútbol»). En beta.
- El sitio lista 32 proveedores y herramientas (StatsBomb, Opta, Wyscout, SportMonks, Sportradar, Impect, SkillCorner, FBref, Understat, kloppy, mplsoccer, socceraction, soccerdata, Transfermarkt, FotMob, API-Football y otros) y unos 3.587 fragmentos buscables.
- Enlaces: sitio https://nutmeg.withqwerty.com/football-docs/ · guía de instalación para agentes https://nutmeg.withqwerty.com/football-docs/setup.md · código https://github.com/withqwerty/football-docs · paquete https://www.npmjs.com/package/football-docs (`npx -y football-docs@latest`, Node 22.13 o superior, sin clave de API).
- Cada resultado indica su fuente y puede enlazar a una copia archivada. El sitio dice que las tablas de endpoints se generan desde especificaciones públicas y se comprueban en CI.
- **Licencia:** el pie del sitio dice «MIT», pero el enlace no apunta a un archivo de licencia visible. Por eso aquí se guardan notas resumidas con atribución y no una copia del índice.

## Cómo se consultó

Con el servidor MCP `football-docs`, que ya está instalado en el CLI de Alvaro. Su índice local trae **10 de los 32 proveedores**:

| Proveedor | Fragmentos | Contenido |
|---|---|---|
| statsbomb | 143 | api-access, coordinate-system, data-model, event-types, xg-model |
| kloppy | 100 | data-model, provider-mapping, usage |
| sportmonks | 71 | api-access, data-model, event-types |
| databallpy | 63 | data-model, overview, usage |
| mplsoccer | 62 | overview, pitch-types, visualizations |
| wyscout | 61 | api-access, coordinate-system, data-model, event-types |
| free-sources | 45 | fbref, understat, overview |
| soccerdata | 40 | data-sources, overview, usage |
| opta | 29 | api-access, coordinate-system, event-types, qualifiers |
| socceraction | 26 | spadl, vaep-xt |

**Límites de esta instalación:**
- `resolve_entity` (equivalencias de IDs entre Transfermarkt, FBref, Sofascore y Opta) devolvió *401 Unauthorized* de la API Reep: hace falta credencial. No se pudo cruzar ningún ID.
- Las herramientas de papers y de métricas que anuncia el sitio (`search_papers`, `get_paper`, `read_paper`, `get_metric`, `list_metrics`) no están expuestas en esta instalación, así que no hay papers guardados.
- Algunos fragmentos del índice local traen solo el título de la sección. Donde pasó, las notas no completan lo que falta.
- La búsqueda con consultas largas no devuelve resultados; funcionan mejor las cortas («coordinate system», «xG model»).

## Notas

| Nota | Para qué sirve en GroneStats |
|---|---|
| [`coordenadas-entre-proveedores.md`](coordenadas-entre-proveedores.md) | Sistemas de coordenadas de Opta, StatsBomb y Wyscout, conversiones, y contraste con lo que ya verificamos de SofaScore |
| [`xg-y-valoracion-de-acciones.md`](xg-y-valoracion-de-acciones.md) | Cómo calculan el xG StatsBomb, Opta y Understat; xT, VAEP y SPADL; qué comparar con nuestro xG |
| [`estadisticas-para-scouting.md`](estadisticas-para-scouting.md) | Catálogo de estadísticas de scouting (FBref, Understat), qué trae nuestro `Player Stats` y la separación entre la capa de televisión y la de scouting |

## Cómo refrescarlo

Desde un agente con el MCP `football-docs`: `list_providers` para ver qué está indexado, `search_docs` con consultas cortas y filtro de proveedor, y `compare_providers` para contrastar un tema entre varios.

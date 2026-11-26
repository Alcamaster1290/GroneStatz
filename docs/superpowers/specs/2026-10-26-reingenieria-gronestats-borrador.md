# Reingeniería GroneStats mobile-web — borrador de diseño

**Estado:** brainstorming en curso (2026-10-26). NO aprobado. No es un spec final: faltan secciones.
**Rama:** `feat/clausura-2026-data` (sin commit de este archivo).

## Objetivo general

Usar la app Fantasy (`FantasyL1-2026/`: FastAPI + Next.js + Capacitor) como base de una app **mobile-web de GroneStats**, leer también los datos del Clausura y **relanzarla para 2027**. Servidor: **Oracle Cloud Always Free** (Hetzner descartado por soporte en LatAm).

## Descomposición en 4 sub-proyectos

Cada uno tiene su propio ciclo spec → plan → implementación.

| | Sub-proyecto | Depende de |
|---|---|---|
| A | **Datos**: completar Clausura y hacer el pipeline repetible | — |
| B | **Núcleo multi-torneo**: backend y BD con Apertura + Clausura (hoy asume una temporada por año) | A |
| C | **App mobile-web**: nueva interfaz GroneStats sobre la base Fantasy; qué se porta del dashboard Streamlit | B |
| D | **Infra en Oracle Always Free**: despliegue, dominio, backups | paralelo |

Orden elegido por el usuario: **A primero**.

## Sub-proyecto A — decisiones tomadas

1. **Quién scrapea:** el usuario, desde su PC, tras cada jornada. No se scrapea desde Oracle (IP de centro de datos, Cloudflare la bloquearía).
2. **Los 84 partidos de 2026 sin detalle** (72 Apertura rondas 2-16, 12 Clausura rondas 2-3): publicar parcial con la cobertura marcada y completarlos en tandas pequeñas, cada una autorizada por el usuario.
3. **Publicación al servidor:** un comando que sube por SSH (rsync) el bundle de parquets (~20 MB); el servidor corre la ingesta a Postgres.
4. **Enfoque:** evolucionar el pipeline existente (`gronestats/processing/pipeline.py`), no reescribirlo.
5. **Heatmaps:** apagados por defecto (son ~34 de ~35 llamadas por partido y el mayor riesgo de bloqueo).

## Sub-proyecto A — Sección 1 (presentada; pendiente de visto bueno)

```
Tu PC                                                    Oracle (servidor)
jornada ─┬─ 1. refrescar master  (lista de partidos)
         ├─ 2. scrape-batch      (solo pendientes, en tanda)
         │      └─ libro de registro: pendiente/ok/vacío/bloqueado
         ├─ 3. pipeline          (staging → curated → warehouse → validate)
         ├─ 4. empaquetar        (bundle + manifest + coverage.json + checksum)
         └─ 5. subir por SSH ───────────────────────────►  releases/<run_id>/
                                                            cambio atómico de `current`
                                                            ingesta a Postgres
```

Piezas nuevas:

1. **Libro de registro** `scrape_ledger.json` junto al master: por `match_id`, estado (`pendiente`/`ok`/`vacío`/`bloqueado`), intentos, fecha del último intento, último error. Se siembra con los 177 workbooks válidos como `ok` y los 84 restantes como `pendiente`.
2. **`scrape-batch`**: `--max-matches N`, `--sin-heatmaps` (por defecto), pausa mínima entre llamadas. Para al primer `challenge` o 403 consecutivo y marca `bloqueado`; sin reintentos en bucle. Usa siempre la sesión persistente (`sofascore_session.py`, ventana visible) y la cierra al terminar.
3. **`jornada`**: orquesta los 5 pasos; cada uno idempotente y ejecutable suelto. Si el paso 2 se detiene por bloqueo, el pipeline corre igual con lo que hay.
4. **Paquete de publicación**: incluye `coverage.json` (partidos terminados vs con detalle, por torneo y ronda; la app lo usa para marcar cobertura parcial) y checksum de los archivos.
5. **Lado servidor**: script corto que verifica checksum, apunta `current` al release nuevo (atómico) y lanza la ingesta a Postgres. Se conserva el release anterior (rollback = reapuntar `current`).

No cambia: fases del pipeline, parquets, esquema del warehouse.

## Pendiente de presentar para A

- Sección 2: protección contra Cloudflare (reglas de la tanda, qué hacer ante un bloqueo, logs), manejo de errores y casos borde (partido suspendido, workbook vacío < 15 KB, master sin cambios).
- Sección 3: pruebas (ledger, `coverage.json`, empaquetado/checksum, dry-run de la subida sin servidor).
- Luego: autoevaluación del spec, revisión del usuario, y `writing-plans`.

## Contexto que no hay que redescubrir

- Estado de datos 2026: master con 261 partidos terminados (153 Apertura, 108 Clausura); detalle de 177 (81 Apertura, 96 Clausura). `fantasy/current` y `dashboard/current` siguen en el release `20260407_223511`.
- Cloudflare: el usuario pidió **no abrir el navegador automatizado sin su autorización explícita**. Transporte actual: `gronestats/processing/sofascore_session.py`; `GRONESTATS_SKIP_HEATMAPS=1` omite heatmaps.
- Runbook del servicio caído: `docs/fantasy/RUNBOOK_RECUPERACION.md` (aún habla de Railway y VPS+Traefik; habrá que adaptarlo a Oracle en el sub-proyecto D).
- La app Fantasy aún no soporta dos torneos por temporada (ver apéndice del runbook): es el sub-proyecto B.
- El visual companion de superpowers se reinicia con `scripts/start-server.sh --project-dir <repo>` (Bash en segundo plano); añadir `.superpowers/` al `.gitignore` (aún no está).

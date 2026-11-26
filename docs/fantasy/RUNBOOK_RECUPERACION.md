# Runbook de recuperación — Fantasy Liga 1 (producción caída)

Estado documentado el **2026-10-22**. El servicio se dejó caído a propósito; este documento explica cómo levantarlo de nuevo sin romper nada y qué trampas tiene el repo.

> Todo lo de "qué hay desplegado hoy" sale de observar desde afuera (DNS y HTTP). No se tuvo acceso al panel de Railway ni al VPS, así que **el primer paso siempre es averiguar dónde estaba corriendo**.

## 1. Síntomas observados

| Comprobación | Resultado |
|---|---|
| `https://api.fantasyliga1peru.com/health` y `/health/db` | `404 {"status":"error","code":404,"message":"Application not found","request_id":"…"}` |
| `https://fantasyliga1peru.com` | `301` (redirige a `www`/`landing`) |
| `qa.` y `api-qa.fantasyliga1peru.com` | no hay registro DNS (sin respuesta) |

El cuerpo `Application not found` con `request_id` lo devuelve el proxy de borde de la plataforma, **no FastAPI** (el 404 de Traefik es el texto plano `404 page not found`). Significa que el hostname llega a la plataforma pero no está enlazado a ningún servicio vivo: dominio desvinculado, servicio o proyecto borrado, o proyecto pausado (créditos o plan). Es una inferencia por el formato de la respuesta, no está verificada.

## 2. Hay dos destinos de despliegue en el repo

El repo contiene los dos, y no hay documentación de cuál era el vigente:

- **A. VPS + Traefik + Docker Compose** (`docker-compose.prod.yml`, `docker-compose.qa.yml`, `DEPLOYMENT_PROD.md`). Era el diseño original.
- **B. Railway** (`FantasyL1-2026/backend/railway.toml`, `FantasyL1-2026/frontend/railway.toml`). Preparado en los commits `8aaf342` y `de1ffe8` (2026-04-05): `PORT` dinámico y normalización de `DATABASE_URL`.

El mensaje de error apunta a que hoy el dominio apuntaba a Railway. Confírmalo mirando los registros DNS del dominio y entrando al panel de Railway.

## 3. Pre-requisito común: secretos

Antes de levantar nada:

1. Rotar `JWT_SECRET`, `ADMIN_TOKEN` y `POSTGRES_PASSWORD`. `.env.qa` y `.env.test` están **versionados en git** con valores de 7 a 9 caracteres (el `.gitignore` solo cubre `.env` y `**/.env.prod`). Si QA usó esos valores en un servidor real, ya están expuestos en el historial.
2. Sacar esos archivos del índice (`git rm --cached FantasyL1-2026/.env.qa FantasyL1-2026/.env.test`) y añadirlos al `.gitignore`.
3. El backend exige `JWT_SECRET` y `ADMIN_TOKEN` (no arranca sin ellos) pero no valida su longitud: usa valores aleatorios largos (32+ caracteres).

## 4. Camino B — Railway

Necesitas tres servicios en un proyecto Railway:

| Servicio | Origen | Notas |
|---|---|---|
| Postgres | plugin de Railway | provee `DATABASE_URL` |
| Backend | repo, *root directory* `FantasyL1-2026/backend` | `Dockerfile` + `railway.toml` (healthcheck `/health`, 30 s) |
| Frontend | repo, *root directory* `FantasyL1-2026/frontend` | `Dockerfile` + `railway.toml` (healthcheck `/landing`, 30 s) |

**Variables del backend:** `DATABASE_URL` (si viene como `postgresql://` el código la convierte a `postgresql+psycopg://`), `JWT_SECRET`, `ADMIN_TOKEN`, `APP_ENV=prod` (activa el CORS de `fantasyliga1peru.com` y `www`), `CORS_ORIGINS`. Ojo: `CORS_ORIGIN_REGEX` por defecto solo permite localhost. Opcionales: `MOBILE_CORS_ORIGINS`, `PUSH_ENABLED`, `PUSH_REMINDER_HOURS_BEFORE`, `FCM_PROJECT_ID`, `FCM_SERVICE_ACCOUNT_JSON`, y los tres `SYNC_*` (ver sección 6).

**Variables del frontend:** `NEXT_PUBLIC_API_URL` (URL **absoluta** `https://api…`; se hornea en el build y alimenta el rewrite `/api/*`, así que hay que redeployar si cambia), `NEXT_PUBLIC_APP_CHANNEL`, `NEXT_PUBLIC_MOBILE_WEB_URL`.

**Dominios:** adjuntar `api.fantasyliga1peru.com` al servicio backend y `fantasyliga1peru.com`/`www` al frontend, y crear en el DNS los CNAME y registros de verificación que Railway indique. Aquí estaba probablemente la ruptura.

**Migraciones:** no hay *release command* ni se migra al arrancar (ni el Dockerfile ni `main.py` ejecutan Alembic). Con la base nueva vacía hay que correr una vez, apuntando `DATABASE_URL` a la URL **pública** del Postgres de Railway:

```powershell
cd FantasyL1-2026
$env:DATABASE_URL = "<url publica de Railway>"; $env:JWT_SECRET = "x"; $env:ADMIN_TOKEN = "x"
python -m alembic -c backend\alembic.ini upgrade head
```

(`railway run` también sirve.) Hay 19 migraciones, hasta `0019_add_premium_badge_defaults`.

**El contenedor no incluye `gronestats/`**, así que `POST /admin/rebuild_catalog` falla con `parquet_dir_not_found`. El catálogo (equipos y jugadores) se carga desde una máquina que tenga el repo y vea la base:

```powershell
python FantasyL1-2026\scripts\ingest_to_duckdb.py
python FantasyL1-2026\scripts\sync_duckdb_to_postgres.py
```

(con `DATABASE_URL`, `PARQUET_DIR` y `DUCKDB_PATH` definidos y los flags `SYNC_*`, sección 6).

## 5. Camino A — VPS + Traefik

Desde la **raíz del repo** en el VPS (`/opt/GroneStatz`):

```bash
docker compose -f docker-compose.prod.yml --env-file FantasyL1-2026/.env.prod up -d --build
```

Cosas que no aparecen en la documentación original:

- **El proyecto compose debe llamarse `gronestatz`** (el directorio `/opt/GroneStatz` en minúsculas lo da por defecto). Traefik busca la red `gronestatz_edge`, que está fija en `--providers.docker.network` y en las etiquetas `traefik.docker.network`. Con otro nombre (`-p`, otro directorio) Traefik no encuentra rutas y responde `404 page not found`.
- El archivo de entorno vive en `FantasyL1-2026/.env.prod` (está en `.gitignore`). `DEPLOYMENT_PROD.md` dice `cp .env.prod.example .env.prod`, pero **ese ejemplo no existe**, y el README manda a `../.env.prod`, que apuntaría a la raíz. Hay que crearlo a mano con: `ACME_EMAIL`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET`, `ADMIN_TOKEN` y, si quieres push, `PUSH_ENABLED`, `PUSH_REMINDER_HOURS_BEFORE`, `FCM_PROJECT_ID`, `FCM_SERVICE_ACCOUNT_JSON`.
- El compose pasa al contenedor solo `JWT_SECRET`, `ADMIN_TOKEN`, `DATABASE_URL`, CORS y push. **No pasa** `SEASON_*`, `PARQUET_DIR`, `DUCKDB_PATH` ni los `SYNC_*`: dentro del contenedor rigen los valores por defecto del código (`SYNC_*` en `False`).
- DNS: `A @` y `A api` al IP del VPS, `CNAME www` a `fantasyliga1peru.com`. Puertos 80, 443 y 22. Postgres no se publica.
- Traefik emite certificados con el desafío HTTP en el puerto 80; la raíz `/` redirige a `https://www.fantasyliga1peru.com/landing`.
- **QA** usa su propio Traefik en 8080/4443, pero el desafío ACME sigue necesitando que el puerto 80 público llegue a él. Los registros DNS de `qa` y `api-qa` hay que crearlos (hoy no existen).
- Diagnóstico de `db_unavailable` (ya documentado): ver la sección correspondiente de `FantasyL1-2026/DEPLOYMENT_PROD.md`.

## 6. Trampas que pueden destruir datos

1. **`_prune_missing_players` es global.** El sync borra de `players_catalog` todo jugador que no esté en el parquet, y con él sus filas en plantillas, transfers, historial de precios, `points_round`, `player_round_stats` y `player_match_stats` de **todas** las temporadas. Mantener siempre `SYNC_SKIP_PRUNE_MISSING_PLAYERS=true`.
2. Para no pisar precios ni estadísticas ya cargadas: `SYNC_PRESERVE_EXISTING_PRICE_CURRENT=true` y `SYNC_PRESERVE_EXISTING_BASE_STATS=true`.
3. **El `docker run` del final de `FantasyL1-2026/README.md` no pasa esos tres flags**, así que ejecutarlo tal cual hace prune y sobrescribe precios y stats. Añadir:
   `-e SYNC_SKIP_PRUNE_MISSING_PLAYERS=true -e SYNC_PRESERVE_EXISTING_PRICE_CURRENT=true -e SYNC_PRESERVE_EXISTING_BASE_STATS=true`.
4. **`scripts/activate_prod.ps1` ejecuta `clear_rounds.py` salvo que pases `-SkipClearRounds`.** Ese script hace `DELETE` de rondas, fixtures, alineaciones, transfers, stats e historial de precios de todas las temporadas, sin filtro. No lo uses contra una base con datos.
5. Los `build args` `NEXT_PUBLIC_ENABLE_PASSWORD_RESET`, `NEXT_PUBLIC_UI_REDESIGN_V1` y `NEXT_PUBLIC_UI_REDESIGN_V1_ROUTES` que pasa `docker-compose.prod.yml` **no tienen `ARG` en el `Dockerfile` del frontend** (solo están `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_CHANNEL` y `NEXT_PUBLIC_MOBILE_WEB_URL`). En el build en contenedor esas banderas se pierden y quedan en su valor por defecto. Añadir los `ARG`/`ENV` antes de contar con el rediseño en producción.
6. `SCHEDULER_ENABLED` está en `True` por defecto y el planificador corre dentro del proceso web. Con más de una réplica o varios workers, los recordatorios push y el cierre automático de rondas se ejecutarían duplicados. Hoy el `Dockerfile` arranca un solo proceso.

## 7. Orden de arranque con base vacía

1. Levantar Postgres y la API (sección 4 o 5). `GET /health` debe dar `{"ok": true, "env": "prod"}`.
2. Migrar: `alembic upgrade head`.
3. Con el repo a mano: `ingest_to_duckdb.py` y luego `sync_duckdb_to_postgres.py` (carga equipos y jugadores desde `gronestats/data/Liga 1 Peru/2026/fantasy/current/`).
4. Crear la temporada y las rondas: `POST /admin/seed_season_rounds?rounds=N` (cabecera `X-Admin-Token`).
5. Cargar fixtures (`POST /admin/fixtures`) y, ronda a ronda, estadísticas (`POST /admin/player-stats`) y `POST /admin/recalc_round`. Los fixtures **no** se sincronizan desde los parquets.
6. Verificar: `GET /health/db` (`"db":"up"`), `GET /public/app-config`, `GET /public/leaderboard?limit=25&season_year=2026`.

Los usuarios, equipos y ligas de los usuarios viven solo en Postgres. Si la base anterior ya no existe, esos datos se perdieron: comprobar si hay respaldo del volumen `fantasy_pg_data` (VPS) o de Railway antes de crear una base nueva.

## 8. Estado de los datos que alimentan la app

- El bundle publicado en `gronestats/data/Liga 1 Peru/2026/fantasy/current/` fue generado el **2026-04-07** (run `20260407_223511`) y cubría solo el **Apertura, rondas 1 a 9** (72 partidos). Para el resto del Apertura y el Clausura ver `docs/gronestats/clausura_multitorneo.md`.
- Todo release anterior sigue en `fantasy/releases/`, por si hay que volver atrás.

## 9. Apéndice: qué cambiar en la app para soportar el Clausura

Solo diseño, nada de esto está implementado. Hoy el backend asume una temporada por año:

1. **`get_or_create_season`** (`backend/app/services/fantasy.py:41`) busca por `Season.year == SEASON_YEAR` con `scalar_one_or_none()`. Con dos temporadas del mismo año lanza `MultipleResultsFound` y todos los endpoints devuelven 500. Se usa unas 70 veces. Resolver por `name` o por una clave de `app_config` (`CURRENT_SEASON_YEAR` ya se siembra pero ningún código la lee). Otros sitios con lookup por año: `services/premium.py:44-51`, `api/admin.py:706`, `api/public.py:25,49`, `scripts/seed_test_minimum.py`, `scripts/mirror_prod_public_to_test.py`, `gronestats/processing/fantasy_bridge_export.py`.
2. **Esquema:** `rounds` no tiene UNIQUE(`season_id`, `round_number`) y `seasons` no tiene unicidad; `fantasy_teams.user_id` es UNIQUE, así que el equipo del Apertura se reasigna al Clausura (`get_or_create_fantasy_team`) y el ranking del Apertura desaparece; `league_members.fantasy_team_id` es UNIQUE; el CHECK de `plan_code` solo admite `FREE`, `PREMIUM_2R`, `PREMIUM_4R`, `PREMIUM_APERTURA`.
3. **Estado que se arrastra:** `fantasy_team_players` no tiene temporada (conserva `bought_price` de rondas del Apertura), `budget_cap` se acumula, y `players_catalog.price_current` es global. Para empezar el Clausura con precios nuevos hay que sincronizar una vez con `SYNC_PRESERVE_EXISTING_PRICE_CURRENT=false`.
4. **Admin:** todos los endpoints operan sobre la temporada "activa"; para preparar el Clausura con el Apertura abierto hace falta un parámetro de temporada.
5. **Premium:** `PREMIUM_APERTURA`, `APERTURA_PREMIUM_LAST_SELL_ROUND=12`, `APERTURA_TOTAL_ROUNDS=18` y los campos `apertura_*` de los esquemas y de `frontend/lib/types.ts`.
6. **Frontend:** `season_year=2026` fijo en `lib/api.ts` y `components/LandingTabs.tsx`; textos "Apertura 2026" y "2026" en `layout.tsx`, `landing/page.tsx`, `AppHeader.tsx`, `WelcomeSlideshow.tsx`, etc.
7. **Scripts legados:** `watch_parquets.py` es un bucle infinito que además llama a `create_empty_matches_2026.py` (apunta a rutas `parquets/normalized` de 2025, ya obsoletas).
8. **Tests que faltan:** `get_or_create_season` con dos temporadas, reinicio de presupuesto en la ronda 1, ventana premium y reasignación del equipo.

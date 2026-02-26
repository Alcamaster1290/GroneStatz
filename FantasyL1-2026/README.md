# Fantasy Liga 1 2026

App Fantasy (FastAPI + Next.js) basada en el pipeline de parquets.
Flujo: Parquets → DuckDB → Postgres → API → PWA.

## Requisitos
- Docker Desktop
- Python 3.11+
- Node 18+

## Setup rápido (local/test/qa)
1) Entra al proyecto:
```
cd FantasyL1-2026
```
Si tu ruta tiene espacios, usa comillas en PowerShell.

2) Variables de entorno:
- Edita `.env`, `.env.test`, `.env.qa`, `.env.prod` según el entorno.
- Frontend: parte de `frontend/.env.local.example` y crea `frontend/.env.local`.

3) Levanta todo (local):
```
.\scripts\start_all.ps1 -Env local -SkipWatch
```
Test:
```
.\scripts\start_all.ps1 -Env test -SkipWatch
```
QA:
```
.\scripts\start_all.ps1 -Env qa -SkipWatch
```
Rebuild completo (parquets + imágenes + caches):
```
.\scripts\start_all.ps1 -Env test -SkipWatch -Rebuild
```

## Entornos
- `local`: usa `.env` y `frontend/.env.local`.
- `test`: entorno legado de pruebas.
- `qa`: entorno QA formal (`.env.qa`) con base separada.
- `prod`: producción.

Arquitectura objetivo:
- `prod-web` y `prod-mobile` comparten API y DB de producción.
- `qa-web` (y opcional `qa-mobile`) usan API + DB QA separadas.

El backend lee `APP_ENV` o `ENV_FILE`.
Migraciones por entorno:
```
$env:ENV_FILE=".env.test"
python -m alembic -c backend\alembic.ini upgrade head
```

## Premium + Landing + Top25 (TEST primero)
Checklist de ejecucion en TEST antes de tocar PROD:

1) Activar entorno test:
```
$env:APP_ENV="test"
$env:ENV_FILE=".env.test"
```

2) Migrar SOLO test:
```
cd backend
python -m alembic -c alembic.ini upgrade head
```

3) Seed minimo para 2026 + rondas 1..18:
```
cd ..
python scripts/seed_test_minimum.py --season-year 2026 --season-name "2026 Apertura" --total-rounds 18
```

4) Validar endpoints nuevos:
```
curl http://localhost:8000/public/leaderboard?limit=25&season_year=2026
curl http://localhost:8000/public/premium/config?season_year=2026
curl http://localhost:8000/public/app-config
curl -H "Authorization: Bearer <TOKEN>" http://localhost:8000/me/subscription
curl -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" ^
  -d "{\"plan_code\":\"PREMIUM_2R\",\"provider\":\"manual\"}" http://localhost:8000/premium/checkout-intent
```

5) Branding Premium Badge (admin):
- Keys en `app_config`:
  - `PREMIUM_BADGE_ENABLED` (`true`|`false`)
  - `PREMIUM_BADGE_TEXT` (`P` por defecto)
  - `PREMIUM_BADGE_COLOR` (`#7C3AED` por defecto)
  - `PREMIUM_BADGE_SHAPE` (`circle`|`rounded`)
- Lectura publica (whitelist): `GET /public/app-config`
- Escritura admin:
  - `GET /admin/app-config/premium-badge`
  - `PUT /admin/app-config/premium-badge` (requiere `X-Admin-Token`)

5) Flujo web:
- `/` => landing con tabs (inicio, como-jugar, ranking top25, premium, fixtures, faq)
- CTA principal => `/login?redirect=/app`
- `/app` => entrada al juego (redirige a ruta actual `/team`)

Notas:
- `PREMIUM_APERTURA` se ofrece solo hasta ronda configurable (`APERTURA_PREMIUM_LAST_SELL_ROUND`, default `12`).
- Backend rechaza activacion de `PREMIUM_APERTURA` fuera de ventana aunque frontend lo oculte.
- No desplegar a PROD sin validar el checklist anterior.

## Parquets
Ruta esperada (datos base):
`gronestats/data/Liga 1 Peru/2025/parquets/normalized/`

Parquets usados:
- matches.parquet
- teams.parquet
- players.parquet
- players_fantasy.parquet
- player_match.parquet
- player_totals.parquet
- player_team.parquet
- player_transfer.parquet
- team_stats.parquet

**Importante:** la app usa `players_fantasy.parquet` como catálogo. Fixtures 2026 se cargan desde Admin (no desde matches 2025).

## Scripts clave
- `scripts/ingest_to_duckdb.py`: carga parquets a DuckDB.
- `scripts/sync_duckdb_to_postgres.py`: sincroniza a Postgres.
- `scripts/watch_parquets.py`: watcher para re-sync automático.
- `scripts/recalc_round.py`: recalcula puntos y precios.
- `scripts/convert_images_to_png.py`: convierte a PNG con fondo transparente.
- `scripts/start_qa.ps1`: arranca stack QA.
- `scripts/activate_qa.ps1`: migra + inicia QA.

## App móvil (Capacitor)
Base móvil en `frontend` con Capacitor (Android/iOS).

Comandos:
```
cd frontend
npm install
npm run cap:add:android
npm run cap:add:ios
npm run cap:sync
```

Variables frontend relevantes:
- `NEXT_PUBLIC_APP_CHANNEL=mobile`
- `NEXT_PUBLIC_MOBILE_WEB_URL=https://fantasyliga1peru.com` (prod)
- `NEXT_PUBLIC_MOBILE_WEB_URL=https://qa.fantasyliga1peru.com` (qa)

Push móvil:
- Backend: `PUSH_ENABLED`, `PUSH_REMINDER_HOURS_BEFORE`, `FCM_PROJECT_ID`, `FCM_SERVICE_ACCOUNT_JSON` (o `GOOGLE_APPLICATION_CREDENTIALS`).
- Frontend: activar/desactivar desde `Ajustes`.

## Admin API
Header requerido: `X-Admin-Token: <ADMIN_TOKEN>`

Endpoints comunes:
- `POST /admin/rebuild_catalog`
- `POST /admin/fixtures` (crear/actualizar partido)
- `PUT /admin/fixtures/{id}`
- `POST /admin/player-stats`
- `POST /admin/recalc_round?round_number=1`
- `PUT /admin/rounds/{round_number}/window` (configura `starts_at`/`ends_at`)
- `POST /admin/notifications/round-reminders/run?dry_run=true|false`

Notificaciones autenticadas (usuario):
- `POST /notifications/devices/register`
- `GET /notifications/devices`
- `DELETE /notifications/devices/{device_id}`

## Login / Reset password
En prod el reset está deshabilitado por defecto.
Para habilitarlo en web:
```
NEXT_PUBLIC_ENABLE_PASSWORD_RESET=true
```

## Deploy PROD (VPS)
Usa el compose raíz y Traefik (TLS):
- `../docker-compose.prod.yml`
- `../docker-compose.qa.yml` (QA)
- `DEPLOYMENT_PROD.md`

Comando:
```
docker compose -f ../docker-compose.prod.yml --env-file ../.env.prod up -d --build
```
QA:
```
docker compose -f ../docker-compose.qa.yml --env-file ../.env.qa up -d --build
```

## Troubleshooting rápido
- `ModuleNotFoundError: app`: corre alembic desde la raíz del proyecto con `.venv` activo.
- `fixtures.status does not exist`: migra y luego `sync_duckdb_to_postgres.py`.
- `no_players_available`: verifica `players_fantasy.parquet` y re-sync.

---

Si estás en VPS y necesitas refrescar catálogo/imagenes desde parquets:
```
docker run --rm --network gronestatz_internal \
  -e DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}" \
  -e PARQUET_DIR="/data/parquets" \
  -e DUCKDB_PATH="/data/fantasy.duckdb" \
  -e PYTHONPATH=/app \
  -v "/opt/GroneStatz/gronestats/data/Liga 1 Peru/2025/parquets/normalized:/data/parquets" \
  -v "/opt/GroneStatz/FantasyL1-2026:/repo" \
  gronestatz-api sh -lc "python /repo/scripts/ingest_to_duckdb.py && python /repo/scripts/sync_duckdb_to_postgres.py"
```

# Deploy PROD (Fantasy Liga 1 2026)

## Requisitos DNS
- A @ -> IP del VPS
- A api -> IP del VPS
- CNAME www -> fantasyliga1peru.com

## Variables de entorno
1) Copia y edita:
```
cp .env.prod.example .env.prod
```
2) Completa:
- ACME_EMAIL
- POSTGRES_PASSWORD (fuerte)
- PUSH_ENABLED=true
- PUSH_REMINDER_HOURS_BEFORE=24
- FCM_PROJECT_ID
- FCM_SERVICE_ACCOUNT_JSON (o GOOGLE_APPLICATION_CREDENTIALS)

## Despliegue
```
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Despliegue QA (VPS)
Archivo compose QA (raíz del repo):
`docker-compose.qa.yml`

Comando:
```
docker compose -f docker-compose.qa.yml --env-file .env.qa up -d --build
```

Dominios sugeridos QA:
- `qa.fantasyliga1peru.com`
- `api-qa.fantasyliga1peru.com`

## Verificacion
```
docker compose -f docker-compose.prod.yml ps
curl https://api.fantasyliga1peru.com/health
```
QA:
```
docker compose -f docker-compose.qa.yml ps
curl https://api-qa.fantasyliga1peru.com/health
```

## Firewall
- 80
- 443
- 22

## Nota
Postgres no se expone a internet (sin ports).

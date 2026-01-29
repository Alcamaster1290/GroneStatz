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

## Despliegue
```
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Verificacion
```
docker compose -f docker-compose.prod.yml ps
curl https://api.fantasyliga1peru.com/health
```

## Firewall
- 80
- 443
- 22

## Nota
Postgres no se expone a internet (sin ports).

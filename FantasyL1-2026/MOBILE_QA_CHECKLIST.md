# Mobile QA Checklist (Android v1 sin push)

## Build metadata
- Perfil:
- Version code:
- Version name:
- Dispositivo:
- Android:
- Fecha:
- Tester:

## Smoke principal
- [ ] Instala desde Play Internal (o AAB local) sin error.
- [ ] Abre app y muestra landing.
- [ ] CTA `JUEGA YA` lleva a login.
- [ ] Login correcto redirige a `/app` (no rebote a landing).
- [ ] Cierre y reapertura mantiene sesion activa.

## Flujos funcionales
- [ ] Team carga sin errores.
- [ ] Market carga jugadores y permite operaciones base.
- [ ] Ranking carga sin estados colgados.
- [ ] Fixtures muestra jornada correctamente.
- [ ] Rondas/estadisticas publicas visibles sin bloqueo.

## Robustez
- [ ] Modo avion durante carga muestra error controlado.
- [ ] Recupera al volver red sin reiniciar app.
- [ ] No hay crash en navegacion entre tabs.

## Politica v1
- [ ] No solicita permisos de push.
- [ ] Seccion push no visible cuando `NEXT_PUBLIC_PUSH_ENABLED=false`.

## Evidencia
- Capturas:
- Logs:
- Bugs abiertos:

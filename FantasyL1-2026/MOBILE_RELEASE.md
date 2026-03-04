# Plan Modular Mobile Release (Android primero)

Este documento aterriza el plan por etapas para llevar Fantasy Liga 1 2026 a tiendas sin romper el flujo web.

## Etapa 1 - Fundaciones (bundle local)

### Modulo 1.1 - Arquitectura bundle local
Estado: implementado.

Hechos:
- Build mobile con `MOBILE_BUILD_PROFILE=qa|prod`.
- Next export para mobile (`output=export`) y assets locales en `frontend/www`.
- Capacitor en release QA/PROD sin `server.url` remoto.
- `NEXT_PUBLIC_API_URL` obligatorio absoluto en build mobile.

Comandos:
```
cd frontend
npm run build:mobile:bundle:qa
npm run build:mobile:bundle:prod
```

### Modulo 1.2 - Perfiles y configuracion por entorno
Estado: implementado.

Hechos:
- Perfiles versionados:
  - `frontend/.env.mobile.qa`
  - `frontend/.env.mobile.prod`
- Scripts de sync por perfil:
  - `npm run cap:sync:qa`
  - `npm run cap:sync:prod`
- Push deshabilitado en v1 por variable:
  - `NEXT_PUBLIC_PUSH_ENABLED=false`

Flujo rapido QA:
```
cd frontend
npm run build:mobile:qa
```

## Etapa 2 - Android release v1 (Play Internal Testing)

### Modulo 2.1 - Hardening Android para tienda
Estado: implementado parcialmente.

Hechos en repo:
- `versionCode` y `versionName` configurables por entorno:
  - `MOBILE_ANDROID_VERSION_CODE`
  - `MOBILE_ANDROID_VERSION_NAME`
- Firma release soportada por:
  - Variables `ANDROID_KEYSTORE_*`, o
  - `frontend/android/keystore.properties` (no commitear).
- Ejemplo de keystore:
  - `frontend/android/keystore.properties.example`
- Scripts E2E Android:
  - `npm run android:release:qa`
  - `npm run android:release:prod`
  - `npm run android:assemble:qa`
  - `npm run android:assemble:prod`

Pendiente externo:
- Subida de `.aab` a Play Console Internal Testing.

### Modulo 2.2 - Compliance Android (v1 sin push)
Estado: pendiente externo (Play Console).

Checklist:
- Privacy policy publica y estable.
- Data Safety completado.
- Declaracion de permisos coherente.
- Store listing final (icono, screenshots, copy).

## Etapa 3 - QA funcional y observabilidad

### Modulo 3.1 - QA funcional mobile
Estado: pendiente ejecucion con dispositivos.

Checklist minimo:
- Landing -> JUEGA YA -> login -> /app.
- Team / Market / Ranking / Fixtures sin bloqueos.
- Reinicio de app mantiene sesion.
- Sin prompt de notificaciones (v1).

### Modulo 3.2 - Observabilidad minima
Estado: pendiente.

Checklist minimo:
- Captura de errores cliente mobile.
- Metricas de fallos de login/API.
- Alertas backend para 5xx y `db_unavailable`.

## Etapa 4 - iOS y push v1.1

### Modulo 4.1 - Pipeline iOS
Estado: bloqueado por cuentas/certs.

Pendientes:
- Apple Developer activo.
- Certificados y provisioning profiles.
- Validacion TestFlight internal.

### Modulo 4.2 - Push v1.1
Estado: pendiente.

Pendientes:
- Android FCM release (`google-services.json`).
- iOS APNs + entitlements + `GoogleService-Info.plist`.
- Reactivar `NEXT_PUBLIC_PUSH_ENABLED=true` en perfiles compatibles.

## Comandos operativos recomendados

Build QA + sync:
```
cd frontend
npm run build:mobile:qa
```

AAB QA (Play Internal):
```
cd frontend
npm run android:release:qa
```

AAB PROD:
```
cd frontend
npm run android:release:prod
```

## Criterio de salida para Android v1
- App instalable desde Play Internal.
- Flujo end-to-end operativo en QA backend.
- Sin push activo en UI.
- Sin P0/P1 en matriz de QA.

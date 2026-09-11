# Symfony gateway

Pasarela Symfony mínima para introducir una entrada pública delante del backend Python de Training Online. La fase 3 añade un proxy autenticado y de solo lectura para exponer el perfil de la sesión Python existente.

Python sigue siendo la fuente de verdad de persistencia, importación FIT/TCX/GPX, parseo GPX, planificación, vinculación de sesiones y cálculo determinista de cumplimiento.

## Inicio local

```bash
composer install
cp .env.example .env
php -S 127.0.0.1:8080 -t public public/index.php
```

El backend Python debe estar disponible en la URL configurada para probar `/health/ready`.

## Variables de entorno

- `APP_ENV`: entorno Symfony (`dev`, `test` o `prod`).
- `APP_SECRET`: secreto local de Symfony; sustituir el valor de ejemplo fuera de pruebas.
- `PYTHON_API_BASE_URL`: URL interna/base del backend Python, sin `/api` final.
- `PYTHON_HTTP_CONNECT_TIMEOUT`: timeout de conexión en segundos.
- `PYTHON_HTTP_READ_TIMEOUT`: timeout de espera de respuesta en segundos.
- `PYTHON_SESSION_COOKIE_NAME`: nombre de la cookie de sesión Python permitida. El backend actual no establece `session_cookie` en `SessionMiddleware`, por lo que su valor efectivo de Starlette es `session`; se declara explícitamente aquí y no se interpreta en Symfony.

No se configuran credenciales de usuario, JWT, cookies, `user_id`, base de datos ni almacenamiento de archivos en esta fase.

## Endpoints

- `GET /health`: liveness local. Siempre responde `200` si Symfony puede procesar la petición; no llama a Python.
- `GET /health/ready`: readiness. Llama a `GET {PYTHON_API_BASE_URL}/api/health`. Devuelve `200` si Python responde con HTTP 200 y JSON `{ "status": "ok" }`; en cualquier error devuelve `503` sin revelar detalles internos.
- `GET /api/auth/session`: proxy transparente de solo lectura a `GET {PYTHON_API_BASE_URL}/api/auth/session`. Reenvía únicamente la cookie configurada y devuelve el JSON `UserRead` o los errores semánticos `401`, `403`, `404` y `422` de Python.
- `GET /api/profile`: proxy transparente de solo lectura a `GET {PYTHON_API_BASE_URL}/api/profile`. Reutiliza la cookie de sesión permitida, devuelve sin transformar el JSON `AthleteProfileRead` y conserva los errores semánticos `401`, `403`, `404` y `422` de Python. Incluye `Cache-Control: private, no-store` y no usa caché compartida.

Los endpoints devuelven JSON. Readiness y el proxy de sesión preservan un `X-Request-Id` válido o generan uno seguro, lo propagan al upstream y lo devuelven al cliente. El proxy descarta cookies no permitidas y solo reenvía `Set-Cookie` si pertenece a la cookie de sesión configurada, conservando sus atributos de seguridad.

## Modelo de sesión

La sesión es transparente: Symfony no deserializa la cookie firmada de Starlette, no crea una sesión PHP y no consulta la base de datos. Python continúa resolviendo la identidad mediante su cookie de sesión y `get_current_user()`, por lo que Python conserva la autoridad final de autenticación y autorización. Symfony no autoriza ni persiste perfiles.

Symfony no acepta identidad desde query string, body, `Authorization`, JWT, `X-User-Id`, `X-Forwarded-User` u otras cabeceras. Tampoco reenvía el encabezado `Cookie` original completo: extrae mediante el parser de cookies del framework solo la cookie cuyo nombre coincide con `PYTHON_SESSION_COOKIE_NAME`.

## Alcance excluido

No se migran rutas de negocio `/api`, login, registro, logout, JWT, identidad interna firmada, HMAC/mTLS, operaciones de escritura, lógica de negocio, entidades Doctrine, migraciones, PostgreSQL, archivos de usuario, almacenamiento Symfony ni Python, ni frontend.

## Siguiente fase

La fase 4 podrá abordar lecturas de objetivos o actividades, previa definición del contrato y sus límites. Todavía no están implementados login, logout, JWT, identidad interna firmada, HMAC/mTLS ni operaciones de negocio.

## Rollback

El frontend sigue apuntando directamente al backend Python mediante `VITE_API_URL`. Para revertir esta fase basta con no publicar las rutas Symfony `/api/auth/session` y `/api/profile` o retirar el gateway del tráfico; no es necesario cambiar usuarios, sesiones, frontend ni contratos Python.

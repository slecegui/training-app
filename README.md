# Training Online

Training Online es un planificador ciclista multiusuario. Esta entrega cierra los hitos
verticales: **Planificación Semanal**, **Vinculación plan–realizado** y **Cumplimiento Determinista y Explicable**. Cuenta con persistencia versionada de planes, resultados y compliance,
reglas de negocio deterministas en Python, API autenticada, interfaz de usuario interactiva,
migraciones Alembic y un robusto conjunto de pruebas unitarias y de aislamiento de datos. La integración avanzada con IA aún está pendiente.

## Requisitos y puesta en marcha

- Docker y Docker Compose, o Python 3.12, PostgreSQL y Node.js 20 o superior.
- Copia `.env.example` a `.env` y cambia al menos `POSTGRES_PASSWORD` y `SESSION_SECRET`.

```bash
cp .env.example .env
docker compose up --build -d
```

La aplicación queda en `http://localhost:5173` y la API en `http://localhost:8000`. Compose
aplica `alembic upgrade head` antes de arrancar el backend. La cookie de sesión se envía entre
el frontend y la API; en producción debe configurarse `SESSION_HTTPS_ONLY=true` y usarse HTTPS.

## Funcionalidad disponible

- Registro, inicio, consulta y cierre de sesión.
- Perfil por usuario con deportes, nivel, disponibilidad, zonas, preferencias y limitaciones.
- Creación, consulta, actualización, activación y eliminación de objetivos. Solo puede haber un
  objetivo activo por usuario.
- Importación FIT/TCX/GPX y consulta de actividades del usuario autenticado.
- Planificación semanal determinista: Generación de planes de la semana siguiente mediante un pipeline de reglas estructuradas que respetan la disponibilidad del usuario, nivel, equipamiento (potenciómetro explícito) y proximidad del objetivo.
- Persistencia versionada e histórica: Generación de versiones correlativas aisladas por usuario, permitiendo consultar históricos y manteniendo un único plan activo por semana de forma atómica.
- Vinculación plan–realizado: Registro de estados completado, omitido, parcial o sustituido para cada sesión, vinculación de actividades reales e historial correlativo de correcciones de manera insert-only.
- Cumplimiento determinista y explicable: Cálculo semanal y acumulado por objetivo del cumplimiento basado en duraciones de forma 100% determinista en Python (ruleset `duration-v1`), con precisión Decimal, fingerprints canónicos para idempotencia e historial de revisiones.
- Aislamiento de perfiles, objetivos, actividades y metadatos de archivos por identidad de
  sesión. Los endpoints de producción no toman `user_id` del cliente.

Los archivos originales se guardan en el directorio configurado por `UPLOAD_DIR`, excluido de
Git. Los formatos inválidos o ilegibles se rechazan y no conservan el archivo fallido.

## Desarrollo sin Docker

```bash
cd backend
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

En otra terminal:

```bash
cd frontend
npm ci
npm run dev
```

## Controles de calidad

```bash
cd backend
ruff format --check .
ruff check .
pytest

cd ../frontend
npm run lint
npm run build
```

Las pruebas backend cubren autenticación, acceso protegido, perfil, objetivos, aislamiento entre
usuarios, importación de actividades, aislamiento de sus registros/archivos, parsing GPX,
planificación semanal por pipeline, persistencia de planes/sesiones, versionado e idempotencia,
vinculación plan-realizado (modelo versionado insert-only) y cumplimiento determinista semanal y por objetivo (precisiones Decimal, redondeo ROUND_HALF_UP, fingerprints canónicos y consistencias de checks en BD).

## Fuera de esta entrega

La base de conocimiento situada en `backend/app/coaching/knowledge/` y su endpoint protegido de
depuración son preparación previa; no invocan ningún proveedor de IA. No se consideran terminados
el análisis avanzado de carga o recuperación, ni la configuración de proveedores e integración con IA por usuario.

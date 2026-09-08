# Training Online

Primera versión ejecutable para importar y consultar actividades deportivas. Incluye API FastAPI, React + Vite, PostgreSQL, migraciones Alembic y almacenamiento local de archivos originales.

## Requisitos

- Node.js 20 o superior
- Docker y Docker Compose

## Puesta en marcha local

Copiar las variables de ejemplo y ajustar `POSTGRES_PASSWORD`:

```bash
cp .env.example .env
```

Construir e iniciar todos los servicios:

```bash
docker compose up --build -d
```

Abrir `http://localhost:5173`. La interfaz carga tres actividades de demostración para el usuario con id `1`; no hace falta importar archivos para revisar el recorrido. La API queda en `http://localhost:8000` y su health check en `http://localhost:8000/api/health`.

Para ver logs:

```bash
docker compose logs -f backend frontend
```

## Recorrido y API

- Selecciona **Importar FIT, TCX o GPX** en la interfaz. El archivo se guarda en `storage/uploads/`, directorio excluido de Git.
- `GET /api/activities?user_id=1` lista exclusivamente las sesiones de ese usuario.
- `GET /api/activities/{id}?user_id=1` obtiene un detalle, manteniendo ese aislamiento hasta que exista autenticación.
- `POST /api/activities/import?user_id=1` recibe un multipart `file` FIT, TCX o GPX y extrae fecha, nombre, deporte, duración, distancia, desnivel, frecuencia cardiaca, potencia, cadencia y calorías cuando el formato las contiene.

Las métricas no presentes en un archivo se conservan como vacías. GPX y TCX se leen con la biblioteca XML estándar; FIT con `fitdecode`.

## Desarrollo sin Docker

Se requiere Python 3.12 y PostgreSQL. Configura `DATABASE_URL` en `.env`, instala el backend (`pip install -e '.[dev]'`), aplica `alembic upgrade head` desde `backend/` y ejecuta el seed indicado en el comando de Compose. Para el frontend: `cd frontend && npm install && npm run dev`.

Vite mostrará la URL local, normalmente `http://localhost:5173`.

## Controles de calidad

```bash
cd frontend && npm run lint && npm run build
cd backend && ruff check . && pytest
```

No se incluye entrenador IA ni planificación automática en esta entrega.

# Plan: Formulario de Objetivos Estructurado

## Background & Motivation
Sustituir las entradas de texto libre en la pantalla "Objetivos" por selectores cerrados, controles numéricos específicos con unidades y una validación robusta y coherente entre el frontend y el backend, preservando la compatibilidad con objetivos legacy.

## Scope & Impact
- **Database:** Añadir las columnas `success_metric_type`, `success_metric_value` y `success_metric_unit` a la tabla `goals`. Generar una migración Alembic correspondiente.
- **Backend Schemas:** Validadores estrictos en `schemas.py` para asegurar que el deporte, el tipo de objetivo, la prioridad y la combinación de métrica de éxito sean válidas, con límites de valores reales. Generación determinista del string `success_metric` en el backend.
- **Frontend Form:** Rediseño completo de la sección "Objetivos" en `App.tsx` agrupando en secciones ("Objetivo", "Resultado esperado" y "Recorrido") y agregando controles numéricos específicos para cada métrica seleccionada.
- **Planner & Compatibility:** Asegurar que `planner.py` siga funcionando de forma transparente con los nuevos códigos canónicos (ej. traduciendo deportes a etiquetas legibles para los títulos de entrenamiento).

## Proposed Solution

### 1. Persistence (Models & Migrations)
Agregar las siguientes columnas en `backend/app/models.py` para la clase `Goal`:
- `success_metric_type`: String(80), nullable
- `success_metric_value`: Float, nullable
- `success_metric_unit`: String(30), nullable

Generar la migración de Alembic para actualizar la base de datos de producción.

### 2. Backend Validation (`schemas.py`)
- Tipos de objetivo válidos: `sportive`, `race`, `climb`, `endurance`, `ftp_improvement`, `health`.
- Deportes ciclistas válidos: `cycling_general`, `road_cycling`, `mountain_biking`, `gravel`, `indoor_cycling`, `cyclocross`, `track_cycling`.
- Validadores para `title`: trim automático, longitud [2, 120] y rechazar cadenas de puros espacios.
- Validador de consistencia: La `success_metric_type` y la `success_metric_unit` deben corresponder de forma lógica con el `goal_type` elegido (ej. `ftp_objetivo` solo para `ftp_improvement`).
- El backend construirá automáticamente la cadena `success_metric` (para compatibilidad de lectura legacy) según los valores numéricos y la unidad estructurada recibida.

### 3. Frontend Redesign (`App.tsx`)
- Sustituir campos abiertos por selectores para Tipo, Deporte y Prioridad con etiquetas amigables en español.
- Formulario dividido en secciones accesibles (labels explícitas, `aria-describedby` para ayudas y errores inline).
- Al cambiar el tipo de objetivo se limpian y actualizan dinámicamente las métricas de éxito permitidas.
- Mostrar inputs numéricos con step y unidades fijas (ej. km, W, %, horas/minutos separados) según la métrica seleccionada.
- Bloquear envíos inválidos, mostrar contadores de caracteres para Nombre (detalles) y resetear a estados limpios y válidos tras creación.

## Alternativa Considerada
- *Mantener base de datos idéntica sin columnas estructuradas y parsear JSON en success_metric:* Descartado para favorecer la auditoría y persistencia limpia de datos directamente en el esquema SQL de `goals`.

¿Estás de acuerdo con este plan breve y la migración correspondiente para proceder con el desarrollo?
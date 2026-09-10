# Roadmap de Training Online

Un hito solo se marca completo cuando tiene migración aplicable, reglas o servicios necesarios,
API autenticada, interfaz, pruebas de comportamiento y aislamiento, y calidad en verde.

| Hito | Estado auditado | Evidencia y trabajo pendiente |
| --- | --- | --- |
| Autenticación, perfiles, objetivos y actividades | Completo | Sesión local, UI, CRUD de perfil y objetivos, objetivo activo único, importación FIT/TCX/GPX y consultas por identidad autenticada. Pruebas API verifican comportamiento, validación, archivos y aislamiento entre dos usuarios; migraciones comprobadas desde base vacía. |
| Planificación semanal | Completo | Planes semanales y sesiones persistidos. Algoritmo determinista de reglas estructurado en un pipeline en Python (fecha de corte, límites ISO, zonas dinámicas, distribución de carga y recuperación). API autenticada e interfaz funcional con trazabilidad. |
| Vinculación plan–realizado | Completo | Vinculación de PlannedSession con Activity (completed, partial, replaced) o registro sin actividad (omitted) con explicaciones obligatorias. Modelo de correcciones insert-only versionado con revisiones incrementadas y desactivación atómica. |
| Cumplimiento | Completo | Cálculo de cumplimiento semanal y por objetivo en base a duraciones de forma 100% determinista en Python mediante Decimal y ROUND_HALF_UP. Persistencia versionada insert-only, fingerprints canónicos para idempotencia y desglose de componentes. |
| Versionado e histórico | Completo | Versiones correlativas de planes generadas de forma atómica y aislada por usuario. Historial de versiones consultable desde la interfaz de forma interactiva y regeneración explícita con tracking. |
| IA por usuario | Pendiente | El contexto y conocimiento local son solo preparación. No hay proveedor por usuario, gestión segura de claves, llamada IA ni validación de propuestas. |
| Endurecimiento para producción | Pendiente | Faltan HTTPS/despliegue seguro, límites de carga, observabilidad sin datos sensibles, gestión externa de secretos y revisión operativa de dependencias. |

## Siguiente hito

La siguiente entrega puede abordar la **IA por usuario** o la **Gestión avanzada de carga o recuperación** basada en métricas de entrenamiento.

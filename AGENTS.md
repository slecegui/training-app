# Instrucciones persistentes

- Codex debe usar siempre la skill Graphify al analizar o modificar este repositorio. Antes de trabajar, debe consultar el grafo existente. Después de cambios materiales, debe ejecutar `/graphify . --update` para mantener `graphify-out` actualizado.
- Training Online es un planificador ciclista multiusuario, no solo un visor de actividades. Toda decisión de producto, diseño y cambio debe conservar esta dirección.
- El alcance funcional persistente es: perfil por usuario (disponibilidad, zonas, preferencias, limitaciones y proveedor IA propio), objetivos con fecha, tipo, distancia y desnivel opcionales, prioridad y métrica de éxito; importación FIT/TCX/GPX; planificación de la semana siguiente desde el último entrenamiento y objetivo activo; y vinculación de cada sesión planificada con una actividad realizada o los estados omitida, sustituida o parcial.
- Los porcentajes de cumplimiento semanal y por objetivo deben calcularse y validarse en Python mediante reglas deterministas, trazables y explicables. La IA solo puede proponer o explicar en una salida estructurada validada; nunca es la fuente de cálculo, autorización ni persistencia de hechos.
- Los planes deben versionarse y mantener histórico por semana y objetivo de planificado frente a realizado, cambios y decisiones.
- Datos, consultas, archivos importados, credenciales y proveedor IA se aíslan estrictamente por usuario. La identidad autenticada debe determinar el usuario efectivo; no se acepta un `user_id` controlado por el cliente como frontera de seguridad en funcionalidades de producción.
- No se considera un hito completo por disponer solo de modelos, esquemas o migraciones: exige migración aplicable, servicio/reglas, endpoint autenticado, interfaz cuando corresponda y pruebas de comportamiento y aislamiento.
- Preservar cambios existentes del árbol de trabajo. Antes de cambios materiales, inspeccionar el estado con Git; después, actualizar Graphify y ejecutar las comprobaciones aplicables de backend, frontend, migraciones, servicios y endpoints.

# Repository instructions

- Before answering questions about the codebase or making code changes, use Graphify as the first discovery step. If `graphify-out/graph.json` exists, query it; otherwise build or update the graph as permitted by the environment, then use it to trace the relevant flow. Report any environment limitation that prevents Graphify extraction.
- When the user requests commits, use an English Conventional Commit-style message in the format `type(scope): description`, where `type` describes the change and `scope` identifies the affected module or domain. Example: `feat(sga): require approval for outbound orders`.
- Stage and commit only files modified for the requested task. Never include unrelated or pre-existing worktree changes.

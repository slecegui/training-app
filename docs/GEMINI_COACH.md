# Entrenador remoto: primera integración

El backend conserva la identidad, los datos privados, la metodología y las reglas del plan.
`POST /api/coaching/plan-preview` acepta `reference_date` como `/api/plans/generate`, requiere
la sesión autenticada y no crea ni modifica planes. Python fija semana, días, duración, métrica
y zona; Gemini propone el texto, la estructura y el criterio de ajuste de cada sesión.
La respuesta contiene `preview_only: true`, modelo, versiones de metodología/instrucciones y
contadores de uso devueltos por Google. Si Gemini cambia los días o devuelve JSON inválido,
la propuesta se rechaza. Esta vista previa no constituye un plan publicado ni verifica
automáticamente todas las afirmaciones clínicas o deportivas de texto libre.

Configurar `GEMINI_API_KEY` como secreto del servidor y, opcionalmente,
`GEMINI_MODEL=gemini-2.5-flash-lite` (valor predeterminado). Nunca poner la clave en el frontend o el repositorio. Sin clave,
el endpoint responde 503 y el planificador determinista existente sigue disponible.

La instrucción versionada está en `backend/app/coaching/coach-v1.md`. Las referencias temáticas
de `backend/app/coaching/knowledge/` son la metodología compartida; `ContextBuilder` selecciona
solo las pertinentes para `plan`. El perfil personal, CSV, FIT y PDF de la skill local de Codex
no se copian al backend. Para publicar propuestas de IA en un hito posterior harán falta reglas
deterministas que validen también la estructura de cada intervalo y una evaluación de casos
reales antes de incorporar el proveedor al flujo de versionado.

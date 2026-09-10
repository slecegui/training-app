# Training Online — producto

## Propósito y flujo

Training Online es un planificador ciclista multiusuario. Cada persona administra un perfil
deportivo y un proveedor de IA propio, importa entrenamientos y define objetivos. El sistema
elige el objetivo activo y el último entrenamiento válido como corte para generar un borrador
versionado de la semana siguiente. Python valida las reglas y calcula resultados; la IA solo
puede devolver una propuesta estructurada y una explicación. La persona confirma o ajusta el
plan y, después de entrenar, relaciona cada sesión con una actividad importada o registra que
fue omitida, sustituida o parcial. El resultado se conserva en un histórico consultable por
semana y objetivo.

Flujo verificable:

1. Una identidad autenticada accede únicamente a sus datos y secretos.
2. Completa su perfil: disponibilidad, zonas, preferencias, limitaciones y configuración de
   proveedor IA por usuario.
3. Crea o activa un objetivo con fecha, tipo, prioridad, métrica de éxito y, opcionalmente,
   distancia y desnivel.
4. Importa FIT, TCX o GPX; Python normaliza y valida sus métricas.
5. El planificador toma el último entrenamiento y el objetivo activo, determina la semana
   inmediatamente siguiente y guarda una nueva versión del plan.
6. Cada sesión se vincula a una actividad realizada o recibe un estado terminal y, cuando
   procede, su sustitución o ejecución parcial.
7. Python calcula cumplimiento semanal y del objetivo, y el histórico enseña plan, resultado,
   cambios y decisiones.

## Entidades y propiedad

| Entidad | Campos mínimos | Propiedad / relación |
| --- | --- | --- |
| Usuario | identidad, nombre | raíz del aislamiento |
| Perfil ciclista | disponibilidad, zonas de potencia/FC/RPE, preferencias, limitaciones | uno por usuario |
| Configuración IA | proveedor, modelo, secreto referenciado/cifrado, configuración | una o más por usuario; nunca visible a otro |
| Objetivo | tipo, fecha, distancia opcional, desnivel opcional, prioridad, métrica de éxito, estado | pertenece a un usuario |
| Actividad | archivo origen, inicio, deporte y métricas normalizadas | pertenece a un usuario |
| Plan semanal | usuario, objetivo, lunes de semana, versión, estado, corte de actividad | pertenece a un usuario y objetivo |
| Sesión planificada | fecha, intención, estructura, carga/volumen objetivo, zonas | pertenece a una versión de plan |
| Resultado de sesión | actividad vinculada o estado `omitted`, `replaced` o `partial`, motivo y sustituta | uno por sesión planificada |
| Decisión | entrada mínima, salida estructurada validada, explicación, actor y fecha | pertenece a un usuario y referencia un plan/sesión |
| Resumen de cumplimiento | componentes, numerador, denominador, porcentaje y versión de regla | derivado reproducible por semana y objetivo |

## Reglas de dominio

- La semana objetivo es la semana ISO inmediatamente posterior a la fecha/hora del último
  entrenamiento del usuario; si no existe, se exige una fecha de corte explícita. El plan usa
  solo el objetivo activo de mayor prioridad y, ante empate, la fecha más próxima.
- Un plan ya publicado no se muta: un cambio crea una versión posterior que conserva el motivo,
  autor, momento y la versión de origen. Las sesiones de una versión permanecen inmutables.
- Una sesión puede terminar exactamente en uno de estos estados: `completed` (actividad
  vinculada), `omitted`, `replaced` o `partial`. Una sustitución referencia la sesión que
  reemplaza; una actividad no puede acreditar sesiones de usuarios distintos.
- Python comprueba propiedad, fechas, estado, disponibilidad, limitaciones y formato de la
  propuesta IA antes de persistir. Ninguna respuesta de IA ejecuta acciones o cambia hechos por
  sí sola.
- La IA recibe el mínimo contexto del mismo usuario, devuelve JSON conforme a un esquema de
  propuesta y puede explicar restricciones o alternativas. Claves de proveedor se guardan fuera
  de respuestas, logs y contextos; se cifran o se referencian en un gestor de secretos.

## Cumplimiento determinista y explicable

Cada sesión tiene un peso positivo explícito (por defecto, minutos planificados; si una métrica
de éxito del objetivo define otro peso, se usa esa métrica). Para cada sesión, Python calcula
un crédito entre 0 y 1: `1` si está completada y validada, `0` si fue omitida, el porcentaje
validado de volumen/intensidad si es parcial y el crédito definido por la regla de sustitución
si fue sustituida. El porcentaje semanal es:

`100 × suma(peso_de_sesión × crédito) / suma(peso_de_sesión)`.

El porcentaje por objetivo usa el mismo cálculo sobre las sesiones de sus planes dentro del
periodo solicitado. El resultado almacena los pesos, créditos, exclusiones justificadas,
versión de regla, sesión y actividad de origen; por ello se puede recomputar y explicar sin IA.
No hay denominador cero: se devuelve `not_applicable` con explicación.

## Criterios de aceptación verificables

- Dos usuarios autenticados no pueden listar, consultar, enlazar, descargar ni incluir en un
  contexto IA recursos, archivos, planes, decisiones o claves del otro; hay pruebas de API y
  servicio para ello.
- Se pueden crear objetivos válidos con todos los campos requeridos y opcionales, y solo uno
  queda activo tras aplicar la regla explícita de activación/prioridad.
- FIT, TCX y GPX válidos crean actividades normalizadas del usuario autenticado; archivos no
  permitidos o ilegibles producen errores sin conservar el archivo temporal.
- Con último entrenamiento y objetivo activo, una petición genera la siguiente semana ISO, una
  versión inicial y sesiones que respetan disponibilidad y limitaciones; sin datos de corte se
  obtiene un error accionable o se usa la fecha explícita documentada.
- Vincular una actividad a una sesión actualiza su estado y rechaza actividades ajenas, enlaces
  duplicados incompatibles y transiciones de estado inválidas.
- Un conjunto de sesiones completada, omitida, sustituida y parcial produce el porcentaje
  esperado y expone numerador, denominador y créditos en API y en el histórico.
- Cambiar un plan conserva la versión anterior y permite consultar por semana y objetivo las
  versiones, resultados, decisiones y motivos de cambio.
- Un proveedor IA por usuario solo acepta salida estructurada validada; claves no aparecen en
  respuestas, logs, decisiones ni contextos.

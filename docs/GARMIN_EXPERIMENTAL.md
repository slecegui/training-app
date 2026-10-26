# Garmin Connect: descarga experimental

Training Online puede importar actividades de Garmin Connect mediante la biblioteca comunitaria `python-garminconnect`. Es una conexión no oficial a servicios privados de Garmin: puede fallar por cambios de autenticación, límites o cambios en los datos. Garmin restringe la extracción automatizada en sus condiciones de uso. Mantén disponible la importación manual FIT, TCX y GPX.

## Activación

1. Configura `GARMIN_TOKEN_KEY` con una clave Fernet persistente. Genera una con `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Guárdala en el gestor de secretos del despliegue; si se pierde o cambia, cada usuario deberá volver a conectar Garmin.
2. Instala las dependencias del backend y aplica `alembic upgrade head`.
3. Cada usuario abre Actividades y conecta su propia cuenta. La contraseña solo se usa durante el inicio de sesión y no se guarda. Si Garmin solicita MFA, el código debe introducirse en cinco minutos y en el mismo proceso de backend. Tras reiniciar el backend se debe iniciar de nuevo el proceso de conexión.

La app cifra el token de sesión en `garmin_connections`, vinculado a la identidad autenticada. No acepta un `user_id` enviado por el navegador. La descarga consulta hasta las 100 actividades más recientes, conserva el archivo original y evita duplicados por identificador de Garmin y usuario. Sincroniza al abrir Actividades cuando han pasado al menos 24 horas desde la última sincronización, o al pulsar «Sincronizar ahora». No sincroniza en segundo plano cuando nadie abre la página.

Desconectar elimina el token almacenado en Training Online y conserva las actividades ya importadas. La eliminación local no revoca por sí misma una sesión que Garmin haya emitido; la revocación debe hacerse desde la cuenta de Garmin. No se envían datos de Garmin al proveedor de IA para calcular cumplimiento: los hechos importados pasan por las reglas deterministas existentes.

## Comprobaciones

Prueba con una cuenta de prueba antes de habilitarla para usuarios reales. Verifica conexión normal y con MFA, importación repetida sin duplicados, fallo de Garmin con retorno a importación manual y aislamiento entre dos usuarios. No uses cuentas reales en las pruebas automatizadas.

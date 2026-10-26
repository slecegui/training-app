"""Optional, experimental Garmin Connect import through an unofficial client."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from threading import Lock
from uuid import uuid4
from zipfile import BadZipFile, ZipFile, is_zipfile

from cryptography.fernet import Fernet, InvalidToken
from garminconnect import Garmin
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Activity, GarminConnection
from app.services.activity_parser import parse_activity_file

MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_ACTIVITY_BYTES = 20 * 1024 * 1024
_pending: dict[int, tuple[Garmin, datetime]] = {}
_pending_lock = Lock()


class GarminUnavailable(Exception):
    """The experimental connection cannot be used right now."""


def _cipher() -> Fernet:
    key = get_settings().garmin_token_key
    if not key:
        raise GarminUnavailable("La conexión experimental con Garmin no está configurada.")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as error:
        raise GarminUnavailable("La clave de cifrado de Garmin no es válida.") from error


def available() -> bool:
    try:
        _cipher()
        return True
    except GarminUnavailable:
        return False


def _save_connection(db: Session, user_id: int, client: Garmin) -> None:
    tokens = client.client.dumps()
    connection = db.scalar(select(GarminConnection).where(GarminConnection.user_id == user_id))
    if connection is None:
        connection = GarminConnection(user_id=user_id, encrypted_tokens="")
        db.add(connection)
    connection.encrypted_tokens = _cipher().encrypt(tokens.encode()).decode()
    connection.last_error = None
    db.commit()


def connect(db: Session, user_id: int, email: str, password: str) -> str:
    _cipher()
    if not email.strip() or not password:
        raise GarminUnavailable("Indica el correo y la contraseña de Garmin.")
    client = Garmin(email.strip(), password, return_on_mfa=True, retry_attempts=0)
    try:
        status, _ = client.login()
    except Exception as error:
        raise GarminUnavailable("Garmin no ha permitido iniciar sesión. Revisa las credenciales o inténtalo más tarde.") from error
    if status == "needs_mfa":
        client.password = None
        with _pending_lock:
            _pending[user_id] = (client, datetime.now(timezone.utc) + timedelta(minutes=5))
        return "needs_mfa"
    _save_connection(db, user_id, client)
    return "connected"


def finish_mfa(db: Session, user_id: int, code: str) -> None:
    with _pending_lock:
        pending = _pending.get(user_id)
    if not pending or pending[1] < datetime.now(timezone.utc):
        with _pending_lock:
            _pending.pop(user_id, None)
        raise GarminUnavailable("El código ha caducado. Inicia de nuevo la conexión.")
    if not code.strip():
        raise GarminUnavailable("Indica el código de verificación de Garmin.")
    try:
        pending[0].resume_login({}, code.strip())
        _save_connection(db, user_id, pending[0])
    except Exception as error:
        raise GarminUnavailable("No se pudo verificar el código de Garmin.") from error
    with _pending_lock:
        _pending.pop(user_id, None)


def disconnect(db: Session, user_id: int) -> None:
    with _pending_lock:
        _pending.pop(user_id, None)
    connection = db.scalar(select(GarminConnection).where(GarminConnection.user_id == user_id))
    if connection:
        db.delete(connection)
        db.commit()


def _activity_file(payload: bytes) -> tuple[str, bytes]:
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("Archivo de Garmin demasiado grande")
    if not is_zipfile(BytesIO(payload)):
        if len(payload) > MAX_ACTIVITY_BYTES:
            raise ValueError("Actividad de Garmin demasiado grande")
        return "fit", payload
    try:
        with ZipFile(BytesIO(payload)) as archive:
            candidates = sorted(
                (item for item in archive.infolist() if Path(item.filename).suffix.lower() in {".fit", ".tcx", ".gpx"}),
                key=lambda item: {".fit": 0, ".tcx": 1, ".gpx": 2}[Path(item.filename).suffix.lower()],
            )
            if not candidates or candidates[0].file_size > MAX_ACTIVITY_BYTES:
                raise ValueError("El archivo de Garmin no contiene una actividad compatible")
            item = candidates[0]
            with archive.open(item) as extracted:
                data = extracted.read(MAX_ACTIVITY_BYTES + 1)
            if len(data) > MAX_ACTIVITY_BYTES:
                raise ValueError("Actividad de Garmin demasiado grande")
            return Path(item.filename).suffix.lower().lstrip("."), data
    except BadZipFile as error:
        raise ValueError("Archivo de Garmin no válido") from error


def sync(db: Session, user_id: int, upload_dir: Path) -> dict[str, int]:
    connection = db.scalar(select(GarminConnection).where(GarminConnection.user_id == user_id))
    if connection is None:
        raise GarminUnavailable("Conecta primero tu cuenta de Garmin.")
    try:
        tokens = _cipher().decrypt(connection.encrypted_tokens.encode()).decode()
    except InvalidToken as error:
        raise GarminUnavailable("No se puede leer la conexión. Vuelve a conectar Garmin.") from error
    client = Garmin(retry_attempts=0)
    try:
        client.login(tokens)
        imported = skipped = failed = 0
        upload_dir.mkdir(parents=True, exist_ok=True)
        for offset in range(0, 100, 20):
            items = client.get_activities(start=offset, limit=20)
            if not isinstance(items, list):
                raise ValueError("Respuesta de actividades no válida")
            if not items:
                break
            page_new = 0
            for item in items:
                external_id = str(item.get("activityId") or "") if isinstance(item, dict) else ""
                if not external_id.isdigit() or len(external_id) > 100:
                    failed += 1
                    continue
                exists = db.scalar(
                    select(Activity.id).where(
                        Activity.user_id == user_id,
                        Activity.source_provider == "garmin",
                        Activity.external_activity_id == external_id,
                    )
                )
                if exists:
                    skipped += 1
                    continue
                page_new += 1
                destination = None
                try:
                    raw = client.download_activity(
                        external_id, dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL
                    )
                    extension, data = _activity_file(raw)
                    destination = upload_dir / f"{uuid4().hex}.{extension}"
                    destination.write_bytes(data)
                    parsed = parse_activity_file(destination, extension)
                    parsed["name"] = str(item.get("activityName") or parsed["name"])[:255]
                    db.add(
                        Activity(
                            user_id=user_id,
                            original_filename=f"garmin-{external_id}.{extension}",
                            stored_filename=destination.name,
                            source_format=extension,
                            source_provider="garmin",
                            external_activity_id=external_id,
                            **parsed,
                        )
                    )
                    db.commit()
                    imported += 1
                except Exception:
                    db.rollback()
                    if destination:
                        destination.unlink(missing_ok=True)
                    failed += 1
            if page_new == 0 or len(items) < 20:
                break
        connection.encrypted_tokens = _cipher().encrypt(client.client.dumps().encode()).decode()
        connection.last_sync_at = datetime.now(timezone.utc)
        connection.last_error = "Algunas actividades no se pudieron importar." if failed else None
        db.commit()
        return {"imported": imported, "skipped": skipped, "failed": failed}
    except GarminUnavailable:
        raise
    except Exception as error:
        db.rollback()
        connection.last_error = "La sincronización con Garmin ha fallado. Vuelve a intentarlo."
        db.commit()
        raise GarminUnavailable(connection.last_error) from error

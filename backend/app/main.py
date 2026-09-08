"""FastAPI application."""

from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Activity, User
from app.schemas import ActivityRead
from app.services.activity_parser import parse_activity_file

app = FastAPI(title="Training Online API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def user_or_404(user_id: int, db: Session) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    return user


@app.get("/api/activities", response_model=list[ActivityRead], tags=["activities"])
def list_activities(user_id: int = 1, db: Session = Depends(get_db)) -> list[Activity]:
    user_or_404(user_id, db)
    return list(
        db.scalars(
            select(Activity).where(Activity.user_id == user_id).order_by(Activity.started_at.desc())
        )
    )


@app.get("/api/activities/{activity_id}", response_model=ActivityRead, tags=["activities"])
def get_activity(activity_id: int, user_id: int = 1, db: Session = Depends(get_db)) -> Activity:
    activity = db.scalar(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == user_id)
    )
    if not activity:
        raise HTTPException(404, "Actividad no encontrada")
    return activity


@app.post(
    "/api/activities/import", response_model=ActivityRead, status_code=201, tags=["activities"]
)
async def import_activity(
    user_id: int = 1, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> Activity:
    user_or_404(user_id, db)
    extension = Path(file.filename or "").suffix.lower().lstrip(".")
    if extension not in {"fit", "tcx", "gpx"}:
        raise HTTPException(400, "Solo se admiten archivos FIT, TCX y GPX")
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.{extension}"
    destination = upload_dir / stored_name
    destination.write_bytes(await file.read())
    try:
        data = parse_activity_file(destination, extension)
    except Exception as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, f"No se pudo leer el archivo: {error}") from error
    activity = Activity(
        user_id=user_id,
        original_filename=file.filename,
        stored_filename=stored_name,
        source_format=extension,
        **data,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity

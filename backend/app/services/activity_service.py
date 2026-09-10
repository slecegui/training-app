"""Ownership-safe activity deletion rules."""

from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, PlannedSessionResult, User


class ActivityService:
    """Keeps historical plan/result evidence intact when activities are removed."""

    def delete(self, activity_id: int, user: User, db: Session, upload_dir: Path) -> None:
        activity = db.scalar(
            select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
        )
        if not activity:
            raise HTTPException(404, "Actividad no encontrada")
        linked = db.scalar(
            select(PlannedSessionResult.id).where(PlannedSessionResult.activity_id == activity.id)
        )
        if linked:
            raise HTTPException(
                409,
                "No se puede eliminar una actividad vinculada a una sesión planificada: conserva el histórico. Corrige o sustituye primero el resultado de la sesión.",
            )
        stored_filename = activity.stored_filename
        db.delete(activity)
        db.commit()
        if stored_filename:
            (upload_dir / stored_filename).unlink(missing_ok=True)

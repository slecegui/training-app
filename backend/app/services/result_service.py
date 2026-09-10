"""Domain service for managing planned session results (insert-only, versioned corrections)."""

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import Activity, PlannedSession, PlannedSessionResult


class ResultServiceException(Exception):
    """Base exception for planned session result service."""

    pass


class SessionNotFoundException(ResultServiceException):
    pass


class ActivityNotFoundException(ResultServiceException):
    pass


class ActivityAlreadyLinkedException(ResultServiceException):
    pass


class InvalidResultStateException(ResultServiceException):
    pass


class ResultDomainService:
    @staticmethod
    def get_session_or_404(db: Session, session_id: int, user_id: int) -> PlannedSession:
        session = db.scalar(select(PlannedSession).where(PlannedSession.id == session_id))
        if not session or session.weekly_plan.user_id != user_id:
            raise SessionNotFoundException("Sesión de entrenamiento no encontrada.")
        return session

    @classmethod
    def get_eligible_activities(cls, db: Session, session_id: int, user_id: int) -> list[Activity]:
        # Verify ownership
        cls.get_session_or_404(db, session_id, user_id)

        # Get activities of the user that are NOT currently linked to other current results
        # Activities linked to this session's current result should be allowed (eligible)
        subq = (
            select(PlannedSessionResult.activity_id)
            .where(
                and_(
                    PlannedSessionResult.is_current.is_(True),
                    PlannedSessionResult.planned_session_id != session_id,
                    PlannedSessionResult.activity_id.is_not(None),
                )
            )
            .scalar_subquery()
        )

        query = (
            select(Activity)
            .where(
                and_(
                    Activity.user_id == user_id,
                    Activity.id.not_in(subq),
                )
            )
            .order_by(Activity.started_at.desc())
        )

        return list(db.scalars(query))

    @classmethod
    def record_result(
        cls,
        db: Session,
        session_id: int,
        user_id: int,
        status: str,
        activity_id: int | None,
        reason: str | None,
        correction_reason: str | None,
        notes: str | None,
    ) -> PlannedSessionResult:
        # 1. Fetch and validate session
        session = cls.get_session_or_404(db, session_id, user_id)

        # 2. Status check validation
        status = status.lower()
        if status not in ("completed", "omitted", "partial", "replaced"):
            raise InvalidResultStateException("Estado de resultado inválido.")

        if status == "omitted":
            if activity_id is not None:
                raise InvalidResultStateException(
                    "El estado omitido no permite vincular una actividad."
                )
        else:
            if activity_id is None:
                raise InvalidResultStateException(
                    f"El estado '{status}' requiere vincular una actividad."
                )

        if status in ("omitted", "partial", "replaced"):
            if not reason or not reason.strip():
                raise InvalidResultStateException(
                    f"El estado '{status}' requiere un motivo o explicación."
                )

        # 3. Validate activity ownership and uniqueness
        if activity_id is not None:
            activity = db.scalar(select(Activity).where(Activity.id == activity_id))
            if not activity or activity.user_id != user_id:
                raise ActivityNotFoundException("Actividad deportiva no encontrada.")

            # Validate that the activity does not belong to another goal
            if (
                activity.goal_id is not None
                and activity.goal_id != session.weekly_plan.active_goal_id
            ):
                raise InvalidResultStateException(
                    "Esta actividad ya está asignada a otro objetivo y no puede ser doblemente contabilizada."
                )

            # Auto-associate activity to the plan's goal if unassigned
            if activity.goal_id is None:
                activity.goal_id = session.weekly_plan.active_goal_id
                db.add(activity)

            # Ensure activity is not already linked to another active result
            already_linked = db.scalar(
                select(PlannedSessionResult).where(
                    and_(
                        PlannedSessionResult.activity_id == activity_id,
                        PlannedSessionResult.is_current.is_(True),
                        PlannedSessionResult.planned_session_id != session_id,
                    )
                )
            )
            if already_linked:
                raise ActivityAlreadyLinkedException(
                    "Esta actividad ya está vinculada a otra sesión de entrenamiento."
                )

        # 4. Check for existing current result (Correction)
        old_result = db.scalar(
            select(PlannedSessionResult).where(
                and_(
                    PlannedSessionResult.planned_session_id == session_id,
                    PlannedSessionResult.is_current.is_(True),
                )
            )
        )

        now = datetime.utcnow()
        if old_result:
            # This is a correction
            if not correction_reason or not correction_reason.strip():
                raise InvalidResultStateException(
                    "Se requiere especificar un motivo de corrección para modificar el resultado anterior."
                )

            # Atomic transition
            old_result.is_current = False
            db.add(old_result)

            new_result = PlannedSessionResult(
                planned_session_id=session_id,
                revision=old_result.revision + 1,
                is_current=True,
                supersedes_result_id=old_result.id,
                activity_id=activity_id,
                status=status,
                reason=reason,
                correction_reason=correction_reason,
                notes=notes,
                recorded_at=now,
                recorded_by_user_id=user_id,
                created_at=now,
            )
        else:
            # First time recording result
            new_result = PlannedSessionResult(
                planned_session_id=session_id,
                revision=1,
                is_current=True,
                supersedes_result_id=None,
                activity_id=activity_id,
                status=status,
                reason=reason,
                correction_reason=None,
                notes=notes,
                recorded_at=now,
                recorded_by_user_id=user_id,
                created_at=now,
            )

        db.add(new_result)
        db.commit()
        db.refresh(new_result)
        return new_result

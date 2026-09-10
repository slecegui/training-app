"""FastAPI application."""

from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import get_current_user, hash_password, verify_password
from app.coaching.context import ContextBuilder
from app.config import get_settings
from app.database import get_db
from app.models import (
    Activity,
    AthleteProfile,
    ComplianceSummary,
    Goal,
    PlannedSession,
    PlannedSessionResult,
    User,
    WeeklyPlan,
)
from app.schemas import (
    ActivityGoalUpdate,
    ActivityRead,
    AthleteProfileRead,
    AthleteProfileUpdate,
    CoachDebugContext,
    ComplianceSummaryRead,
    GeneratePlanRequest,
    GoalComplianceCalculateRequest,
    GoalInput,
    GoalRead,
    LoginRequest,
    PlannedSessionResultRead,
    RegisterRequest,
    SessionResultInput,
    UserRead,
    WeeklyPlanHistoryRead,
    WeeklyPlanRead,
)
from app.services.activity_parser import parse_activity_file
from app.services.activity_service import ActivityService
from app.services.goal_gpx_service import MAX_GPX_BYTES, parse_goal_gpx
from app.services.compliance_service import (
    ComplianceDomainService,
    PlanNotFoundException,
)
from app.services.planner import (
    DeterministicPlannerService,
    NoActiveGoalException,
    NoAvailabilityException,
    NoProfileException,
    PlannerDomainException,
)
from app.services.result_service import (
    ActivityAlreadyLinkedException,
    ActivityNotFoundException,
    InvalidResultStateException,
    ResultDomainService,
    SessionNotFoundException,
)

app = FastAPI(title="Training Online API", version="0.1.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=get_settings().session_secret,
    https_only=get_settings().session_https_only,
    same_site="lax",
)
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


def require_coaching_debug_token(x_coaching_debug_token: str | None = Header(default=None)) -> None:
    token = get_settings().coaching_debug_token
    if not token or x_coaching_debug_token != token:
        raise HTTPException(403, "Depuración del entrenador no autorizada")


def get_goal_or_404(goal_id: int, current_user: User, db: Session) -> Goal:
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
    if not goal:
        raise HTTPException(404, "Objetivo no encontrado")
    return goal


def activate_goal(goal: Goal, db: Session) -> None:
    """Only one active goal exists per user; activating one atomically deactivates the rest."""
    db.execute(update(Goal).where(Goal.user_id == goal.user_id).values(is_active=False))
    goal.is_active = True


@app.post("/api/auth/register", response_model=UserRead, status_code=201, tags=["auth"])
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "Ya existe una cuenta con ese email")
    user = User(
        name=payload.name.strip(),
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session.clear()
    request.session["user_id"] = user.id
    return user


@app.post("/api/auth/login", response_model=UserRead, tags=["auth"])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Credenciales incorrectas")
    request.session.clear()
    request.session["user_id"] = user.id
    return user


@app.get("/api/auth/session", response_model=UserRead, tags=["auth"])
def session(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.post("/api/auth/logout", status_code=204, tags=["auth"])
def logout(request: Request, current_user: User = Depends(get_current_user)) -> Response:
    del current_user
    request.session.clear()
    return Response(status_code=204)


@app.get("/api/activities", response_model=list[ActivityRead], tags=["activities"])
def list_activities(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Activity]:
    return list(
        db.scalars(
            select(Activity)
            .where(Activity.user_id == current_user.id)
            .order_by(Activity.started_at.desc())
        )
    )


@app.get("/api/activities/{activity_id}", response_model=ActivityRead, tags=["activities"])
def get_activity(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Activity:
    activity = db.scalar(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    if not activity:
        raise HTTPException(404, "Actividad no encontrada")
    return activity


@app.delete("/api/activities/{activity_id}", status_code=204, tags=["activities"])
def delete_activity(activity_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    ActivityService().delete(activity_id, current_user, db, Path(get_settings().upload_dir))
    return Response(status_code=204)


@app.post(
    "/api/activities/import", response_model=ActivityRead, status_code=201, tags=["activities"]
)
async def import_activity(
    file: UploadFile = File(...),
    goal_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Activity:
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

    started_at = data.get("started_at")
    assigned_goal_id = None

    if goal_id is not None:
        goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
        if not goal:
            raise HTTPException(404, "Objetivo no encontrado.")

        if not started_at:
            raise HTTPException(
                400,
                "La actividad no posee fecha y hora de inicio (started_at) para ser asociada al objetivo.",
            )

        activity_date = started_at.date()
        if not (goal.start_date <= activity_date <= goal.target_date):
            raise HTTPException(
                400,
                f"La fecha de la actividad ({activity_date}) se encuentra fuera del periodo permitido para este objetivo ({goal.start_date} al {goal.target_date}).",
            )
        assigned_goal_id = goal_id

    activity = Activity(
        user_id=current_user.id,
        original_filename=file.filename,
        stored_filename=stored_name,
        source_format=extension,
        goal_id=assigned_goal_id,
        **data,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@app.get(
    "/api/coaching/debug/context",
    response_model=CoachDebugContext,
    dependencies=[Depends(require_coaching_debug_token)],
    tags=["coaching"],
)
def coaching_debug_context(
    task_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Inspect the minimum context a future coach provider would receive.

    Uses the authenticated identity; this endpoint remains separate from the user workflow.
    """
    try:
        return ContextBuilder(db).build(user_id=current_user.id, task_type=task_type)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.get("/api/profile", response_model=AthleteProfileRead, tags=["profile"])
def get_profile(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AthleteProfileRead:
    profile = db.scalar(select(AthleteProfile).where(AthleteProfile.user_id == current_user.id))
    if not profile:
        return AthleteProfileRead()
    return AthleteProfileRead(
        id=profile.id,
        sports=profile.sports,
        experience_level=profile.experience_level,
        availability=profile.availability,
        power_zones=profile.power_zones,
        heart_rate_zones=profile.heart_rate_zones,
        preferences=profile.preferences,
        injuries_or_constraints=profile.injuries_or_constraints,
    )


@app.put("/api/profile", response_model=AthleteProfileRead, tags=["profile"])
def update_profile(
    payload: AthleteProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AthleteProfile:
    profile = db.scalar(select(AthleteProfile).where(AthleteProfile.user_id == current_user.id))
    if not profile:
        profile = AthleteProfile(user_id=current_user.id, **payload.model_dump())
        db.add(profile)
    else:
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/api/goals", response_model=list[GoalRead], tags=["goals"])
def list_goals(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Goal]:
    return list(
        db.scalars(
            select(Goal)
            .where(Goal.user_id == current_user.id)
            .order_by(Goal.is_active.desc(), Goal.target_date.asc())
        )
    )


@app.post("/api/goals", response_model=GoalRead, status_code=201, tags=["goals"])
def create_goal(
    payload: GoalInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    values = payload.model_dump()
    goal = Goal(user_id=current_user.id, **(values | {"is_active": False}))
    db.add(goal)
    db.flush()
    if payload.is_active:
        activate_goal(goal, db)
    db.commit()
    db.refresh(goal)
    return goal


@app.get("/api/goals/{goal_id}", response_model=GoalRead, tags=["goals"])
def get_goal(
    goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Goal:
    return get_goal_or_404(goal_id, current_user, db)


@app.put("/api/goals/{goal_id}", response_model=GoalRead, tags=["goals"])
def update_goal(
    goal_id: int,
    payload: GoalInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Goal:
    goal = get_goal_or_404(goal_id, current_user, db)
    for field, value in payload.model_dump(exclude={"is_active"}).items():
        setattr(goal, field, value)
    if payload.is_active:
        activate_goal(goal, db)
    else:
        goal.is_active = False
    db.commit()
    db.refresh(goal)
    return goal


@app.post("/api/goals/{goal_id}/route-gpx", response_model=GoalRead, tags=["goals"])
async def upload_goal_route_gpx(goal_id: int, file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Goal:
    goal = get_goal_or_404(goal_id, current_user, db)
    if Path(file.filename or "").suffix.lower() != ".gpx" or file.content_type not in {"application/gpx+xml", "application/xml", "text/xml", ""}:
        raise HTTPException(400, "Solo se admite un archivo GPX")
    raw = await file.read(MAX_GPX_BYTES + 1)
    try:
        metadata = parse_goal_gpx(raw)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    upload_dir = Path(get_settings().upload_dir) / "goal-routes" / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.gpx"
    (upload_dir / stored_name).write_bytes(raw)
    old_name = goal.route_stored_filename
    goal.route_original_filename, goal.route_stored_filename = file.filename, stored_name
    goal.route_size_bytes, goal.route_uploaded_at = len(raw), datetime.utcnow()
    for key, value in metadata.items(): setattr(goal, key, value)
    db.commit(); db.refresh(goal)
    if old_name: (upload_dir / old_name).unlink(missing_ok=True)
    return goal


@app.delete("/api/goals/{goal_id}/route-gpx", status_code=204, tags=["goals"])
def delete_goal_route_gpx(goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    goal = get_goal_or_404(goal_id, current_user, db)
    stored_name = goal.route_stored_filename
    for field in ("route_original_filename", "route_stored_filename", "route_size_bytes", "route_uploaded_at", "route_distance_meters", "route_elevation_gain_meters", "route_start_latitude", "route_start_longitude", "route_end_latitude", "route_end_longitude", "route_bounds"):
        setattr(goal, field, None)
    db.commit()
    if stored_name: (Path(get_settings().upload_dir) / "goal-routes" / str(current_user.id) / stored_name).unlink(missing_ok=True)
    return Response(status_code=204)


@app.post("/api/goals/{goal_id}/activate", response_model=GoalRead, tags=["goals"])
def activate_existing_goal(
    goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Goal:
    goal = get_goal_or_404(goal_id, current_user, db)
    activate_goal(goal, db)
    db.commit()
    db.refresh(goal)
    return goal


@app.delete("/api/goals/{goal_id}", status_code=204, tags=["goals"])
def delete_goal(
    goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    goal = get_goal_or_404(goal_id, current_user, db)
    db.delete(goal)
    db.commit()
    return Response(status_code=204)


@app.post("/api/plans/generate", response_model=WeeklyPlanRead, status_code=201, tags=["plans"])
def generate_weekly_plan(
    payload: GeneratePlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeeklyPlan:
    # 1. Fetch user context
    profile = db.scalar(select(AthleteProfile).where(AthleteProfile.user_id == current_user.id))
    goal = db.scalar(select(Goal).where(Goal.user_id == current_user.id, Goal.is_active.is_(True)))
    activities = list(db.scalars(select(Activity).where(Activity.user_id == current_user.id)))

    # 2. Run deterministic planner
    try:
        planner_service = DeterministicPlannerService()
        planner_context = planner_service.generate_plan(
            user_id=current_user.id,
            profile=profile,
            goal=goal,
            activities=activities,
            reference_date=payload.reference_date,
        )
    except NoProfileException as e:
        raise HTTPException(404, "Perfil deportivo no configurado.") from e
    except NoActiveGoalException as e:
        raise HTTPException(400, "No hay ningún objetivo activo configurado.") from e
    except NoAvailabilityException as e:
        raise HTTPException(400, "La disponibilidad semanal no está configurada.") from e
    except PlannerDomainException as e:
        raise HTTPException(422, str(e)) from e

    start_date = planner_context.start_date
    end_date = planner_context.end_date

    # 3. Check for existing active plan
    existing_active = db.scalar(
        select(WeeklyPlan).where(
            WeeklyPlan.user_id == current_user.id,
            WeeklyPlan.active_goal_id == goal.id,
            WeeklyPlan.start_date == start_date,
            WeeklyPlan.is_active.is_(True),
        )
    )

    if existing_active and not payload.force_regenerate:
        # Idempotent response: return existing active plan
        return existing_active

    # 4. Create new version atomically
    # Fetch all previous plans for the same week/goal
    previous_plans = list(
        db.scalars(
            select(WeeklyPlan).where(
                WeeklyPlan.user_id == current_user.id,
                WeeklyPlan.active_goal_id == goal.id,
                WeeklyPlan.start_date == start_date,
            )
        )
    )

    # Deactivate previous active plan if regenerating
    if existing_active:
        existing_active.is_active = False

    # Calculate version and source_plan_id
    next_version = max([p.version for p in previous_plans], default=0) + 1
    source_id = existing_active.id if existing_active else None

    new_plan = WeeklyPlan(
        user_id=current_user.id,
        active_goal_id=goal.id,
        start_date=start_date,
        end_date=end_date,
        version=next_version,
        is_active=True,
        rationale_data={"decisions": planner_context.decisions},
        cutoff_activity_id=planner_context.cutoff_activity.id
        if planner_context.cutoff_activity
        else None,
        source_plan_id=source_id,
        generation_reason=payload.generation_reason,
        ruleset_version="v1",
    )
    db.add(new_plan)
    db.flush()

    # Create planned sessions
    for sess in planner_context.sessions:
        planned_sess = PlannedSession(
            plan_id=new_plan.id,
            date=sess["date"],
            training_type=sess["training_type"],
            title=sess["title"],
            description=sess["description"],
            planned_duration=sess["planned_duration"],
            planned_distance_meters=sess["planned_distance_meters"],
            intensity_metric=sess["intensity_metric"],
            target_zone=sess["target_zone"],
            session_goal=sess["session_goal"],
            position=sess["position"],
            rationale=sess["rationale"],
        )
        db.add(planned_sess)

    db.commit()
    db.refresh(new_plan)
    return new_plan


@app.get("/api/plans/active", response_model=WeeklyPlanRead, tags=["plans"])
def get_active_plan(
    goal_id: int | None = None,
    start_date: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeeklyPlan:
    # 1. Resolve goal_id
    if goal_id is None:
        goal = db.scalar(
            select(Goal).where(Goal.user_id == current_user.id, Goal.is_active.is_(True))
        )
        if not goal:
            raise HTTPException(400, "No hay ningún objetivo activo configurado.")
        goal_id = goal.id

    # 2. Resolve start_date (Monday of target week)
    if start_date is None:
        # Default to Monday of next week relative to today
        today = date.today()
        start_date = today - timedelta(days=today.weekday()) + timedelta(days=7)

    # 3. Query active plan
    plan = db.scalar(
        select(WeeklyPlan).where(
            WeeklyPlan.user_id == current_user.id,
            WeeklyPlan.active_goal_id == goal_id,
            WeeklyPlan.start_date == start_date,
            WeeklyPlan.is_active.is_(True),
        )
    )
    if not plan:
        raise HTTPException(
            404, "No se encontró ningún plan activo para los parámetros especificados."
        )
    return plan


@app.get("/api/plans/history", response_model=list[WeeklyPlanHistoryRead], tags=["plans"])
def list_plan_history(
    goal_id: int,
    start_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WeeklyPlan]:
    # Query all versions for that user, goal, and week
    plans = list(
        db.scalars(
            select(WeeklyPlan)
            .where(
                WeeklyPlan.user_id == current_user.id,
                WeeklyPlan.active_goal_id == goal_id,
                WeeklyPlan.start_date == start_date,
            )
            .order_by(WeeklyPlan.version.desc())
        )
    )
    return plans


@app.get("/api/plans/{plan_id}", response_model=WeeklyPlanRead, tags=["plans"])
def get_specific_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeeklyPlan:
    plan = db.scalar(
        select(WeeklyPlan).where(WeeklyPlan.id == plan_id, WeeklyPlan.user_id == current_user.id)
    )
    if not plan:
        raise HTTPException(404, "Plan no encontrado.")
    return plan


@app.post(
    "/api/planned-sessions/{session_id}/result",
    response_model=PlannedSessionResultRead,
    status_code=201,
    tags=["results"],
)
def record_session_result(
    session_id: int,
    payload: SessionResultInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlannedSessionResult:
    try:
        result = ResultDomainService.record_result(
            db=db,
            session_id=session_id,
            user_id=current_user.id,
            status=payload.status,
            activity_id=payload.activity_id,
            reason=payload.reason,
            correction_reason=payload.correction_reason,
            notes=payload.notes,
        )
        return result
    except SessionNotFoundException as e:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from e
    except ActivityNotFoundException as e:
        raise HTTPException(status_code=404, detail="Actividad no encontrada.") from e
    except ActivityAlreadyLinkedException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InvalidResultStateException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get(
    "/api/planned-sessions/{session_id}/result",
    response_model=PlannedSessionResultRead,
    tags=["results"],
)
def get_session_result(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlannedSessionResult:
    try:
        # Validate session ownership
        ResultDomainService.get_session_or_404(db, session_id, current_user.id)

        result = db.scalar(
            select(PlannedSessionResult).where(
                PlannedSessionResult.planned_session_id == session_id,
                PlannedSessionResult.is_current.is_(True),
            )
        )
        if not result:
            raise HTTPException(status_code=404, detail="Resultado no registrado.")
        return result
    except SessionNotFoundException as e:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from e


@app.get(
    "/api/planned-sessions/{session_id}/result/history",
    response_model=list[PlannedSessionResultRead],
    tags=["results"],
)
def list_session_result_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PlannedSessionResult]:
    try:
        # Validate session ownership
        ResultDomainService.get_session_or_404(db, session_id, current_user.id)

        results = list(
            db.scalars(
                select(PlannedSessionResult)
                .where(PlannedSessionResult.planned_session_id == session_id)
                .order_by(PlannedSessionResult.revision.desc())
            )
        )
        return results
    except SessionNotFoundException as e:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from e


@app.get(
    "/api/planned-sessions/{session_id}/eligible-activities",
    response_model=list[ActivityRead],
    tags=["results"],
)
def list_eligible_activities(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Activity]:
    try:
        activities = ResultDomainService.get_eligible_activities(
            db=db, session_id=session_id, user_id=current_user.id
        )
        return activities
    except SessionNotFoundException as e:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from e


# --- COMPLIANCE ENDPOINTS ---


@app.post(
    "/api/plans/{plan_id}/compliance/calculate",
    response_model=ComplianceSummaryRead,
    status_code=201,
    tags=["compliance"],
)
def calculate_weekly_compliance(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceSummary:
    try:
        summary = ComplianceDomainService.calculate_and_persist_weekly(
            db=db, plan_id=plan_id, user_id=current_user.id
        )
        return summary
    except PlanNotFoundException as e:
        raise HTTPException(status_code=404, detail="Plan semanal no encontrado.") from e


@app.get(
    "/api/plans/{plan_id}/compliance",
    response_model=ComplianceSummaryRead,
    tags=["compliance"],
)
def get_weekly_compliance(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceSummary:
    # Verify ownership first
    plan = db.scalar(
        select(WeeklyPlan).where(
            and_(WeeklyPlan.id == plan_id, WeeklyPlan.user_id == current_user.id)
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan semanal no encontrado.")

    summary = db.scalar(
        select(ComplianceSummary).where(
            and_(
                ComplianceSummary.user_id == current_user.id,
                ComplianceSummary.weekly_plan_id == plan_id,
                ComplianceSummary.scope == "weekly",
                ComplianceSummary.is_current.is_(True),
            )
        )
    )
    if not summary:
        raise HTTPException(status_code=404, detail="Cumplimiento no calculado aún.")
    return summary


@app.get(
    "/api/plans/{plan_id}/compliance/history",
    response_model=list[ComplianceSummaryRead],
    tags=["compliance"],
)
def get_weekly_compliance_history(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ComplianceSummary]:
    plan = db.scalar(
        select(WeeklyPlan).where(
            and_(WeeklyPlan.id == plan_id, WeeklyPlan.user_id == current_user.id)
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan semanal no encontrado.")

    summaries = list(
        db.scalars(
            select(ComplianceSummary)
            .where(
                and_(
                    ComplianceSummary.user_id == current_user.id,
                    ComplianceSummary.weekly_plan_id == plan_id,
                    ComplianceSummary.scope == "weekly",
                )
            )
            .order_by(ComplianceSummary.revision.desc())
        )
    )
    return summaries


@app.post(
    "/api/goals/{goal_id}/compliance/calculate",
    response_model=ComplianceSummaryRead,
    status_code=201,
    tags=["compliance"],
)
def calculate_goal_compliance(
    goal_id: int,
    payload: GoalComplianceCalculateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceSummary:
    # Verify goal ownership
    goal = db.scalar(select(Goal).where(and_(Goal.id == goal_id, Goal.user_id == current_user.id)))
    if not goal:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado.")

    summary = ComplianceDomainService.calculate_and_persist_goal(
        db=db,
        goal_id=goal_id,
        user_id=current_user.id,
        from_date=payload.from_date,
        to_date=payload.to_date,
    )
    return summary


@app.get(
    "/api/goals/{goal_id}/compliance",
    response_model=ComplianceSummaryRead,
    tags=["compliance"],
)
def get_goal_compliance(
    goal_id: int,
    from_date: date,
    to_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ComplianceSummary:
    goal = db.scalar(select(Goal).where(and_(Goal.id == goal_id, Goal.user_id == current_user.id)))
    if not goal:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado.")

    summary = db.scalar(
        select(ComplianceSummary).where(
            and_(
                ComplianceSummary.user_id == current_user.id,
                ComplianceSummary.goal_id == goal_id,
                ComplianceSummary.scope == "goal",
                ComplianceSummary.from_date == from_date,
                ComplianceSummary.to_date == to_date,
                ComplianceSummary.is_current.is_(True),
            )
        )
    )
    if not summary:
        raise HTTPException(
            status_code=404, detail="Cumplimiento no calculado aún para este intervalo."
        )
    return summary


@app.get(
    "/api/goals/{goal_id}/compliance/history",
    response_model=list[ComplianceSummaryRead],
    tags=["compliance"],
)
def get_goal_compliance_history(
    goal_id: int,
    from_date: date,
    to_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ComplianceSummary]:
    goal = db.scalar(select(Goal).where(and_(Goal.id == goal_id, Goal.user_id == current_user.id)))
    if not goal:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado.")

    summaries = list(
        db.scalars(
            select(ComplianceSummary)
            .where(
                and_(
                    ComplianceSummary.user_id == current_user.id,
                    ComplianceSummary.goal_id == goal_id,
                    ComplianceSummary.scope == "goal",
                    ComplianceSummary.from_date == from_date,
                    ComplianceSummary.to_date == to_date,
                )
            )
            .order_by(ComplianceSummary.revision.desc())
        )
    )
    return summaries


@app.get("/api/goals/{goal_id}/activities", response_model=list[ActivityRead], tags=["goals"])
def list_goal_activities(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Activity]:
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
    if not goal:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado.")

    activities = list(
        db.scalars(
            select(Activity)
            .where(Activity.goal_id == goal_id, Activity.user_id == current_user.id)
            .order_by(Activity.started_at.desc())
        )
    )
    return activities


@app.patch("/api/activities/{activity_id}/goal", response_model=ActivityRead, tags=["activities"])
def update_activity_goal(
    activity_id: int,
    payload: ActivityGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Activity:
    activity = db.scalar(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada.")

    if payload.goal_id is None:
        # Dissociate, but check first if it is linked to any active results
        linked_result = db.scalar(
            select(PlannedSessionResult).where(
                PlannedSessionResult.activity_id == activity_id,
                PlannedSessionResult.is_current.is_(True),
            )
        )
        if linked_result:
            raise HTTPException(
                status_code=400,
                detail="No se puede desasociar la actividad porque está vinculada a un resultado de sesión vigente.",
            )
        activity.goal_id = None
    else:
        # Associate
        goal = db.scalar(
            select(Goal).where(Goal.id == payload.goal_id, Goal.user_id == current_user.id)
        )
        if not goal:
            raise HTTPException(status_code=404, detail="Objetivo no encontrado.")

        if not activity.started_at:
            raise HTTPException(
                status_code=400,
                detail="La actividad no posee fecha de inicio para ser asociada al objetivo.",
            )

        activity_date = activity.started_at.date()
        if not (goal.start_date <= activity_date <= goal.target_date):
            raise HTTPException(
                status_code=400,
                detail=f"La fecha de la actividad ({activity_date}) se encuentra fuera del periodo permitido para este objetivo ({goal.start_date} al {goal.target_date}).",
            )
        activity.goal_id = payload.goal_id

    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity

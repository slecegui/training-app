"""Database models."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activities: Mapped[list["Activity"]] = relationship(back_populates="user")
    athlete_profile: Mapped["AthleteProfile | None"] = relationship(back_populates="user")
    goals: Mapped[list["Goal"]] = relationship()
    weekly_plans: Mapped[list["WeeklyPlan"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    sport: Mapped[str] = mapped_column(String(80), default="Otros")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_gain_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_format: Mapped[str] = mapped_column(String(10), default="demo")
    source_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    external_activity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    user: Mapped[User] = relationship(back_populates="activities")
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    goal: Mapped["Goal | None"] = relationship()
    __table_args__ = (
        UniqueConstraint(
            "user_id", "source_provider", "external_activity_id", name="uq_activity_external_source"
        ),
    )


class GarminConnection(Base):
    __tablename__ = "garmin_connections"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    encrypted_tokens: Mapped[str] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    sports: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_level: Mapped[str | None] = mapped_column(String(50))
    power_zones: Mapped[dict] = mapped_column(JSON, default=dict)
    heart_rate_zones: Mapped[dict] = mapped_column(JSON, default=dict)
    availability: Mapped[dict] = mapped_column(JSON, default=dict)
    injuries_or_constraints: Mapped[str | None] = mapped_column(Text)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    user: Mapped[User] = relationship(back_populates="athlete_profile")


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    goal_type: Mapped[str] = mapped_column(String(80), default="event")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date)
    sport: Mapped[str | None] = mapped_column(String(80))
    priority: Mapped[str] = mapped_column(String(30), default="medium")
    target_distance_meters: Mapped[float | None] = mapped_column(Float)
    target_elevation_meters: Mapped[float | None] = mapped_column(Float)
    success_metric: Mapped[str] = mapped_column(String(255), default="Completar")
    success_metric_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    success_metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    success_metric_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    details: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    route_original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    route_stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    route_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    route_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    route_distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_elevation_gain_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_start_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_start_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_end_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_end_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_bounds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    routes: Mapped[list["GoalRoute"]] = relationship(
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="GoalRoute.display_order, GoalRoute.id",
    )


class GoalRoute(Base):
    __tablename__ = "goal_routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    stage_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_gain_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    bounds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    goal: Mapped[Goal] = relationship(back_populates="routes")


class WellnessEntry(Base):
    __tablename__ = "wellness_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entry_date: Mapped[Date] = mapped_column(Date, index=True)
    sleep_hours: Mapped[float | None] = mapped_column(Float)
    fatigue: Mapped[int | None] = mapped_column(Integer)
    soreness: Mapped[int | None] = mapped_column(Integer)
    stress: Mapped[int | None] = mapped_column(Integer)
    mood: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)


class CoachDecision(Base):
    __tablename__ = "coach_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(50))
    input_context: Mapped[dict] = mapped_column(JSON)
    output_payload: Mapped[dict] = mapped_column(JSON)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(64), unique=True)
    source: Mapped[str] = mapped_column(String(255))
    checksum: Mapped[str] = mapped_column(String(64))
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    active_goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"), index=True, nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    rationale_data: Mapped[dict] = mapped_column(JSON, default=dict)
    cutoff_activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    generation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ruleset_version: Mapped[str] = mapped_column(String(64), default="v1")

    user: Mapped["User"] = relationship(back_populates="weekly_plans")
    sessions: Mapped[list["PlannedSession"]] = relationship(
        "PlannedSession",
        back_populates="weekly_plan",
        cascade="all, delete-orphan",
        order_by="PlannedSession.date, PlannedSession.position",
    )

    __table_args__ = (
        Index(
            "uq_active_plan_per_week",
            "user_id",
            "active_goal_id",
            "start_date",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
        UniqueConstraint(
            "user_id", "active_goal_id", "start_date", "version", name="uq_user_goal_week_version"
        ),
    )


class PlannedSession(Base):
    __tablename__ = "planned_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_plans.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    training_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_duration: Mapped[int] = mapped_column(Integer)
    planned_distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    intensity_metric: Mapped[str] = mapped_column(String(30))
    target_zone: Mapped[str] = mapped_column(String(30))
    session_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    weekly_plan: Mapped["WeeklyPlan"] = relationship("WeeklyPlan", back_populates="sessions")
    results: Mapped[list["PlannedSessionResult"]] = relationship(
        "PlannedSessionResult", back_populates="planned_session", cascade="all, delete-orphan"
    )


class PlannedSessionResult(Base):
    __tablename__ = "planned_session_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    planned_session_id: Mapped[int] = mapped_column(
        ForeignKey("planned_sessions.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    supersedes_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("planned_session_results.id", ondelete="SET NULL"), nullable=True, index=True
    )
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30))  # completed, omitted, partial, replaced
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    recorded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    planned_session: Mapped["PlannedSession"] = relationship(
        "PlannedSession", back_populates="results"
    )
    activity: Mapped["Activity | None"] = relationship("Activity")

    __table_args__ = (
        UniqueConstraint("planned_session_id", "revision", name="uq_planned_session_revision"),
        # Unique constraint to allow ONLY one active result per planned_session
        Index(
            "uq_current_result_per_session",
            "planned_session_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
        # Unique constraint to prevent an activity from being linked to multiple current results
        Index(
            "uq_current_activity_assignment",
            "activity_id",
            unique=True,
            postgresql_where=text("is_current = true AND activity_id IS NOT NULL"),
            sqlite_where=text("is_current = 1 AND activity_id IS NOT NULL"),
        ),
    )


class ComplianceSummary(Base):
    __tablename__ = "compliance_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(30))  # weekly, goal
    weekly_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_plans.id", ondelete="CASCADE"), nullable=True, index=True
    )
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    from_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    to_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30))  # complete, incomplete, not_applicable
    numerator: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    denominator: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    ruleset_version: Mapped[str] = mapped_column(String(64), default="duration-v1")
    input_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    supersedes_summary_id: Mapped[int | None] = mapped_column(
        ForeignKey("compliance_summaries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    user: Mapped["User"] = relationship()
    weekly_plan: Mapped["WeeklyPlan | None"] = relationship()
    goal: Mapped["Goal"] = relationship()
    components: Mapped[list["ComplianceComponent"]] = relationship(
        "ComplianceComponent", back_populates="summary", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Checks
        CheckConstraint("scope IN ('weekly', 'goal')", name="chk_compliance_scope"),
        CheckConstraint(
            "status IN ('complete', 'incomplete', 'not_applicable')", name="chk_compliance_status"
        ),
        CheckConstraint(
            "(scope = 'weekly' AND weekly_plan_id IS NOT NULL AND from_date IS NULL AND to_date IS NULL) OR "
            "(scope = 'goal' AND weekly_plan_id IS NULL AND from_date IS NOT NULL AND to_date IS NOT NULL)",
            name="chk_scope_fields",
        ),
        CheckConstraint(
            "(status = 'complete' AND percentage IS NOT NULL AND denominator > 0) OR "
            "(status = 'incomplete' AND percentage IS NULL) OR "
            "(status = 'not_applicable' AND percentage IS NULL AND denominator = 0)",
            name="chk_status_fields",
        ),
        # Unique indexes for active summaries
        Index(
            "uq_current_weekly_compliance",
            "user_id",
            "weekly_plan_id",
            unique=True,
            postgresql_where=text("scope = 'weekly' AND is_current = true"),
            sqlite_where=text("scope = 'weekly' AND is_current = 1"),
        ),
        Index(
            "uq_current_goal_compliance",
            "user_id",
            "goal_id",
            "from_date",
            "to_date",
            unique=True,
            postgresql_where=text("scope = 'goal' AND is_current = true"),
            sqlite_where=text("scope = 'goal' AND is_current = 1"),
        ),
    )


class ComplianceComponent(Base):
    __tablename__ = "compliance_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    summary_id: Mapped[int] = mapped_column(
        ForeignKey("compliance_summaries.id", ondelete="CASCADE"), index=True
    )
    planned_session_id: Mapped[int] = mapped_column(
        ForeignKey("planned_sessions.id", ondelete="CASCADE"), index=True
    )
    planned_session_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("planned_session_results.id", ondelete="SET NULL"), nullable=True, index=True
    )
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    credit: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    weighted_credit: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    exclusion_or_error_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    planned_duration_snapshot: Mapped[int] = mapped_column(Integer)
    actual_duration_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)

    summary: Mapped["ComplianceSummary"] = relationship(
        "ComplianceSummary", back_populates="components"
    )
    planned_session: Mapped["PlannedSession"] = relationship()
    planned_session_result: Mapped["PlannedSessionResult | None"] = relationship()
    activity: Mapped["Activity | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("summary_id", "planned_session_id", name="uq_summary_session_component"),
        CheckConstraint("weight > 0", name="chk_weight_positive"),
        CheckConstraint("credit IS NULL OR (credit >= 0 AND credit <= 1)", name="chk_credit_range"),
    )

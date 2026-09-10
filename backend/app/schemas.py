"""API schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    sport: str
    started_at: datetime | None
    duration_seconds: int | None
    distance_meters: float | None
    elevation_gain_meters: float | None
    average_heart_rate: int | None
    average_power: int | None
    average_cadence: int | None
    calories: int | None
    original_filename: str | None
    source_format: str
    goal_id: int | None = None


class PlannedSession(BaseModel):
    date: date
    sport: str
    objective: str
    duration_minutes: int
    intensity_target: str
    structure: list[str]
    safety_notes: list[str] = []


class TrainingPlanResponse(BaseModel):
    goal_summary: str
    sessions: list[PlannedSession]
    assumptions: list[str]
    knowledge_version: str


class AdjustmentResponse(BaseModel):
    action: str
    reason: str
    replacement_session: PlannedSession | None = None
    safety_flags: list[str] = []
    knowledge_version: str


class CoachDebugContext(BaseModel):
    task_type: str
    knowledge_version: str
    methodology: dict[str, str]
    athlete_profile: dict | None
    active_goal: dict | None
    availability: dict
    recent_activities: list[dict]
    recent_wellness: list[dict]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("El email no es válido")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)


class AthleteProfileUpdate(BaseModel):
    sports: list[str] = Field(default_factory=list, max_length=10)
    experience_level: str | None = Field(default=None, max_length=50)
    availability: dict[str, int] = Field(default_factory=dict)
    power_zones: dict[str, float] = Field(default_factory=dict)
    heart_rate_zones: dict[str, int] = Field(default_factory=dict)
    preferences: dict[str, str | int | float | bool] = Field(default_factory=dict)
    injuries_or_constraints: str | None = Field(default=None, max_length=4000)

    @field_validator("availability")
    @classmethod
    def validate_availability(cls, value: dict[str, int]) -> dict[str, int]:
        valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        if set(value) - valid_days or any(
            minutes < 0 or minutes > 1440 for minutes in value.values()
        ):
            raise ValueError("Disponibilidad: días mon..sun y minutos entre 0 y 1440")
        return value

    @field_validator("power_zones")
    @classmethod
    def validate_power_zones(cls, value: dict[str, float]) -> dict[str, float]:
        if any(watts <= 0 for watts in value.values()):
            raise ValueError("Las zonas de potencia deben ser positivas")
        return value

    @field_validator("heart_rate_zones")
    @classmethod
    def validate_heart_rate_zones(cls, value: dict[str, int]) -> dict[str, int]:
        if any(bpm <= 0 or bpm > 260 for bpm in value.values()):
            raise ValueError("Las zonas de frecuencia cardiaca deben estar entre 1 y 260")
        return value


class AthleteProfileRead(AthleteProfileUpdate):
    id: int | None = None


class GoalInput(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    goal_type: str = Field(min_length=2, max_length=80)
    start_date: date | None = None
    target_date: date
    sport: str = Field(min_length=2, max_length=80)
    priority: str = Field(pattern="^(low|medium|high)$")
    target_distance_meters: float | None = Field(default=None, gt=0)
    target_elevation_meters: float | None = Field(default=None, gt=0)
    success_metric: str | None = None
    success_metric_type: str | None = None
    success_metric_value: float | None = None
    success_metric_unit: str | None = None
    details: str | None = Field(default=None, max_length=1000)
    is_active: bool = False

    @field_validator("target_date")
    @classmethod
    def date_must_be_future(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("La fecha del objetivo no puede estar en el pasado")
        return value

    @model_validator(mode="after")
    def validate_and_generate_metrics(self) -> "GoalInput":
        if self.title:
            self.title = self.title.strip()
            if len(self.title) < 2 or len(self.title) > 120:
                raise ValueError("El título debe tener entre 2 y 120 caracteres.")
            if not self.title:
                raise ValueError("El título no puede contener únicamente espacios.")

        # Default start_date to today if not provided (safety default)
        if self.start_date is None:
            self.start_date = date.today()

        if self.start_date and self.target_date:
            if self.start_date > self.target_date:
                raise ValueError(
                    "La fecha de inicio no puede ser posterior a la fecha del objetivo."
                )

        valid_types = {"sportive", "race", "climb", "endurance", "ftp_improvement", "health"}
        if self.goal_type not in valid_types:
            if self.goal_type in ("event", "evento"):
                self.goal_type = "race"
            else:
                raise ValueError("Tipo de objetivo no permitido.")

        valid_sports = {
            "cycling_general",
            "road_cycling",
            "mountain_biking",
            "gravel",
            "indoor_cycling",
            "cyclocross",
            "track_cycling",
        }
        if self.sport not in valid_sports:
            if self.sport == "Ciclismo":
                self.sport = "cycling_general"
            else:
                raise ValueError("Modalidad deportiva no permitida.")

        m_type = self.success_metric_type
        val = self.success_metric_value

        if m_type == "completar":
            self.success_metric = "Completar"
        elif m_type == "tiempo_maximo":
            if val is None:
                raise ValueError("Se requiere un valor para el tiempo máximo.")
            h = int(val)
            m = int(round((val - h) * 60))
            self.success_metric = f"Finalizar en un tiempo máximo de {h}h {m}m"
        elif m_type == "velocidad_media":
            if val is None:
                raise ValueError("Se requiere un valor para la velocidad media.")
            self.success_metric = f"Alcanzar una velocidad media de {val} km/h"
        elif m_type == "posicion_objetivo":
            if val is None:
                raise ValueError("Se requiere un valor para la posición objetivo.")
            self.success_metric = f"Terminar en posición {int(val)} o mejor"
        elif m_type == "potencia_media":
            if val is None:
                raise ValueError("Se requiere un valor para la potencia media.")
            self.success_metric = f"Potencia media objetivo de {int(val)} W"
        elif m_type == "distancia_total":
            if val is None:
                raise ValueError("Se requiere un valor para la distancia total.")
            self.success_metric = f"Distancia total de {val} km"
        elif m_type == "duracion_total":
            if val is None:
                raise ValueError("Se requiere un valor para la duración total.")
            self.success_metric = f"Duración total de {int(val)} minutos"
        elif m_type == "ftp_objetivo":
            if val is None:
                raise ValueError("Se requiere un valor para el FTP objetivo.")
            self.success_metric = f"FTP objetivo de {int(val)} W"
        elif m_type == "ftp_incremento":
            if val is None:
                raise ValueError("Se requiere un valor para el incremento porcentual.")
            self.success_metric = f"Incremento de FTP de {val}%"
        elif m_type == "sesiones_semanales":
            if val is None:
                raise ValueError("Se requiere un valor para las sesiones semanales.")
            self.success_metric = f"{int(val)} sesiones por semana"
        elif m_type == "minutos_semanales":
            if val is None:
                raise ValueError("Se requiere un valor para los minutos semanales.")
            self.success_metric = f"{int(val)} minutos por semana"
        elif m_type == "semanas_consecutivas":
            if val is None:
                raise ValueError("Se requiere un valor para las semanas consecutivas.")
            self.success_metric = f"{int(val)} semanas consecutivas cumpliendo"
        else:
            if not self.success_metric:
                self.success_metric = "Completar"

        return self


class GoalRead(GoalInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    route_original_filename: str | None = None
    route_size_bytes: int | None = None
    route_uploaded_at: datetime | None = None
    route_distance_meters: float | None = None
    route_elevation_gain_meters: float | None = None
    route_start_latitude: float | None = None
    route_start_longitude: float | None = None
    route_end_latitude: float | None = None
    route_end_longitude: float | None = None
    route_bounds: dict | None = None


class PlannedSessionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    planned_session_id: int
    revision: int
    is_current: bool
    supersedes_result_id: int | None = None
    activity_id: int | None = None
    status: str
    reason: str | None = None
    correction_reason: str | None = None
    notes: str | None = None
    recorded_at: datetime
    created_at: datetime


class SessionResultInput(BaseModel):
    status: str
    activity_id: int | None = None
    reason: str | None = None
    correction_reason: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_status_rules(self) -> "SessionResultInput":
        status = self.status.lower()
        if status not in ("completed", "omitted", "partial", "replaced"):
            raise ValueError("Estado de resultado inválido.")

        if status == "omitted":
            if self.activity_id is not None:
                raise ValueError("El estado omitido no permite vincular una actividad.")
        else:
            if self.activity_id is None:
                raise ValueError(f"El estado '{self.status}' requiere vincular una actividad.")

        if status in ("omitted", "partial", "replaced"):
            if not self.reason or not self.reason.strip():
                raise ValueError(f"El estado '{self.status}' requiere un motivo o explicación.")

        return self


class PlannedSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    training_type: str
    title: str
    description: str | None = None
    planned_duration: int
    planned_distance_meters: float | None = None
    intensity_metric: str
    target_zone: str
    session_goal: str | None = None
    position: int
    rationale: str | None = None
    results: list[PlannedSessionResultRead] = Field(default_factory=list)


class WeeklyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    active_goal_id: int | None = None
    start_date: date
    end_date: date
    version: int
    is_active: bool
    created_at: datetime
    generation_reason: str | None = None
    ruleset_version: str
    sessions: list[PlannedSessionRead]
    rationale_data: dict


class WeeklyPlanHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    start_date: date
    end_date: date
    version: int
    is_active: bool
    created_at: datetime
    generation_reason: str | None = None


class GeneratePlanRequest(BaseModel):
    reference_date: date | None = None
    force_regenerate: bool = False
    generation_reason: str | None = None


class ComplianceComponentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    summary_id: int
    planned_session_id: int
    planned_session_result_id: int | None = None
    activity_id: int | None = None
    weight: Decimal
    credit: Decimal | None = None
    weighted_credit: Decimal | None = None
    exclusion_or_error_reason: str | None = None
    planned_duration_snapshot: int
    actual_duration_snapshot: int | None = None


class ComplianceSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    scope: str
    weekly_plan_id: int | None = None
    goal_id: int
    from_date: date | None = None
    to_date: date | None = None
    revision: int
    status: str
    numerator: Decimal
    denominator: Decimal
    percentage: Decimal | None = None
    ruleset_version: str
    input_fingerprint: str
    computed_at: datetime
    is_current: bool
    components: list[ComplianceComponentRead] = Field(default_factory=list)


class GoalComplianceCalculateRequest(BaseModel):
    from_date: date
    to_date: date


class ActivityGoalUpdate(BaseModel):
    goal_id: int | None = None

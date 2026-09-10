"""Deterministic training planner service utilizing a Pipeline pattern."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


class PlannerDomainException(Exception):
    """Base exception for training planner domain errors."""

    pass


class NoProfileException(PlannerDomainException):
    pass


class NoActiveGoalException(PlannerDomainException):
    pass


class NoAvailabilityException(PlannerDomainException):
    pass


@dataclass
class PlannerContext:
    user_id: int
    profile: Any  # AthleteProfile
    goal: Any  # Goal
    activities: list[Any]  # list[Activity]
    reference_date: date | None = None

    # Pipeline output / intermediate state
    start_date: date | None = None
    end_date: date | None = None
    cutoff_activity: Any | None = None
    intensity_metric: str = "rpe"  # "power", "hr", "rpe"
    target_weekly_minutes: int = 0
    sessions: list[dict] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)


class PlannerPipelineStep:
    def process(self, context: PlannerContext) -> None:
        raise NotImplementedError()


class ValidateAndDateRule(PlannerPipelineStep):
    def process(self, context: PlannerContext) -> None:
        if not context.profile:
            raise NoProfileException("Perfil deportivo no configurado.")

        if not context.goal:
            raise NoActiveGoalException("No hay ningún objetivo activo configurado.")

        # Check availability
        avail = context.profile.availability or {}
        valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        avail_mins = {d: m for d, m in avail.items() if d in valid_days and m > 0}
        if not avail_mins:
            raise NoAvailabilityException(
                "No hay días disponibles declarados en la disponibilidad."
            )

        context.decisions.append("Validación de perfil, objetivo activo y disponibilidad superada.")

        # Date calculation
        valid_activities = [a for a in context.activities if a.started_at]
        if valid_activities:
            # Find the most recent activity
            latest = max(valid_activities, key=lambda a: a.started_at)
            context.cutoff_activity = latest
            latest_date = latest.started_at.date()
            context.decisions.append(
                f"Actividad más reciente encontrada en fecha: {latest_date}. "
                f"Calculando semana ISO posterior."
            )
            monday_of_latest = latest_date - timedelta(days=latest_date.weekday())
            context.start_date = monday_of_latest + timedelta(days=7)
            context.end_date = context.start_date + timedelta(days=6)
        else:
            if not context.reference_date:
                raise PlannerDomainException(
                    "No se dispone de actividades previas y no se ha especificado reference_date."
                )
            context.decisions.append(
                f"Sin actividades previas. Usando la reference_date explícita: {context.reference_date}."
            )
            monday_of_ref = context.reference_date - timedelta(
                days=context.reference_date.weekday()
            )
            context.start_date = monday_of_ref + timedelta(days=7)
            context.end_date = context.start_date + timedelta(days=6)

        context.decisions.append(
            f"Semana de planificación calculada: {context.start_date} a {context.end_date}."
        )


class MetricSelectionRule(PlannerPipelineStep):
    def process(self, context: PlannerContext) -> None:
        profile = context.profile
        # Explicit check for power meter equipment
        has_power_meter = profile.preferences.get("has_power_meter") is True
        power_zones = profile.power_zones or {}
        heart_rate_zones = profile.heart_rate_zones or {}

        if has_power_meter and power_zones:
            context.intensity_metric = "power"
            context.decisions.append(
                "Métrica seleccionada: Potencia (potenciómetro explícito y zonas de potencia configuradas)."
            )
        elif heart_rate_zones:
            context.intensity_metric = "hr"
            context.decisions.append(
                "Métrica seleccionada: Frecuencia Cardíaca (sin potenciómetro, pero zonas de FC configuradas)."
            )
        else:
            context.intensity_metric = "rpe"
            context.decisions.append(
                "Métrica seleccionada: RPE (escala de esfuerzo percibido, sin potenciómetro ni zonas de FC)."
            )


class LoadAndVolumeRule(PlannerPipelineStep):
    def process(self, context: PlannerContext) -> None:
        # Calculate availability sums
        avail = context.profile.availability or {}
        total_avail_minutes = sum(
            v for k, v in avail.items() if k in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        )

        # Adjust total load based on experience level
        experience = (context.profile.experience_level or "beginner").lower()
        multiplier = (
            0.5 if experience == "beginner" else (0.7 if experience == "intermediate" else 0.85)
        )

        target = int(total_avail_minutes * multiplier)

        # Proximity adjustment
        days_to_goal = (context.goal.target_date - context.start_date).days
        if days_to_goal < 0:
            # Goal is in the past! (Should not happen in future-only, but let's handle gracefully)
            context.decisions.append(
                "Objetivo alcanzado o pasado. Enfocando en recuperación activa."
            )
            target = int(target * 0.4)
        elif days_to_goal < 14:
            # Taper phase
            context.decisions.append(
                f"Fase de Puesta a Punto (Taper) detectada ({days_to_goal} días al objetivo). Reduciendo volumen un 40%."
            )
            target = int(target * 0.6)
        elif days_to_goal < 56:
            # Build phase
            context.decisions.append(
                f"Fase de Construcción (Build) detectada ({days_to_goal} días al objetivo). Aplicando volumen estándar de entrenamiento."
            )
        else:
            # Base phase
            context.decisions.append(
                f"Fase Base de acondicionamiento detectada ({days_to_goal} días al objetivo). Limitando intensidad y estabilizando volumen."
            )
            target = int(target * 0.9)

        context.target_weekly_minutes = max(target, 30)  # At least 30 minutes
        context.decisions.append(
            f"Volumen semanal objetivo calculado: {context.target_weekly_minutes} minutos."
        )


class SessionAssignmentRule(PlannerPipelineStep):
    def process(self, context: PlannerContext) -> None:
        avail = context.profile.availability or {}
        sorted_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        available_days = [d for d in sorted_days if avail.get(d, 0) > 0]

        # Priority and Goal influence on intense sessions counts
        priority = (context.goal.priority or "medium").lower()
        max_intense = 1 if priority == "low" else (2 if priority == "medium" else 3)

        # Let's assign session roles to available days
        # Roles: "interval" (high intensity), "endurance" (aerobic), "recovery" (low intensity)
        day_roles = {}
        intense_count = 0

        # Long ride goes to the day with maximum available time
        long_ride_day = max(available_days, key=lambda d: avail[d])
        day_roles[long_ride_day] = "endurance"

        # Sort remaining available days by available time to distribute intense sessions
        remaining_days = [d for d in available_days if d != long_ride_day]

        # To prevent back-to-back intense sessions, we track previous day's role
        # Mon-Sun cycle tracking:
        day_indices = {d: i for i, d in enumerate(sorted_days)}

        for day in sorted(remaining_days, key=lambda d: avail[d], reverse=True):
            if intense_count < max_intense:
                # Check neighbors to ensure no adjacent intense sessions
                idx = day_indices[day]
                prev_day = sorted_days[idx - 1] if idx > 0 else "sun"
                next_day = sorted_days[idx + 1] if idx < 6 else "mon"

                if day_roles.get(prev_day) != "interval" and day_roles.get(next_day) != "interval":
                    day_roles[day] = "interval"
                    intense_count += 1
                else:
                    day_roles[day] = "recovery"
            else:
                day_roles[day] = "recovery"

        # Build sessions list
        weekly_target_min = context.target_weekly_minutes
        allocated_min = 0

        # Construct raw session plan structure
        for position, day in enumerate(sorted_days, start=1):
            day_avail = avail.get(day, 0)
            if day_avail <= 0:
                continue

            role = day_roles.get(day, "recovery")
            # Allocate duration: target is proportional to day availability but constrained by total weekly target
            duration = min(
                day_avail,
                int(weekly_target_min * (day_avail / sum(avail.get(d, 0) for d in available_days))),
            )
            duration = max(duration, min(day_avail, 30))  # At least 30 mins or max availability

            # Specific session properties based on role and sport
            sport = context.goal.sport or "Ciclismo"
            metric = context.intensity_metric

            if role == "interval":
                title = f"Intervalos de {sport}"
                desc = (
                    "Sesión estructurada de intervalos de alta intensidad para mejorar el umbral."
                )
                intensity_lbl, zone_lbl = self._get_zone(metric, "z4", context.profile)
                goal_str = "Desarrollar potencia/resistencia aeróbica de alta intensidad."
                distance_est = (
                    self._estimate_distance(sport, duration, 280)
                    if sport.lower() == "ciclismo"
                    else None
                )
            elif role == "endurance":
                if day == long_ride_day:
                    title = f"Fondo de {sport}"
                    desc = "Entrenamiento largo y continuo para desarrollar la base aeróbica."
                    goal_str = "Desarrollar la capacidad de resistencia general."
                else:
                    title = f"Resistencia Base {sport}"
                    desc = "Sesión continua a ritmo constante en zona aeróbica."
                    goal_str = "Fomentar adaptaciones metabólicas base."
                intensity_lbl, zone_lbl = self._get_zone(metric, "z2", context.profile)
                distance_est = (
                    self._estimate_distance(sport, duration, 240)
                    if sport.lower() == "ciclismo"
                    else None
                )
            else:
                title = f"Recuperación Activa {sport}"
                desc = "Sesión muy suave para facilitar el flujo sanguíneo y la recuperación."
                intensity_lbl, zone_lbl = self._get_zone(metric, "z1", context.profile)
                goal_str = "Eliminar fatiga residual de sesiones anteriores."
                distance_est = (
                    self._estimate_distance(sport, duration, 200)
                    if sport.lower() == "ciclismo"
                    else None
                )

            # Calculate session date
            session_date = context.start_date + timedelta(days=day_indices[day])

            context.sessions.append(
                {
                    "date": session_date,
                    "training_type": sport,
                    "title": title,
                    "description": desc,
                    "planned_duration": duration,
                    "planned_distance_meters": distance_est,
                    "intensity_metric": metric,
                    "target_zone": zone_lbl,
                    "session_goal": goal_str,
                    "position": position,
                    "rationale": f"Sesión asignada el {day.upper()} por rol de {role.upper()} ajustado a disponibilidad de {day_avail} min.",
                }
            )
            allocated_min += duration

        context.decisions.append(
            f"Asignación de sesiones finalizada. Total minutos asignados: {allocated_min}."
        )

    @staticmethod
    def _get_zone(metric: str, zone_key: str, profile: Any) -> tuple[str, str]:
        if metric == "power":
            zones = profile.power_zones or {}
            val = zones.get(zone_key)
            if val:
                return "Potencia (W)", f"{zone_key.upper()} ({int(val)} W)"
            return "Potencia (W)", zone_key.upper()
        elif metric == "hr":
            zones = profile.heart_rate_zones or {}
            val = zones.get(zone_key)
            if val:
                return "Frecuencia Cardíaca (ppm)", f"{zone_key.upper()} ({int(val)} ppm)"
            return "Frecuencia Cardíaca (ppm)", zone_key.upper()
        else:
            rpe_map = {
                "z1": "RPE 2-3 (Muy suave)",
                "z2": "RPE 4 (Moderado)",
                "z4": "RPE 7-8 (Intenso)",
            }
            return "RPE (1-10)", rpe_map.get(zone_key, "RPE 4")

    @staticmethod
    def _estimate_distance(sport: str, duration_mins: int, speed_m_per_min: float) -> float | None:
        if sport.lower() == "ciclismo":
            return round((duration_mins * speed_m_per_min), 1)
        return None


class DeterministicPlannerService:
    def __init__(self):
        self.pipeline: list[PlannerPipelineStep] = [
            ValidateAndDateRule(),
            MetricSelectionRule(),
            LoadAndVolumeRule(),
            SessionAssignmentRule(),
        ]

    def generate_plan(
        self,
        user_id: int,
        profile: Any,
        goal: Any,
        activities: list[Any],
        reference_date: date | None = None,
    ) -> PlannerContext:
        context = PlannerContext(
            user_id=user_id,
            profile=profile,
            goal=goal,
            activities=activities,
            reference_date=reference_date,
        )

        for step in self.pipeline:
            step.process(context)

        return context

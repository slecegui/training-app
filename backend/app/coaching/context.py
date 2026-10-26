"""Build minimal, user-scoped coaching context without invoking an AI provider."""

from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, AthleteProfile, Goal, KnowledgeVersion, WellnessEntry

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
TASK_DOCUMENTS = {
    "plan": ("principios", "zonas", "periodizacion", "seguridad"),
    "adjustment": ("principios", "zonas", "recuperacion", "seguridad"),
    "recovery": ("recuperacion", "nutricion", "seguridad"),
    "nutrition": ("nutricion", "seguridad"),
}


class ContextBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(self, user_id: int, task_type: str) -> dict:
        if task_type not in TASK_DOCUMENTS:
            raise ValueError("Tipo de tarea no compatible")
        profile = self.db.scalar(select(AthleteProfile).where(AthleteProfile.user_id == user_id))
        goal = self.db.scalar(
            select(Goal)
            .where(Goal.user_id == user_id, Goal.is_active.is_(True))
            .order_by(Goal.target_date.asc().nullslast())
        )
        since = date.today() - timedelta(days=14 if task_type == "plan" else 7)
        activities = list(
            self.db.scalars(
                select(Activity)
                .where(Activity.user_id == user_id, Activity.started_at >= since)
                .order_by(Activity.started_at.desc())
                .limit(12)
            )
        )
        wellness = list(
            self.db.scalars(
                select(WellnessEntry)
                .where(WellnessEntry.user_id == user_id, WellnessEntry.entry_date >= since)
                .order_by(WellnessEntry.entry_date.desc())
                .limit(10)
            )
        )
        return {
            "task_type": task_type,
            "knowledge_version": self._knowledge_version(),
            "methodology": self._documents(task_type),
            "athlete_profile": self._profile(profile),
            "active_goal": self._goal(goal),
            "availability": profile.availability if profile else {},
            "preferences": profile.preferences if profile else {},
            "recent_activities": [self._activity(item) for item in activities],
            "recent_wellness": [self._wellness(item) for item in wellness],
        }

    def _documents(self, task_type: str) -> dict[str, str]:
        return {
            name: (KNOWLEDGE_DIR / f"{name}.md").read_text() for name in TASK_DOCUMENTS[task_type]
        }

    def _knowledge_version(self) -> str:
        version = self.db.scalar(
            select(KnowledgeVersion).order_by(KnowledgeVersion.activated_at.desc())
        )
        if version:
            return version.version
        content = "".join(sorted(path.read_text() for path in KNOWLEDGE_DIR.glob("*.md")))
        return f"repo-{sha256(content.encode()).hexdigest()[:12]}"

    @staticmethod
    def _profile(item: AthleteProfile | None) -> dict | None:
        if not item:
            return None
        return {
            "sports": item.sports,
            "experience_level": item.experience_level,
            "power_zones": item.power_zones,
            "heart_rate_zones": item.heart_rate_zones,
            "injuries_or_constraints": item.injuries_or_constraints,
        }

    @staticmethod
    def _goal(item: Goal | None) -> dict | None:
        return (
            {
                "title": item.title,
                "target_date": item.target_date,
                "sport": item.sport,
                "priority": item.priority,
                "goal_type": item.goal_type,
                "target_distance_meters": item.target_distance_meters,
                "target_elevation_meters": item.target_elevation_meters,
                "success_metric": item.success_metric,
                "details": item.details,
            }
            if item
            else None
        )

    @staticmethod
    def _activity(item: Activity) -> dict:
        return {
            "started_at": item.started_at,
            "sport": item.sport,
            "duration_seconds": item.duration_seconds,
            "distance_meters": item.distance_meters,
            "average_heart_rate": item.average_heart_rate,
            "average_power": item.average_power,
        }

    @staticmethod
    def _wellness(item: WellnessEntry) -> dict:
        return {
            "entry_date": item.entry_date,
            "sleep_hours": item.sleep_hours,
            "fatigue": item.fatigue,
            "soreness": item.soreness,
            "stress": item.stress,
            "mood": item.mood,
            "notes": item.notes,
        }

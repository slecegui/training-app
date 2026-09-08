"""Demo data available before authentication exists."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, User


def seed_demo_data(db: Session) -> None:
    user = db.scalar(select(User).where(User.email == "demo@training.online"))
    if not user:
        user = User(email="demo@training.online", name="Deportista demo")
        db.add(user)
        db.flush()
    if db.scalar(select(Activity.id).where(Activity.user_id == user.id)):
        return
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            Activity(
                user_id=user.id,
                name="Rodaje suave por el parque",
                sport="Carrera",
                started_at=now - timedelta(days=1),
                duration_seconds=2840,
                distance_meters=8100,
                elevation_gain_meters=73,
                average_heart_rate=143,
                average_cadence=171,
                calories=610,
                source_format="demo",
            ),
            Activity(
                user_id=user.id,
                name="Salida de carretera",
                sport="Ciclismo",
                started_at=now - timedelta(days=3),
                duration_seconds=5470,
                distance_meters=32100,
                elevation_gain_meters=412,
                average_heart_rate=136,
                average_power=184,
                average_cadence=82,
                calories=1050,
                source_format="demo",
            ),
            Activity(
                user_id=user.id,
                name="Series en pista",
                sport="Carrera",
                started_at=now - timedelta(days=6),
                duration_seconds=2560,
                distance_meters=6800,
                elevation_gain_meters=18,
                average_heart_rate=158,
                average_cadence=178,
                calories=520,
                source_format="demo",
            ),
        ]
    )
    db.commit()

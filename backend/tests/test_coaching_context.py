from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.coaching.context import ContextBuilder
from app.database import Base
from app.models import Activity, AthleteProfile, Goal, User, WellnessEntry


def test_context_never_includes_another_users_private_data() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = User(email="first@example.test", name="First")
        second = User(email="second@example.test", name="Second")
        db.add_all([first, second])
        db.flush()
        db.add_all(
            [
                AthleteProfile(user_id=first.id, sports=["Carrera"], availability={"mon": 60}),
                AthleteProfile(user_id=second.id, sports=["Ciclismo"], availability={"sun": 180}),
                Goal(user_id=first.id, title="10K", is_active=True),
                Goal(user_id=second.id, title="Gran fondo", is_active=True),
                Activity(
                    user_id=first.id,
                    name="Solo primera",
                    sport="Carrera",
                    started_at=datetime.now(timezone.utc),
                ),
                Activity(
                    user_id=second.id,
                    name="Secreto segunda",
                    sport="Ciclismo",
                    started_at=datetime.now(timezone.utc),
                ),
                WellnessEntry(user_id=first.id, entry_date=date.today(), fatigue=2),
                WellnessEntry(
                    user_id=second.id, entry_date=date.today(), fatigue=9, notes="Privado"
                ),
            ]
        )
        db.commit()
        context = ContextBuilder(db).build(first.id, "adjustment")
    assert context["athlete_profile"]["sports"] == ["Carrera"]
    assert context["availability"] == {"mon": 60}
    assert context["active_goal"]["title"] == "10K"
    assert [item["sport"] for item in context["recent_activities"]] == ["Carrera"]
    assert context["recent_wellness"] == [
        {
            "entry_date": date.today(),
            "sleep_hours": None,
            "fatigue": 2,
            "soreness": None,
            "stress": None,
            "mood": None,
            "notes": None,
        }
    ]
    assert "Secreto segunda" not in str(context)


def test_context_selects_only_documents_for_task() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="one@example.test", name="One")
        db.add(user)
        db.commit()
        context = ContextBuilder(db).build(user.id, "nutrition")
    assert set(context["methodology"]) == {"nutricion", "seguridad"}

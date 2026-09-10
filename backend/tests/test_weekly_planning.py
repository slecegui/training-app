"""Tests for weekly planning, deterministic rules, versioning, and user isolation."""

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.models import Activity, User


@pytest.fixture
def clients(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.database.SessionLocal", factory)
    return TestClient(app), TestClient(app)


def register_user(client: TestClient, name: str, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "una-clave-local-segura"},
    )
    assert response.status_code == 201
    return response.json()


def create_profile(
    client: TestClient,
    availability: dict = None,
    power_zones: dict = None,
    hr_zones: dict = None,
    preferences: dict = None,
) -> dict:
    payload = {
        "sports": ["Ciclismo"],
        "experience_level": "intermediate",
        "availability": availability or {"mon": 60, "wed": 90, "sat": 180},
        "power_zones": power_zones or {},
        "heart_rate_zones": hr_zones or {},
        "preferences": preferences or {},
        "injuries_or_constraints": None,
    }
    response = client.put("/api/profile", json=payload)
    assert response.status_code == 200
    return response.json()


def create_active_goal(client: TestClient, target_days_ahead: int = 30) -> dict:
    target_date = date.today() + timedelta(days=target_days_ahead)
    payload = {
        "title": "Objetivo A",
        "goal_type": "event",
        "target_date": str(target_date),
        "sport": "Ciclismo",
        "priority": "medium",
        "target_distance_meters": 100000.0,
        "target_elevation_meters": 1500.0,
        "success_metric": "Completar",
        "details": "Detalles del objetivo",
        "is_active": True,
    }
    response = client.post("/api/goals", json=payload)
    assert response.status_code == 201
    return response.json()


def test_generate_plan_success_and_idempotency(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)

    # 1. Normal generation with explicit reference_date
    ref_date = date(2026, 9, 9)  # A Wednesday
    response = c1.post("/api/plans/generate", json={"reference_date": str(ref_date)})
    assert response.status_code == 201
    plan_data = response.json()
    assert plan_data["version"] == 1
    assert plan_data["is_active"] is True
    # September 9 is Week 37. Next week is Week 38, Monday September 14 to Sunday September 20.
    assert plan_data["start_date"] == "2026-09-14"
    assert plan_data["end_date"] == "2026-09-20"
    assert len(plan_data["sessions"]) == 3  # available on Mon, Wed, Sat

    # 2. Idempotent check: calling generate again without force_regenerate should return the same plan
    response2 = c1.post("/api/plans/generate", json={"reference_date": str(ref_date)})
    assert response2.status_code == 201  # response_model matches WeeklyPlanRead
    plan_data2 = response2.json()
    assert plan_data2["id"] == plan_data["id"]
    assert plan_data2["version"] == 1


def test_generate_plan_rejection(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")

    # Rejection 1: missing profile entirely
    response = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    assert response.status_code == 404
    assert "Perfil deportivo no configurado" in response.json()["detail"]

    # Rejection 2: missing active goal
    create_profile(c1)
    response = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    assert response.status_code == 400
    assert "No hay ningún objetivo activo configurado" in response.json()["detail"]

    # Rejection 3: missing availability (all 0 or empty)
    create_active_goal(c1)
    create_profile(c1, availability={"mon": 0, "tue": 0})
    response = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    assert response.status_code == 400
    assert "La disponibilidad semanal no está configurada" in response.json()["detail"]

    # Rejection 4: missing activities and no reference_date provided
    create_profile(c1)  # restore valid profile/availability
    response = c1.post("/api/plans/generate", json={})
    assert response.status_code == 422
    assert (
        "No se dispone de actividades previas y no se ha especificado reference_date"
        in response.json()["detail"]
    )


def test_generate_plan_date_logic_with_activity(
    clients: tuple[TestClient, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)

    # Let's directly seed an activity in the DB via SessionLocal
    from app.database import SessionLocal

    db = SessionLocal()
    # Find user
    user = db.query(User).filter_by(email="user1@example.com").first()
    activity = Activity(
        user_id=user.id,
        name="Carrera test",
        sport="Ciclismo",
        started_at=datetime(2026, 9, 2, 10, 0, 0),  # Wednesday Sep 2 (Week 36)
        duration_seconds=3600,
    )
    db.add(activity)
    db.commit()
    db.close()

    # Generate plan: should use latest activity date to find next week (Week 37, Monday Sep 7 to Sunday Sep 13)
    # Even if reference_date is omitted!
    response = c1.post("/api/plans/generate", json={})
    assert response.status_code == 201
    plan_data = response.json()
    assert plan_data["start_date"] == "2026-09-07"
    assert plan_data["end_date"] == "2026-09-13"


def test_generate_plan_availability_and_limits(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    # Only Mon (30m) and Wed (60m) are available
    create_profile(c1, availability={"mon": 30, "wed": 60, "tue": 0})
    create_active_goal(c1)

    response = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    assert response.status_code == 201
    plan_data = response.json()
    sessions = plan_data["sessions"]
    assert len(sessions) == 2

    # Verify Mon session does not exceed 30m, Wed session does not exceed 60m
    for sess in sessions:
        sess_date = date.fromisoformat(sess["date"])
        weekday = sess_date.strftime("%a").lower()
        if weekday == "mon":
            assert sess["planned_duration"] <= 30
        elif weekday == "wed":
            assert sess["planned_duration"] <= 60


def test_generate_plan_metric_selection(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_active_goal(c1)

    # 1. Default without power or HR: RPE
    create_profile(c1, preferences={"has_power_meter": False})
    response = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    assert response.status_code == 201
    assert response.json()["sessions"][0]["intensity_metric"] == "rpe"

    # 2. Power zones but has_power_meter is False: RPE or HR (if HR exists)
    create_profile(c1, power_zones={"z2": 150}, preferences={"has_power_meter": False})
    response = c1.post(
        "/api/plans/generate", json={"reference_date": "2026-09-09", "force_regenerate": True}
    )
    assert response.status_code == 201
    assert response.json()["sessions"][0]["intensity_metric"] == "rpe"

    # 3. Power zones AND has_power_meter is True: Power
    create_profile(
        c1, power_zones={"z2": 150, "z1": 100, "z4": 200}, preferences={"has_power_meter": True}
    )
    response = c1.post(
        "/api/plans/generate", json={"reference_date": "2026-09-09", "force_regenerate": True}
    )
    assert response.status_code == 201
    assert response.json()["sessions"][0]["intensity_metric"] == "power"

    # 4. No Power meter, but has HR zones: HR
    create_profile(
        c1, hr_zones={"z2": 130, "z1": 110, "z4": 160}, preferences={"has_power_meter": False}
    )
    response = c1.post(
        "/api/plans/generate", json={"reference_date": "2026-09-09", "force_regenerate": True}
    )
    assert response.status_code == 201
    assert response.json()["sessions"][0]["intensity_metric"] == "hr"


def test_generate_plan_versioning_and_active_constraint(
    clients: tuple[TestClient, TestClient],
) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)

    ref_date = "2026-09-09"

    # Version 1
    r1 = c1.post("/api/plans/generate", json={"reference_date": ref_date})
    assert r1.status_code == 201
    p1 = r1.json()
    assert p1["version"] == 1
    assert p1["is_active"] is True

    # Version 2 (force_regenerate = True)
    r2 = c1.post(
        "/api/plans/generate",
        json={
            "reference_date": ref_date,
            "force_regenerate": True,
            "generation_reason": "Mal tiempo previsto",
        },
    )
    assert r2.status_code == 201
    p2 = r2.json()
    assert p2["version"] == 2
    assert p2["is_active"] is True
    assert p2["generation_reason"] == "Mal tiempo previsto"

    # Check that Version 1 is now inactive
    r3 = c1.get(f"/api/plans/{p1['id']}")
    assert r3.status_code == 200
    assert r3.json()["is_active"] is False

    # Check active endpoint
    r4 = c1.get(f"/api/plans/active?start_date={p1['start_date']}")
    assert r4.status_code == 200
    assert r4.json()["id"] == p2["id"]
    assert r4.json()["version"] == 2

    # Check history endpoint
    r5 = c1.get(f"/api/plans/history?goal_id={p1['active_goal_id']}&start_date={p1['start_date']}")
    assert r5.status_code == 200
    history = r5.json()
    assert len(history) == 2
    assert history[0]["version"] == 2
    assert history[1]["version"] == 1


def test_user_isolation(clients: tuple[TestClient, TestClient]) -> None:
    c1, c2 = clients
    register_user(c1, "User One", "user1@example.com")
    register_user(c2, "User Two", "user2@example.com")

    # Set up User 1 context and generate a plan
    create_profile(c1)
    g1 = create_active_goal(c1)
    r1 = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    p1 = r1.json()

    # User 2 tries to access User 1's plan -> 404 Not Found (Isolation!)
    r2 = c2.get(f"/api/plans/{p1['id']}")
    assert r2.status_code == 404

    # User 2 tries to fetch active plans by User 1's goal_id -> should reject or isolate
    r3 = c2.get(f"/api/plans/active?goal_id={g1['id']}&start_date={p1['start_date']}")
    # goal_id belongs to user 1, so user 2 cannot query it or gets 400 because they don't own the active goal
    assert r3.status_code == 400 or r3.status_code == 404


def test_iso_limits_and_timezone_boundary(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)

    # End of the year week boundary: December 28, 2026 is Monday.
    # If reference_date is Wednesday December 30, 2026, the next week Monday should be January 4, 2027.
    ref_date = "2026-12-30"
    response = c1.post("/api/plans/generate", json={"reference_date": ref_date})
    assert response.status_code == 201
    plan_data = response.json()
    assert plan_data["start_date"] == "2027-01-04"
    assert plan_data["end_date"] == "2027-01-10"

"""Tests for structured goals overhaul, legacy compatibility, and date validation."""

from datetime import datetime

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


def test_goal_overhaul_crud_and_validations(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")

    # 1. Successful creation with canonical codes and structured metric
    payload = {
        "title": "  Quebrantahuesos 2027  ",  # with spaces to test trim
        "goal_type": "sportive",
        "sport": "road_cycling",
        "start_date": "2026-09-10",
        "target_date": "2026-12-10",
        "priority": "high",
        "success_metric_type": "completar",
        "target_distance_meters": 200000.0,
        "target_elevation_meters": 3500.0,
        "is_active": True,
    }
    response = c1.post("/api/goals", json=payload)
    assert response.status_code == 201
    goal = response.json()
    assert goal["title"] == "Quebrantahuesos 2027"  # verified trim!
    assert goal["goal_type"] == "sportive"
    assert goal["sport"] == "road_cycling"
    assert goal["start_date"] == "2026-09-10"
    assert goal["success_metric"] == "Completar"  # auto-generated!

    # 2. Reject if start_date > target_date
    bad_payload = payload.copy()
    bad_payload["start_date"] = "2026-12-20"
    response = c1.post("/api/goals", json=bad_payload)
    assert response.status_code == 422  # validation error!

    # 3. Reject if title is pure spaces
    bad_payload = payload.copy()
    bad_payload["title"] = "   "
    response = c1.post("/api/goals", json=bad_payload)
    assert response.status_code == 422

    # 4. Reject unknown codes
    bad_payload = payload.copy()
    bad_payload["goal_type"] = "football"
    response = c1.post("/api/goals", json=bad_payload)
    assert response.status_code == 422


def test_activity_association_and_boundaries(clients: tuple[TestClient, TestClient]) -> None:
    c1, c2 = clients
    register_user(c1, "User One", "user1@example.com")
    register_user(c2, "User Two", "user2@example.com")

    # User 1 creates goal
    goal_payload = {
        "title": "Road Goal",
        "goal_type": "sportive",
        "sport": "road_cycling",
        "start_date": "2026-09-10",
        "target_date": "2026-09-20",
        "priority": "medium",
        "success_metric_type": "completar",
    }
    g1 = c1.post("/api/goals", json=goal_payload).json()

    # Seed activities
    from app.database import SessionLocal

    db = SessionLocal()
    u1 = db.query(User).filter_by(email="user1@example.com").first()
    u2 = db.query(User).filter_by(email="user2@example.com").first()

    # Act 1: Inside period
    act_inside = Activity(user_id=u1.id, name="Inside", started_at=datetime(2026, 9, 15, 10, 0, 0))
    # Act 2: Outside period (too early)
    act_outside_early = Activity(
        user_id=u1.id, name="Too early", started_at=datetime(2026, 9, 8, 10, 0, 0)
    )
    # Act 3: Outside period (too late)
    act_outside_late = Activity(
        user_id=u1.id, name="Too late", started_at=datetime(2026, 9, 22, 10, 0, 0)
    )
    # Act 4: Foreign user activity
    act_foreign = Activity(
        user_id=u2.id, name="Foreign", started_at=datetime(2026, 9, 15, 10, 0, 0)
    )

    db.add_all([act_inside, act_outside_early, act_outside_late, act_foreign])
    db.commit()
    act_inside_id = act_inside.id
    act_early_id = act_outside_early.id
    act_late_id = act_outside_late.id
    act_foreign_id = act_foreign.id
    db.close()

    # 1. Associate inside activity manually: SUCCESS
    r_assoc = c1.patch(f"/api/activities/{act_inside_id}/goal", json={"goal_id": g1["id"]})
    assert r_assoc.status_code == 200
    assert r_assoc.json()["goal_id"] == g1["id"]

    # 2. Reject association outside period (too early)
    r_assoc_early = c1.patch(f"/api/activities/{act_early_id}/goal", json={"goal_id": g1["id"]})
    assert r_assoc_early.status_code == 400
    assert "fuera del periodo" in r_assoc_early.json()["detail"]

    # 3. Reject association outside period (too late)
    r_assoc_late = c1.patch(f"/api/activities/{act_late_id}/goal", json={"goal_id": g1["id"]})
    assert r_assoc_late.status_code == 400
    assert "fuera del periodo" in r_assoc_late.json()["detail"]

    # 4. Reject foreign activity association
    r_assoc_foreign = c1.patch(f"/api/activities/{act_foreign_id}/goal", json={"goal_id": g1["id"]})
    assert r_assoc_foreign.status_code == 404

    # 5. List activities of the goal
    r_list = c1.get(f"/api/goals/{g1['id']}/activities")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1
    assert r_list.json()[0]["id"] == act_inside_id


def test_legacy_goals_and_sports_mapping_compatibility(
    clients: tuple[TestClient, TestClient],
) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")

    # Creating goal with legacy type 'event' and legacy sport 'Ciclismo'
    payload = {
        "title": "Legacy Goal",
        "goal_type": "event",
        "target_date": "2026-09-30",
        "sport": "Ciclismo",
        "priority": "medium",
        "success_metric": "Completar",
    }
    response = c1.post("/api/goals", json=payload)
    assert response.status_code == 201
    goal = response.json()
    # Verified automatic mapping to canonical codes
    assert goal["goal_type"] == "race"
    assert goal["sport"] == "cycling_general"
    assert goal["success_metric"] == "Completar"

"""Tests for planned session results linking, constraints, versioning, and user isolation."""

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.models import (
    Activity,
    User,
)


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


def create_profile(client: TestClient) -> dict:
    payload = {
        "sports": ["Ciclismo"],
        "experience_level": "intermediate",
        "availability": {"mon": 60, "wed": 90, "sat": 180},
        "power_zones": {},
        "heart_rate_zones": {},
        "preferences": {"has_power_meter": False},
        "injuries_or_constraints": None,
    }
    response = client.put("/api/profile", json=payload)
    assert response.status_code == 200
    return response.json()


def create_active_goal(client: TestClient) -> dict:
    target_date = date.today() + timedelta(days=30)
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


def seed_activity(user_email: str, name: str, started_at: datetime) -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    user = db.query(User).filter_by(email=user_email).first()
    act = Activity(
        user_id=user.id,
        name=name,
        sport="Ciclismo",
        started_at=started_at,
        duration_seconds=3600,
        distance_meters=30000.0,
    )
    db.add(act)
    db.commit()
    act_id = act.id
    db.close()
    return act_id


def test_session_initially_without_result(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)

    # Generate a plan
    r = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    assert r.status_code == 201
    plan = r.json()
    session = plan["sessions"][0]

    # Verify session has empty results in detailed response
    assert len(session["results"]) == 0

    # Get result endpoint should return 404
    r_get = c1.get(f"/api/planned-sessions/{session['id']}/result")
    assert r_get.status_code == 404
    assert r_get.json()["detail"] == "Resultado no registrado."


def test_record_results_valid_states(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)

    # Seed activities
    act1 = seed_activity("user1@example.com", "Entreno Mon", datetime(2026, 9, 14, 10, 0, 0))
    act2 = seed_activity("user1@example.com", "Entreno Wed", datetime(2026, 9, 16, 10, 0, 0))

    # Generate plan
    r = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    plan = r.json()
    sess_mon = plan["sessions"][0]  # Mon session
    sess_wed = plan["sessions"][1]  # Wed session
    sess_sat = plan["sessions"][2]  # Sat session

    # 1. COMPLETED con actividad propia
    r_comp = c1.post(
        f"/api/planned-sessions/{sess_mon['id']}/result",
        json={"status": "completed", "activity_id": act1, "notes": "Se sintió bien"},
    )
    assert r_comp.status_code == 201
    res_comp = r_comp.json()
    assert res_comp["status"] == "completed"
    assert res_comp["activity_id"] == act1
    assert res_comp["revision"] == 1
    assert res_comp["is_current"] is True

    # 2. OMITTED sin actividad y con motivo
    r_omit = c1.post(
        f"/api/planned-sessions/{sess_sat['id']}/result",
        json={"status": "omitted", "reason": "Lluvia intensa"},
    )
    assert r_omit.status_code == 201
    res_omit = r_omit.json()
    assert res_omit["status"] == "omitted"
    assert res_omit["activity_id"] is None
    assert res_omit["reason"] == "Lluvia intensa"

    # 3. PARTIAL con actividad y motivo
    r_part = c1.post(
        f"/api/planned-sessions/{sess_wed['id']}/result",
        json={"status": "partial", "activity_id": act2, "reason": "Pinchazo a mitad de entreno"},
    )
    assert r_part.status_code == 201
    res_part = r_part.json()
    assert res_part["status"] == "partial"
    assert res_part["activity_id"] == act2
    assert res_part["reason"] == "Pinchazo a mitad de entreno"


def test_record_results_rejections_and_invalid_payloads(
    clients: tuple[TestClient, TestClient],
) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)
    act1 = seed_activity("user1@example.com", "Entreno Mon", datetime(2026, 9, 14, 10, 0, 0))

    r = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    session_id = r.json()["sessions"][0]["id"]

    # Reject 1: completed without activity
    r_rej = c1.post(
        f"/api/planned-sessions/{session_id}/result",
        json={"status": "completed"},
    )
    assert r_rej.status_code == 422  # Pydantic model validation rejection

    # Reject 2: omitted with activity
    r_rej = c1.post(
        f"/api/planned-sessions/{session_id}/result",
        json={"status": "omitted", "activity_id": act1, "reason": "Lluvia"},
    )
    assert r_rej.status_code == 422

    # Reject 3: partial without reason
    r_rej = c1.post(
        f"/api/planned-sessions/{session_id}/result",
        json={"status": "partial", "activity_id": act1},
    )
    assert r_rej.status_code == 422

    # Reject 4: replaced without reason
    r_rej = c1.post(
        f"/api/planned-sessions/{session_id}/result",
        json={"status": "replaced", "activity_id": act1},
    )
    assert r_rej.status_code == 422


def test_activity_reuse_and_concurrency(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)
    act1 = seed_activity("user1@example.com", "Entreno Mon", datetime(2026, 9, 14, 10, 0, 0))

    r = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    plan = r.json()
    sess1 = plan["sessions"][0]
    sess2 = plan["sessions"][1]

    # Link act1 to sess1
    r_link1 = c1.post(
        f"/api/planned-sessions/{sess1['id']}/result",
        json={"status": "completed", "activity_id": act1},
    )
    assert r_link1.status_code == 201

    # Attempt to link the SAME act1 to sess2 -> Should fail (400 Bad Request)
    r_link2 = c1.post(
        f"/api/planned-sessions/{sess2['id']}/result",
        json={"status": "completed", "activity_id": act1},
    )
    assert r_link2.status_code == 400
    assert "ya está vinculada" in r_link2.json()["detail"]


def test_user_and_resource_isolation(clients: tuple[TestClient, TestClient]) -> None:
    c1, c2 = clients
    register_user(c1, "User One", "user1@example.com")
    register_user(c2, "User Two", "user2@example.com")

    # Set up User 1
    create_profile(c1)
    create_active_goal(c1)
    seed_activity("user1@example.com", "Entreno Mon 1", datetime(2026, 9, 14, 10, 0, 0))
    r1 = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    sess_u1_id = r1.json()["sessions"][0]["id"]

    # Set up User 2
    create_profile(c2)
    create_active_goal(c2)
    act2 = seed_activity("user2@example.com", "Entreno Mon 2", datetime(2026, 9, 14, 10, 0, 0))
    r2 = c2.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    r2.json()["sessions"][0]["id"]

    # User 2 tries to link results to User 1's session -> 404 (prevent enumeration!)
    r_link_foreign = c2.post(
        f"/api/planned-sessions/{sess_u1_id}/result",
        json={"status": "completed", "activity_id": act2},
    )
    assert r_link_foreign.status_code == 404

    # User 1 tries to link User 2's activity to their own session -> 404 (prevent enumeration!)
    r_link_foreign_act = c1.post(
        f"/api/planned-sessions/{sess_u1_id}/result",
        json={"status": "completed", "activity_id": act2},
    )
    assert r_link_foreign_act.status_code == 404


def test_versioned_corrections_and_history(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)
    act1 = seed_activity("user1@example.com", "Entreno 1", datetime(2026, 9, 14, 10, 0, 0))
    act2 = seed_activity("user1@example.com", "Entreno 2", datetime(2026, 9, 14, 11, 0, 0))

    r = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    sess_id = r.json()["sessions"][0]["id"]

    # 1. Revision 1 (First creation)
    r_rev1 = c1.post(
        f"/api/planned-sessions/{sess_id}/result",
        json={"status": "completed", "activity_id": act1},
    )
    assert r_rev1.status_code == 201
    p1 = r_rev1.json()
    assert p1["revision"] == 1
    assert p1["is_current"] is True

    # 2. Try to correct without correction_reason -> should reject (400)
    r_corr_fail = c1.post(
        f"/api/planned-sessions/{sess_id}/result",
        json={"status": "partial", "activity_id": act2, "reason": "Pinchazo"},
    )
    assert r_corr_fail.status_code == 400
    assert "motivo de corrección" in r_corr_fail.json()["detail"]

    # 3. Revision 2 (Valid Correction)
    r_rev2 = c1.post(
        f"/api/planned-sessions/{sess_id}/result",
        json={
            "status": "partial",
            "activity_id": act2,
            "reason": "Pinchazo",
            "correction_reason": "Equivocación de actividad deportiva",
        },
    )
    assert r_rev2.status_code == 201
    p2 = r_rev2.json()
    assert p2["revision"] == 2
    assert p2["is_current"] is True
    assert p2["supersedes_result_id"] == p1["id"]

    # 4. Check active result is Revision 2
    r_get = c1.get(f"/api/planned-sessions/{sess_id}/result")
    assert r_get.status_code == 200
    assert r_get.json()["revision"] == 2

    # 5. Check history in mutable form: should show Revision 2 and Revision 1
    r_hist = c1.get(f"/api/planned-sessions/{sess_id}/result/history")
    assert r_hist.status_code == 200
    hist = r_hist.json()
    assert len(hist) == 2
    assert hist[0]["revision"] == 2
    assert hist[0]["is_current"] is True
    assert hist[1]["revision"] == 1
    assert hist[1]["is_current"] is False


def test_results_retained_in_historical_plan_versions(
    clients: tuple[TestClient, TestClient],
) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)
    act1 = seed_activity("user1@example.com", "Entreno 1", datetime(2026, 9, 14, 10, 0, 0))

    # Version 1 plan
    r_v1 = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    p1 = r_v1.json()
    sess_id = p1["sessions"][0]["id"]

    # Link result to session in Version 1
    c1.post(
        f"/api/planned-sessions/{sess_id}/result",
        json={"status": "completed", "activity_id": act1},
    )

    # Regenerate plan -> creates Version 2
    r_v2 = c1.post(
        "/api/plans/generate", json={"reference_date": "2026-09-09", "force_regenerate": True}
    )
    p2 = r_v2.json()
    assert p2["version"] == 2

    # Fetch Version 1 again: its session should still retain its result!
    r_fetch_v1 = c1.get(f"/api/plans/{p1['id']}")
    assert r_fetch_v1.status_code == 200
    p1_fetched = r_fetch_v1.json()
    # Check that session of version 1 has results
    sess_v1_fetched = p1_fetched["sessions"][0]
    assert len(sess_v1_fetched["results"]) == 1
    assert sess_v1_fetched["results"][0]["status"] == "completed"


def test_unauthenticated_access(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    # Request without authenticating first
    response = c1.post("/api/planned-sessions/1/result", json={"status": "completed"})
    assert response.status_code == 401

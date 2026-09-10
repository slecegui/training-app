"""Tests for deterministic training compliance (duration-v1), versioning, and constraints."""

from datetime import date, datetime, timedelta
from decimal import Decimal

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
        "availability": {"mon": 60, "wed": 120, "sat": 180},
        "power_zones": {},
        "heart_rate_zones": {},
        "preferences": {"has_power_meter": False},
        "injuries_or_constraints": None,
    }
    response = client.put("/api/profile", json=payload)
    assert response.status_code == 200
    return response.json()


def create_active_goal(client: TestClient, target_days_ahead: int = 40) -> dict:
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


def seed_activity(user_email: str, name: str, started_at: datetime, duration_seconds: int) -> int:
    from app.database import SessionLocal

    db = SessionLocal()
    user = db.query(User).filter_by(email=user_email).first()
    act = Activity(
        user_id=user.id,
        name=name,
        sport="Ciclismo",
        started_at=started_at,
        duration_seconds=duration_seconds,
        distance_meters=30000.0,
    )
    db.add(act)
    db.commit()
    act_id = act.id
    db.close()
    return act_id


def test_compliance_math_rules_and_precision(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)

    # Seed activities for partial and replaced
    # 1. Partial: 45m (2700s) on planned 60m (2700/3600 = 0.75 credit)
    act_partial = seed_activity(
        "user1@example.com", "Partial Mon", datetime(2026, 9, 14, 10, 0, 0), 2700
    )
    # 2. Replaced with more than planned: 130m (7800s) on planned 120m (limit to 1.0 credit)
    act_replaced = seed_activity(
        "user1@example.com", "More Wed", datetime(2026, 9, 16, 10, 0, 0), 7800
    )

    # Generate plan (Mon=36m, Wed=72m, Sat=108m - total = 216m)
    # Let's see: user availability sum is 360m (60+120+180). Multiplier for intermediate is 0.7 = 252m target standard.
    # In base/build phase standard 252m target is allocated. Let's inspect generated sessions:
    r = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    assert r.status_code == 201
    plan = r.json()
    sess_mon = plan["sessions"][0]  # Mon
    sess_wed = plan["sessions"][1]  # Wed
    sess_sat = plan["sessions"][2]  # Sat

    # 1. Mon is Partial
    c1.post(
        f"/api/planned-sessions/{sess_mon['id']}/result",
        json={
            "status": "partial",
            "activity_id": act_partial,
            "reason": "Corto de tiempo",
        },
    )

    # 2. Wed is Replaced
    c1.post(
        f"/api/planned-sessions/{sess_wed['id']}/result",
        json={
            "status": "replaced",
            "activity_id": act_replaced,
            "reason": "Cambio de ruta",
        },
    )

    # 3. Sat is Omitted
    c1.post(
        f"/api/planned-sessions/{sess_sat['id']}/result",
        json={
            "status": "omitted",
            "reason": "Fatiga extrema",
        },
    )

    # Calculate compliance
    r_calc = c1.post(f"/api/plans/{plan['id']}/compliance/calculate")
    assert r_calc.status_code == 201
    summary = r_calc.json()

    assert summary["status"] == "complete"
    # Verify precision dynamically
    w1 = Decimal(sess_mon["planned_duration"])
    w2 = Decimal(sess_wed["planned_duration"])
    w3 = Decimal(sess_sat["planned_duration"])

    # Mon: partial (45m = 2700s) on planned w1
    mon_credit = min(Decimal("2700") / (w1 * Decimal("60")), Decimal("1.0000")).quantize(
        Decimal("0.0001")
    )
    # Wed: replaced (130m = 7800s) on planned w2
    wed_credit = min(Decimal("7800") / (w2 * Decimal("60")), Decimal("1.0000")).quantize(
        Decimal("0.0001")
    )
    # Sat: omitted
    sat_credit = Decimal("0.0000")

    expected_numerator = w1 * mon_credit + w2 * wed_credit + w3 * sat_credit
    expected_denominator = w1 + w2 + w3
    expected_percentage = (Decimal("100") * expected_numerator / expected_denominator).quantize(
        Decimal("0.01")
    )

    assert Decimal(summary["numerator"]) == expected_numerator
    assert Decimal(summary["denominator"]) == expected_denominator
    assert Decimal(summary["percentage"]) == expected_percentage


def test_compliance_incomplete_when_results_missing(clients: tuple[TestClient, TestClient]) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)

    r = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    plan = r.json()

    # Link results to Mon but leave Wed/Sat empty
    c1.post(
        f"/api/planned-sessions/{plan['sessions'][0]['id']}/result",
        json={
            "status": "completed",
            "activity_id": seed_activity(
                "user1@example.com", "Act Mon", datetime(2026, 9, 14, 10, 0, 0), 3600
            ),
        },
    )

    r_calc = c1.post(f"/api/plans/{plan['id']}/compliance/calculate")
    assert r_calc.status_code == 201
    summary = r_calc.json()

    assert summary["status"] == "incomplete"
    assert summary["percentage"] is None
    # Component for Mon should have weight/credit, while Wed/Sat have no credit but are still persisted as components!
    assert len(summary["components"]) == 3
    for comp in summary["components"]:
        if comp["planned_session_id"] == plan["sessions"][0]["id"]:
            assert Decimal(comp["credit"]) == Decimal("1.0000")
        else:
            assert comp["credit"] is None
            assert "pendiente" in comp["exclusion_or_error_reason"]


def test_compliance_idempotency_and_versioned_corrections(
    clients: tuple[TestClient, TestClient],
) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    create_active_goal(c1)
    act1 = seed_activity("user1@example.com", "Entreno 1", datetime(2026, 9, 14, 10, 0, 0), 3600)
    seed_activity("user1@example.com", "Entreno 2", datetime(2026, 9, 14, 10, 0, 0), 1800)

    r = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    plan = r.json()
    sess_id = plan["sessions"][0]["id"]

    # Limit result to omitted so we have a fully completed plan
    c1.post(
        f"/api/planned-sessions/{sess_id}/result", json={"status": "omitted", "reason": "Lluvia"}
    )
    # Wed/Sat omission so we can evaluate complete status
    c1.post(
        f"/api/planned-sessions/{plan['sessions'][1]['id']}/result",
        json={"status": "omitted", "reason": "Lluvia"},
    )
    c1.post(
        f"/api/planned-sessions/{plan['sessions'][2]['id']}/result",
        json={"status": "omitted", "reason": "Lluvia"},
    )

    # 1. First calculation: Revision 1
    r_calc1 = c1.post(f"/api/plans/{plan['id']}/compliance/calculate")
    assert r_calc1.status_code == 201
    sum1 = r_calc1.json()
    assert sum1["revision"] == 1
    assert sum1["is_current"] is True

    # 2. Call again: Should be fully IDEMPOTENT (no new revision created)
    r_calc2 = c1.post(f"/api/plans/{plan['id']}/compliance/calculate")
    assert r_calc2.status_code == 201
    sum2 = r_calc2.json()
    assert sum2["id"] == sum1["id"]
    assert sum2["revision"] == 1

    # 3. Correct result on Mon session (requires correction_reason)
    c1.post(
        f"/api/planned-sessions/{sess_id}/result",
        json={
            "status": "completed",
            "activity_id": act1,
            "correction_reason": "Se realizó pero se marcó mal",
        },
    )

    # 4. Calculate again: Fingerprint changed -> Revision 2 created!
    r_calc3 = c1.post(f"/api/plans/{plan['id']}/compliance/calculate")
    assert r_calc3.status_code == 201
    sum3 = r_calc3.json()
    assert sum3["revision"] == 2
    assert sum3["is_current"] is True

    # 5. Correct back to original (omitted) but with unique revision -> Fingerprint changes, Revision 3 created!
    c1.post(
        f"/api/planned-sessions/{sess_id}/result",
        json={
            "status": "omitted",
            "reason": "Lluvia",
            "correction_reason": "Corrección de corrección",
        },
    )
    r_calc4 = c1.post(f"/api/plans/{plan['id']}/compliance/calculate")
    assert r_calc4.status_code == 201
    sum4 = r_calc4.json()
    assert sum4["revision"] == 3


def test_user_compliance_isolation(clients: tuple[TestClient, TestClient]) -> None:
    c1, c2 = clients
    register_user(c1, "User One", "user1@example.com")
    register_user(c2, "User Two", "user2@example.com")

    # Set up User 1 context
    create_profile(c1)
    create_active_goal(c1)
    r1 = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    plan1_id = r1.json()["id"]

    # User 2 tries to trigger calculation or get compliance of User 1's plan -> 404
    r_calc_foreign = c2.post(f"/api/plans/{plan1_id}/compliance/calculate")
    assert r_calc_foreign.status_code == 404

    r_get_foreign = c2.get(f"/api/plans/{plan1_id}/compliance")
    assert r_get_foreign.status_code == 404


def test_goal_aggregated_compliance_and_date_boundaries(
    clients: tuple[TestClient, TestClient],
) -> None:
    c1, _ = clients
    register_user(c1, "User One", "user1@example.com")
    create_profile(c1)
    goal = create_active_goal(c1)
    goal_id = goal["id"]

    # Generate 1st plan (Monday Sep 14 to Sunday Sep 20)
    r_p1 = c1.post("/api/plans/generate", json={"reference_date": "2026-09-09"})
    plan1 = r_p1.json()

    # Mark all sessions of plan 1 as omitted to make it complete (percentage = 0%)
    for s in plan1["sessions"]:
        c1.post(
            f"/api/planned-sessions/{s['id']}/result",
            json={"status": "omitted", "reason": "Lluvia"},
        )

    # Regenerate plan 1 -> creates a substitution version. The substitutions must be EXCLUDED! Only active/vigente plans included.
    # To do this, let's keep plan 1 active. Actually, let's generate another week:
    # Sep 21 is Monday.
    r_p2 = c1.post("/api/plans/generate", json={"reference_date": "2026-09-17"})
    plan2 = r_p2.json()
    assert plan2["start_date"] == "2026-09-21"

    # Mark all sessions of plan 2 as completed (percentage = 100%)
    for s in plan2["sessions"]:
        act_id = seed_activity(
            "user1@example.com",
            "Entreno Week2",
            datetime(2026, 9, 21, 10, 0, 0),
            s["planned_duration"] * 60,
        )
        c1.post(
            f"/api/planned-sessions/{s['id']}/result",
            json={"status": "completed", "activity_id": act_id},
        )

    # Calculate Goal-level compliance over Sep 14 to Sep 27 range (includes both Sep 14 and Sep 21 weeks)
    r_gcalc = c1.post(
        f"/api/goals/{goal_id}/compliance/calculate",
        json={"from_date": "2026-09-14", "to_date": "2026-09-27"},
    )
    assert r_gcalc.status_code == 201
    gsum = r_gcalc.json()
    assert gsum["scope"] == "goal"
    assert gsum["status"] == "complete"
    assert gsum["from_date"] == "2026-09-14"
    assert gsum["to_date"] == "2026-09-27"

    # Expected goal percentage: total completed minutes of plan 2 / total planned minutes of plan 1 + plan 2
    # w_plan1 + w_plan2. w_plan1 (omitted = 0 credit), w_plan2 (completed = full credit).
    # expected_perc = 100 * w_plan2 / (w_plan1 + w_plan2)
    expected_num = Decimal(sum(s["planned_duration"] for s in plan2["sessions"]))
    expected_den = Decimal(sum(s["planned_duration"] for s in plan1["sessions"])) + expected_num
    expected_pct = (Decimal("100") * expected_num / expected_den).quantize(Decimal("0.01"))

    assert Decimal(gsum["numerator"]) == expected_num
    assert Decimal(gsum["denominator"]) == expected_den
    assert Decimal(gsum["percentage"]) == expected_pct

    # Calculate with a different interval that only includes week 2
    r_gcalc2 = c1.post(
        f"/api/goals/{goal_id}/compliance/calculate",
        json={"from_date": "2026-09-21", "to_date": "2026-09-27"},
    )
    assert r_gcalc2.status_code == 201
    gsum2 = r_gcalc2.json()
    assert Decimal(gsum2["percentage"]) == Decimal("100.00")

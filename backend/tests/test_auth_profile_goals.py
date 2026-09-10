from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app


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


def register(client: TestClient, name: str, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "una-clave-local-segura"},
    )
    assert response.status_code == 201
    return response.json()


def goal_payload(title: str, active: bool = False) -> dict:
    return {
        "title": title,
        "goal_type": "evento",
        "target_date": str(date.today() + timedelta(days=30)),
        "sport": "Ciclismo",
        "priority": "high",
        "target_distance_meters": 100000,
        "target_elevation_meters": 1200,
        "success_metric": "Terminar en menos de 5 horas",
        "details": "Prueba",
        "is_active": active,
    }


def test_auth_lifecycle_and_session_required(clients: tuple[TestClient, TestClient]) -> None:
    client, _ = clients
    assert client.get("/api/activities").status_code == 401
    user = register(client, "Ana", "ana@example.test")
    assert (
        client.post(
            "/api/auth/register",
            json={
                "name": "Otra Ana",
                "email": "ANA@example.test",
                "password": "una-clave-local-segura",
            },
        ).status_code
        == 409
    )
    assert client.get("/api/auth/session").json()["id"] == user["id"]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/session").status_code == 401
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/goals").status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "ana@example.test", "password": "una-clave-local-segura"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": "ana@example.test", "password": "incorrecta"}
        ).status_code
        == 401
    )


def test_profile_goal_crud_activation_and_user_isolation(
    clients: tuple[TestClient, TestClient],
) -> None:
    first, second = clients
    register(first, "Ana", "ana@example.test")
    register(second, "Beto", "beto@example.test")
    profile = {
        "sports": ["Ciclismo"],
        "experience_level": "intermedio",
        "availability": {"sat": 180},
        "power_zones": {"z2": 180},
        "heart_rate_zones": {"z2": 145},
        "preferences": {"indoor": False},
        "injuries_or_constraints": "Ninguna",
    }
    assert first.put("/api/profile", json=profile).status_code == 200
    assert second.get("/api/profile").json()["sports"] == []
    first_goal = first.post("/api/goals", json=goal_payload("Marcha A", True)).json()
    second_goal = second.post("/api/goals", json=goal_payload("Secreto B", True)).json()
    assert first.get("/api/goals").json()[0]["title"] == "Marcha A"
    assert first.get(f"/api/goals/{second_goal['id']}").status_code == 404
    assert (
        first.put(f"/api/goals/{second_goal['id']}", json=goal_payload("Ataque")).status_code == 404
    )
    assert first.delete(f"/api/goals/{second_goal['id']}").status_code == 404
    next_goal = first.post("/api/goals", json=goal_payload("Marcha C", True)).json()
    goals = first.get("/api/goals").json()
    assert [goal["id"] for goal in goals if goal["is_active"]] == [next_goal["id"]]
    assert first.post(f"/api/goals/{first_goal['id']}/activate").status_code == 200
    assert [goal["id"] for goal in first.get("/api/goals").json() if goal["is_active"]] == [
        first_goal["id"]
    ]
    assert second.get(f"/api/goals/{second_goal['id']}").status_code == 200


def test_profile_and_goal_validation(clients: tuple[TestClient, TestClient]) -> None:
    client, _ = clients
    register(client, "Ana", "validation@example.test")
    assert client.put("/api/profile", json={"availability": {"noday": 60}}).status_code == 422
    invalid = goal_payload("Malo")
    invalid["target_distance_meters"] = 0
    assert client.post("/api/goals", json=invalid).status_code == 422
    invalid = goal_payload("Pasado")
    invalid["target_date"] = str(date.today() - timedelta(days=1))
    assert client.post("/api/goals", json=invalid).status_code == 422

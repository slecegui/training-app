from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base
from app.main import app
from app.models import Activity


@pytest.fixture
def activity_clients(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[TestClient, TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.database.SessionLocal", factory)
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path / "uploads"))
    return TestClient(app), TestClient(app), factory


def register(client: TestClient, name: str, email: str) -> int:
    response = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "una-clave-local-segura"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def gpx_file(name: str) -> tuple[str, bytes, str]:
    contents = (
        f"<gpx><trk><name>{name}</name><trkseg>"
        "<trkpt lat='40.0' lon='-3.0'><ele>10</ele>"
        "<time>2026-09-01T08:00:00Z</time></trkpt>"
        "<trkpt lat='40.1' lon='-3.1'><ele>25</ele>"
        "<time>2026-09-01T08:10:00Z</time></trkpt>"
        "</trkseg></trk></gpx>"
    ).encode()
    return f"{name}.gpx", contents, "application/gpx+xml"


def test_activity_endpoints_require_authentication() -> None:
    client = TestClient(app)
    assert client.get("/api/activities").status_code == 401
    assert client.get("/api/activities/1").status_code == 401
    assert (
        client.post("/api/activities/import", files={"file": gpx_file("ride")}).status_code == 401
    )


def test_imported_activities_and_files_are_isolated_by_authenticated_user(
    activity_clients: tuple[TestClient, TestClient, sessionmaker],
) -> None:
    first, second, factory = activity_clients
    first_user_id = register(first, "Ana", "ana-activities@example.test")
    second_user_id = register(second, "Beto", "beto-activities@example.test")

    first_response = first.post("/api/activities/import", files={"file": gpx_file("private-ana")})
    second_response = second.post(
        "/api/activities/import", files={"file": gpx_file("private-beto")}
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first_activity = first_response.json()
    second_activity = second_response.json()
    assert first_activity["user_id"] == first_user_id
    assert second_activity["user_id"] == second_user_id

    assert [item["name"] for item in first.get("/api/activities").json()] == ["private-ana"]
    assert [item["name"] for item in second.get("/api/activities").json()] == ["private-beto"]
    assert first.get(f"/api/activities/{second_activity['id']}").status_code == 404
    assert second.get(f"/api/activities/{first_activity['id']}").status_code == 404

    with factory() as db:
        rows = list(db.scalars(select(Activity).order_by(Activity.id)))
        assert rows[0].stored_filename != rows[1].stored_filename
        assert rows[0].stored_filename is not None
        assert rows[1].stored_filename is not None
        upload_dir = Path(get_settings().upload_dir)
        assert (upload_dir / rows[0].stored_filename).read_bytes() != b""
        assert (upload_dir / rows[1].stored_filename).read_bytes() != b""


def test_failed_import_does_not_leave_a_file(
    activity_clients: tuple[TestClient, TestClient, sessionmaker],
) -> None:
    client, _, _ = activity_clients
    register(client, "Ana", "ana-invalid@example.test")
    upload_dir = Path(get_settings().upload_dir)

    response = client.post(
        "/api/activities/import",
        files={"file": ("broken.gpx", b"not xml", "application/gpx+xml")},
    )

    assert response.status_code == 422
    assert list(upload_dir.iterdir()) == []


def test_activity_delete_is_private_and_removes_its_imported_file(
    activity_clients: tuple[TestClient, TestClient, sessionmaker],
) -> None:
    first, second, factory = activity_clients
    register(first, "Ana", "ana-delete@example.test")
    register(second, "Beto", "beto-delete@example.test")
    activity = first.post("/api/activities/import", files={"file": gpx_file("delete-me")}).json()
    assert second.delete(f"/api/activities/{activity['id']}").status_code == 404
    with factory() as db:
        stored = db.get(Activity, activity["id"]).stored_filename
    assert first.delete(f"/api/activities/{activity['id']}").status_code == 204
    assert first.get(f"/api/activities/{activity['id']}").status_code == 404
    assert not (Path(get_settings().upload_dir) / stored).exists()


def test_goal_route_gpx_validates_upload_and_is_private(
    activity_clients: tuple[TestClient, TestClient, sessionmaker],
) -> None:
    first, second, _ = activity_clients
    register(first, "Ana", "ana-route@example.test")
    register(second, "Beto", "beto-route@example.test")
    payload = {"title": "Ruta privada", "goal_type": "race", "start_date": "2026-09-10", "target_date": "2027-09-10", "sport": "gravel", "priority": "high", "is_active": False}
    goal = first.post("/api/goals", json=payload).json()
    valid = first.post(f"/api/goals/{goal['id']}/route-gpx", files={"file": gpx_file("route")})
    assert valid.status_code == 200
    assert valid.json()["route_distance_meters"] is not None
    assert second.post(f"/api/goals/{goal['id']}/route-gpx", files={"file": gpx_file("intrusion")}).status_code == 404
    assert first.post(f"/api/goals/{goal['id']}/route-gpx", files={"file": ("bad.txt", b"x", "text/plain")}).status_code == 400
    assert first.post(f"/api/goals/{goal['id']}/route-gpx", files={"file": ("broken.gpx", b"<!DOCTYPE x>", "application/gpx+xml")}).status_code == 422
    assert first.delete(f"/api/goals/{goal['id']}/route-gpx").status_code == 204

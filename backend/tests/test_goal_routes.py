from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base
from app.main import app
from app.models import GoalRoute
from app.services.goal_gpx_service import MAX_GPX_BYTES


@pytest.fixture
def goal_route_clients(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[TestClient, TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
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


def create_goal(client: TestClient, title: str = "Objetivo de rutas") -> dict:
    response = client.post(
        "/api/goals",
        json={
            "title": title,
            "goal_type": "race",
            "sport": "road_cycling",
            "start_date": "2027-01-01",
            "target_date": "2027-01-10",
            "priority": "high",
            "target_distance_meters": 200000,
            "target_elevation_meters": 3500,
            "success_metric_type": "completar",
        },
    )
    assert response.status_code == 201
    return response.json()


def gpx_file(name: str, contents: bytes | None = None) -> tuple[str, bytes, str]:
    contents = (
        contents
        or (
            f"<gpx><trk><name>{name}</name><trkseg>"
            "<trkpt lat='40.0' lon='-3.0'><ele>10</ele></trkpt>"
            "<trkpt lat='40.1' lon='-3.1'><ele>25</ele></trkpt>"
            "</trkseg></trk></gpx>"
        ).encode()
    )
    return f"{name}.gpx", contents, "application/gpx+xml"


def test_multiple_routes_are_created_listed_and_preserve_manual_goal_values(
    goal_route_clients: tuple[TestClient, TestClient, sessionmaker],
) -> None:
    client, _, _ = goal_route_clients
    register(client, "Ana", "ana-routes@example.test")
    goal = create_goal(client)

    first = client.post(
        f"/api/goals/{goal['id']}/routes",
        files={"file": gpx_file("stage-one")},
        data={"stage_label": "Día 1", "display_order": "1"},
    )
    second = client.post(
        f"/api/goals/{goal['id']}/routes",
        files={"file": gpx_file("stage-two")},
        data={"stage_label": "Día 2", "display_order": "2"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    routes = client.get(f"/api/goals/{goal['id']}/routes")
    assert routes.status_code == 200
    assert [route["stage_label"] for route in routes.json()] == ["Día 1", "Día 2"]
    assert all(route["distance_meters"] is not None for route in routes.json())

    detail = client.get(f"/api/goals/{goal['id']}").json()
    assert len(detail["routes"]) == 2
    assert detail["target_distance_meters"] == 200000
    assert detail["target_elevation_meters"] == 3500


def test_route_isolation_patch_and_single_delete_remove_only_owned_file(
    goal_route_clients: tuple[TestClient, TestClient, sessionmaker],
) -> None:
    first, second, factory = goal_route_clients
    first_user = register(first, "Ana", "ana-route-isolation@example.test")
    register(second, "Beto", "beto-route-isolation@example.test")
    goal = create_goal(first, "Ruta privada")
    route = first.post(
        f"/api/goals/{goal['id']}/routes", files={"file": gpx_file("private")}
    ).json()
    route_id = route["id"]

    assert second.get(f"/api/goals/{goal['id']}/routes").status_code == 404
    assert (
        second.patch(
            f"/api/goals/{goal['id']}/routes/{route_id}",
            json={"stage_label": "intrusión", "display_order": 3},
        ).status_code
        == 404
    )
    assert second.delete(f"/api/goals/{goal['id']}/routes/{route_id}").status_code == 404

    with factory() as db:
        stored = db.scalar(select(GoalRoute).where(GoalRoute.id == route_id))
        assert stored is not None
        stored_name = stored.stored_filename
        route_path = Path(get_settings().upload_dir) / "goal-routes" / str(first_user) / stored_name

    patched = first.patch(
        f"/api/goals/{goal['id']}/routes/{route_id}",
        json={"stage_label": "Etapa principal", "display_order": 4},
    )
    assert patched.status_code == 200
    assert patched.json()["stage_label"] == "Etapa principal"
    assert patched.json()["distance_meters"] is not None

    assert first.delete(f"/api/goals/{goal['id']}/routes/{route_id}").status_code == 204
    assert not route_path.exists()
    assert first.get(f"/api/goals/{goal['id']}/routes").json() == []


@pytest.mark.parametrize(
    ("filename", "contents", "content_type", "status"),
    [
        ("route.txt", b"not gpx", "text/plain", 400),
        ("broken.gpx", b"not xml", "application/gpx+xml", 422),
        (
            "external.gpx",
            b"<!DOCTYPE gpx [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><gpx>&x;</gpx>",
            "application/gpx+xml",
            422,
        ),
        (
            "coordinates.gpx",
            b"<gpx><trk><trkpt lat='91' lon='0'/></trk></gpx>",
            "application/gpx+xml",
            422,
        ),
        ("large.gpx", b"x" * (MAX_GPX_BYTES + 1), "application/gpx+xml", 422),
    ],
)
def test_route_upload_validation_is_preserved(
    goal_route_clients: tuple[TestClient, TestClient, sessionmaker],
    filename: str,
    contents: bytes,
    content_type: str,
    status: int,
) -> None:
    client, _, _ = goal_route_clients
    register(client, "Ana", f"ana-validation-{filename}@example.test")
    goal = create_goal(client, filename)

    response = client.post(
        f"/api/goals/{goal['id']}/routes", files={"file": (filename, contents, content_type)}
    )

    assert response.status_code == status
    assert client.get(f"/api/goals/{goal['id']}/routes").json() == []


def test_legacy_single_route_endpoints_remain_compatible_and_project_first_route(
    goal_route_clients: tuple[TestClient, TestClient, sessionmaker],
) -> None:
    client, _, _ = goal_route_clients
    register(client, "Ana", "ana-legacy-route@example.test")
    goal = create_goal(client, "Compatibilidad")

    response = client.post(f"/api/goals/{goal['id']}/route-gpx", files={"file": gpx_file("legacy")})

    assert response.status_code == 200
    body = response.json()
    assert body["route_original_filename"] == "legacy.gpx"
    assert len(body["routes"]) == 1
    assert body["target_distance_meters"] == 200000
    assert client.delete(f"/api/goals/{goal['id']}/route-gpx").status_code == 204
    assert client.get(f"/api/goals/{goal['id']}/routes").json() == []

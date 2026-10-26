"""Experimental Garmin connection must keep account secrets and activities user-scoped."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base
from app.main import app
from app.models import Activity, GarminConnection


def activity_archive() -> bytes:
    gpx = (
        b"<gpx><trk><name>Ride</name><trkseg>"
        b"<trkpt lat='40' lon='-3'><time>2026-09-14T08:00:00Z</time></trkpt>"
        b"<trkpt lat='40.1' lon='-3.1'><time>2026-09-14T08:30:00Z</time></trkpt>"
        b"</trkseg></trk></gpx>"
    )
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("nested/activity.gpx", gpx)
    return stream.getvalue()


class FakeGarmin:
    class ActivityDownloadFormat:
        ORIGINAL = "original"

    def __init__(self, email=None, password=None, return_on_mfa=False, **kwargs):
        self.email = email
        self.password = password
        self.return_on_mfa = return_on_mfa
        self.client = self

    def login(self, tokens=None):
        if tokens:
            assert '"secret"' in tokens
            return None, None
        if self.email == "mfa@example.test":
            return "needs_mfa", None
        return None, None

    def resume_login(self, state, code):
        assert code == "123456"
        return None, None

    def dumps(self):
        return '{"refresh_token":"secret"}'

    def get_activities(self, start=0, limit=20):
        return [{"activityId": "123", "activityName": "Salida de prueba"}] if start == 0 else []

    def download_activity(self, activity_id, dl_fmt=None):
        assert activity_id == "123"
        assert dl_fmt == "original"
        return activity_archive()


@pytest.fixture
def clients(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.database.SessionLocal", factory)
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(get_settings(), "garmin_token_key", Fernet.generate_key().decode())
    monkeypatch.setattr("app.services.garmin_sync.Garmin", FakeGarmin)
    return TestClient(app), TestClient(app), factory


def register(client: TestClient, name: str, email: str) -> int:
    response = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "una-clave-local-segura"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_garmin_requires_authentication():
    client = TestClient(app)
    assert client.get("/api/integrations/garmin/status").status_code == 401
    assert client.post("/api/integrations/garmin/connect", json={"email": "a@b.c", "password": "x"}).status_code == 401
    assert client.post("/api/integrations/garmin/sync").status_code == 401
    assert client.delete("/api/integrations/garmin").status_code == 401


def test_garmin_connection_sync_deduplicates_and_isolates_users(clients):
    first, second, factory = clients
    first_id = register(first, "Ana", "ana-garmin@example.test")
    second_id = register(second, "Beto", "beto-garmin@example.test")
    assert first.post(
        "/api/integrations/garmin/connect",
        json={"email": "ana@example.test", "password": "garmin-secret"},
    ).json() == {"status": "connected"}
    assert first.get("/api/integrations/garmin/status").json()["connected"] is True
    assert second.get("/api/integrations/garmin/status").json()["connected"] is False
    with factory() as db:
        connection = db.scalar(select(GarminConnection).where(GarminConnection.user_id == first_id))
        assert connection is not None
        assert "secret" not in connection.encrypted_tokens
        assert "garmin-secret" not in connection.encrypted_tokens

    assert first.post("/api/integrations/garmin/sync").json() == {"imported": 1, "skipped": 0, "failed": 0}
    assert first.post("/api/integrations/garmin/sync").json() == {"imported": 0, "skipped": 1, "failed": 0}
    assert second.post("/api/integrations/garmin/sync").status_code == 503
    assert [a["name"] for a in first.get("/api/activities").json()] == ["Salida de prueba"]
    assert second.get("/api/activities").json() == []
    with factory() as db:
        activity = db.scalar(select(Activity).where(Activity.user_id == first_id))
        assert activity.source_provider == "garmin"
        assert activity.external_activity_id == "123"
        assert db.scalar(select(GarminConnection).where(GarminConnection.user_id == second_id)) is None
    assert first.delete("/api/integrations/garmin").status_code == 204
    assert first.get("/api/integrations/garmin/status").json()["connected"] is False
    assert len(first.get("/api/activities").json()) == 1


def test_garmin_mfa_is_bound_to_the_authenticated_user(clients):
    first, second, _ = clients
    register(first, "Ana", "ana-mfa@example.test")
    register(second, "Beto", "beto-mfa@example.test")
    response = first.post(
        "/api/integrations/garmin/connect",
        json={"email": "mfa@example.test", "password": "temporary-secret"},
    )
    assert response.json() == {"status": "needs_mfa"}
    assert second.post("/api/integrations/garmin/mfa", json={"code": "123456"}).status_code == 503
    assert first.post("/api/integrations/garmin/mfa", json={"code": "123456"}).json() == {"status": "connected"}


def test_garmin_failure_keeps_manual_import_available(clients, monkeypatch):
    first, _, _ = clients
    register(first, "Ana", "ana-fallback@example.test")
    first.post(
        "/api/integrations/garmin/connect",
        json={"email": "ana@example.test", "password": "garmin-secret"},
    )

    def fail_download(self, activity_id, dl_fmt=None):
        raise RuntimeError("Garmin changed its endpoint")

    monkeypatch.setattr(FakeGarmin, "download_activity", fail_download)
    assert first.post("/api/integrations/garmin/sync").json() == {
        "imported": 0, "skipped": 0, "failed": 1
    }
    gpx = (
        b"<gpx><trk><name>Manual</name><trkseg>"
        b"<trkpt lat='40' lon='-3'><time>2026-09-14T08:00:00Z</time></trkpt>"
        b"</trkseg></trk></gpx>"
    )
    response = first.post(
        "/api/activities/import", files={"file": ("manual.gpx", gpx, "application/gpx+xml")}
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Manual"

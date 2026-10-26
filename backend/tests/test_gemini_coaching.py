"""Authenticated preview and strict binding of remote text to Python's plan."""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from test_weekly_planning import create_active_goal, create_profile, register_user

from app.coaching.gemini import InvalidCoachProposal, propose_plan
from app.config import get_settings
from app.database import Base
from app.main import app


@pytest.fixture
def clients(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.database.SessionLocal", factory)
    return TestClient(app), TestClient(app)


def test_preview_uses_authenticated_athlete_and_does_not_save(clients, monkeypatch):
    first, second = clients
    register_user(first, "First", "preview-first@example.com")
    register_user(second, "Second", "preview-second@example.com")
    create_profile(first, availability={"mon": 60}, preferences={"has_power_meter": False})
    goal = create_active_goal(first)
    seen = {}

    def fake_propose_plan(**kwargs):
        seen.update(kwargs)
        return {"sessions": kwargs["scaffold"], "explanation": "Prueba", "model": "test"}

    monkeypatch.setattr("app.main.propose_plan", fake_propose_plan)
    response = first.post("/api/coaching/plan-preview", json={"reference_date": "2026-09-09"})
    assert response.status_code == 200
    assert response.json()["preview_only"] is True
    assert response.json()["active_goal_id"] == goal["id"]
    assert seen["context"]["athlete_profile"]["experience_level"] == "intermediate"
    assert len(seen["scaffold"]) == 1
    assert first.get("/api/plans/history").json() == []
    assert (
        second.post("/api/coaching/plan-preview", json={"reference_date": "2026-09-09"}).status_code
        == 404
    )


def test_preview_without_key_is_unavailable(clients, monkeypatch):
    first, _ = clients
    register_user(first, "First", "preview-no-key@example.com")
    create_profile(first)
    create_active_goal(first)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        response = first.post("/api/coaching/plan-preview", json={"reference_date": "2026-09-09"})
        assert response.status_code == 503
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("remote_date,valid", [("2026-09-15", False), ("2026-09-14", True)])
def test_remote_proposal_cannot_change_python_dates(monkeypatch, remote_date, valid):
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, *_):
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "explanation": "Plan",
                                                "sessions": [
                                                    {
                                                        "date": remote_date,
                                                        "title": "Rodaje",
                                                        "description": "Suave",
                                                        "session_goal": "Base",
                                                        "rationale": "Adaptación",
                                                        "structure": [
                                                            "Calentar",
                                                            "Rodar",
                                                            "Enfriar",
                                                        ],
                                                        "adjustment_criterion": "Recortar si hay fatiga",
                                                    }
                                                ],
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, **_kwargs):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr("app.coaching.gemini.urlopen", fake_urlopen)

    def call():
        return propose_plan(
            api_key="test",
            model="gemini-2.5-flash-lite",
            context={"methodology": {}, "knowledge_version": "v1"},
            scaffold=[
                {
                    "date": date(2026, 9, 14),
                    "planned_duration": 60,
                    "intensity_metric": "rpe",
                    "target_zone": "RPE 4",
                    "training_type": "Ciclismo",
                }
            ],
        )

    if not valid:
        with pytest.raises(InvalidCoachProposal):
            call()
    else:
        proposal = call()
        assert proposal["sessions"][0]["planned_duration"] == 60
        assert proposal["sessions"][0]["intensity_metric"] == "rpe"
        assert proposal["sessions"][0]["target_zone"] == "RPE 4"
        sent = json.loads(requests[0].data)
        assert sent["generationConfig"]["responseJsonSchema"]["properties"]["sessions"]
        assert "minLength" not in json.dumps(sent["generationConfig"]["responseJsonSchema"])

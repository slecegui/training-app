"""Gemini proposal adapter. The authenticated backend owns context and validation."""

import json
from datetime import date
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError


class CoachUnavailable(Exception):
    pass


class InvalidCoachProposal(Exception):
    pass


class SessionProposal(BaseModel):
    date: date
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    session_goal: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=1000)
    structure: list[str] = Field(min_length=3, max_length=12)
    adjustment_criterion: str = Field(min_length=1, max_length=500)


class PlanProposal(BaseModel):
    sessions: list[SessionProposal]
    explanation: str = Field(min_length=1, max_length=2000)


INSTRUCTIONS_PATH = Path(__file__).with_name("coach-v1.md")


def _google_schema(value: object) -> object:
    """Keep only the JSON Schema keywords accepted by Gemini's REST API."""
    supported = {
        "$defs",
        "$ref",
        "type",
        "format",
        "title",
        "description",
        "enum",
        "items",
        "minItems",
        "maxItems",
        "properties",
        "required",
    }
    if isinstance(value, dict):
        return {
            key: (
                {name: _google_schema(schema) for name, schema in item.items()}
                if key in {"$defs", "properties"}
                else _google_schema(item)
            )
            for key, item in value.items()
            if key in supported
        }
    if isinstance(value, list):
        return [_google_schema(item) for item in value]
    return value


def propose_plan(*, api_key: str, model: str, context: dict, scaffold: list[dict]) -> dict:
    """Request coaching text, then bind it to Python's immutable plan constraints."""
    if not api_key:
        raise CoachUnavailable("Gemini no está configurado en el servidor")
    instructions = INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    instruction_version = "coach-v1-" + sha256(instructions.encode()).hexdigest()[:12]
    fixed_sessions = [
        {
            "date": session["date"].isoformat(),
            "planned_duration": session["planned_duration"],
            "intensity_metric": session["intensity_metric"],
            "target_zone": session["target_zone"],
            "training_type": session["training_type"],
        }
        for session in scaffold
    ]
    payload = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "methodology": context["methodology"],
                                "athlete": {
                                    key: value
                                    for key, value in context.items()
                                    if key != "methodology"
                                },
                                "fixed_sessions": fixed_sessions,
                            },
                            ensure_ascii=False,
                            default=str,
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": _google_schema(PlanProposal.model_json_schema()),
            "temperature": 0.3,
        },
    }
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise CoachUnavailable("No se pudo obtener la propuesta de Gemini") from error
    try:
        raw = result["candidates"][0]["content"]["parts"][0]["text"]
        proposal = PlanProposal.model_validate_json(raw)
    except (KeyError, IndexError, TypeError, ValidationError, ValueError) as error:
        raise InvalidCoachProposal("Gemini devolvió una propuesta inválida") from error
    expected = {session["date"] for session in scaffold}
    actual = [session.date for session in proposal.sessions]
    if len(actual) != len(scaffold) or set(actual) != expected:
        raise InvalidCoachProposal("La propuesta no respeta los días fijados por Python")
    by_date = {session.date: session for session in proposal.sessions}
    sessions = []
    for fixed in scaffold:
        suggested = by_date[fixed["date"]]
        sessions.append(
            {
                **fixed,
                "title": suggested.title,
                "description": suggested.description,
                "session_goal": suggested.session_goal,
                "rationale": suggested.rationale,
                "structure": suggested.structure,
                "adjustment_criterion": suggested.adjustment_criterion,
            }
        )
    return {
        "sessions": sessions,
        "explanation": proposal.explanation,
        "model": model,
        "instruction_version": instruction_version,
        "knowledge_version": context["knowledge_version"],
        "usage": result.get("usageMetadata", {}),
    }

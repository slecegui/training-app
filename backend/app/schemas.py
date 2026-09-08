"""API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    sport: str
    started_at: datetime | None
    duration_seconds: int | None
    distance_meters: float | None
    elevation_gain_meters: float | None
    average_heart_rate: int | None
    average_power: int | None
    average_cadence: int | None
    calories: int | None
    original_filename: str | None
    source_format: str

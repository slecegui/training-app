"""Import a sanitized profile and activity summaries from a local Training export.

Expected files: profile.json and activities.json. This command never reads credentials,
tokens, original FIT/TCX/GPX files, or directories outside the supplied source folder.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Activity, AthleteProfile, User


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    args = parser.parse_args()
    profile_file = args.source / "profile.json"
    activities_file = args.source / "activities.json"
    if not profile_file.exists() and not activities_file.exists():
        raise SystemExit("Se esperaba profile.json o activities.json en --source")
    with SessionLocal() as db:
        if not db.get(User, args.user_id):
            raise SystemExit("El usuario destino no existe")
        if profile_file.exists():
            raw = json.loads(profile_file.read_text())
            profile = db.scalar(
                select(AthleteProfile).where(AthleteProfile.user_id == args.user_id)
            )
            values = {
                key: raw.get(key, default)
                for key, default in {
                    "sports": [],
                    "experience_level": None,
                    "power_zones": {},
                    "heart_rate_zones": {},
                    "availability": {},
                    "injuries_or_constraints": None,
                }.items()
            }
            if profile:
                for key, value in values.items():
                    setattr(profile, key, value)
            else:
                db.add(AthleteProfile(user_id=args.user_id, **values))
        if activities_file.exists():
            for raw in json.loads(activities_file.read_text()):
                db.add(
                    Activity(
                        user_id=args.user_id,
                        name=raw.get("name", "Actividad importada"),
                        sport=raw.get("sport", "Otros"),
                        started_at=datetime.fromisoformat(raw["started_at"])
                        if raw.get("started_at")
                        else None,
                        duration_seconds=raw.get("duration_seconds"),
                        distance_meters=raw.get("distance_meters"),
                        elevation_gain_meters=raw.get("elevation_gain_meters"),
                        average_heart_rate=raw.get("average_heart_rate"),
                        average_power=raw.get("average_power"),
                        average_cadence=raw.get("average_cadence"),
                        calories=raw.get("calories"),
                        source_format="legacy",
                    )
                )
        db.commit()


if __name__ == "__main__":
    main()

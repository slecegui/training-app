"""Extract common activity data from GPX, TCX and FIT files."""

from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import fitdecode


def number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def average(values: list[float]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def text(element: ET.Element | None, suffix: str) -> str | None:
    found = element.find(f".//{{*}}{suffix}") if element is not None else None
    return found.text if found is not None else None


def parse_xml(path: Path, extension: str) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    activity = root.find(".//{*}Activity") if extension == "tcx" else None
    points = root.findall(".//{*}Trackpoint" if extension == "tcx" else ".//{*}trkpt")
    name = text(activity, "Notes") or text(root, "name") or path.stem
    timestamps = [text(point, "Time" if extension == "tcx" else "time") for point in points]
    dates = [datetime.fromisoformat(item.replace("Z", "+00:00")) for item in timestamps if item]
    elevations = [number(text(point, "AltitudeMeters") or text(point, "ele")) for point in points]
    elevations = [value for value in elevations if value is not None]
    hearts = [number(text(point, "Value") or text(point, "hr")) for point in points]
    cadences = [number(text(point, "Cadence") or text(point, "cad")) for point in points]
    distance = number(text(activity, "DistanceMeters") or text(root, "distance"))
    gain = sum(max(0, elevations[i] - elevations[i - 1]) for i in range(1, len(elevations)))
    sport = (
        activity.get("Sport")
        if activity is not None
        else ("Carrera" if "run" in name.lower() else "Otros")
    )
    return {
        "name": name,
        "sport": (sport or "Otros").title(),
        "started_at": min(dates) if dates else None,
        "duration_seconds": round((max(dates) - min(dates)).total_seconds())
        if len(dates) > 1
        else None,
        "distance_meters": distance,
        "elevation_gain_meters": round(gain, 1) if elevations else None,
        "average_heart_rate": average([x for x in hearts if x is not None]),
        "average_cadence": average([x for x in cadences if x is not None]),
        "average_power": None,
        "calories": None,
    }


def parse_fit(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"name": path.stem, "sport": "Otros"}
    with fitdecode.FitReader(path) as reader:
        for frame in reader:
            if not isinstance(frame, fitdecode.FitDataMessage) or frame.name != "session":
                continue
            fields = {field.name: field.value for field in frame.fields}
            result.update(
                {
                    "sport": str(fields.get("sport", "Otros")).title(),
                    "started_at": fields.get("start_time"),
                    "duration_seconds": round(fields["total_elapsed_time"])
                    if fields.get("total_elapsed_time")
                    else None,
                    "distance_meters": number(fields.get("total_distance")),
                    "elevation_gain_meters": number(fields.get("total_ascent")),
                    "average_heart_rate": fields.get("avg_heart_rate"),
                    "average_power": fields.get("avg_power"),
                    "average_cadence": fields.get("avg_cadence"),
                    "calories": fields.get("total_calories"),
                }
            )
            break
    return result


def parse_activity_file(path: Path, extension: str) -> dict[str, Any]:
    if extension in {"gpx", "tcx"}:
        return parse_xml(path, extension)
    if extension == "fit":
        return parse_fit(path)
    raise ValueError("Formato no compatible")

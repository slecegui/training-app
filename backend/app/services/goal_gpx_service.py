"""Deterministic and safe GPX validation and route metadata extraction."""

from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_GPX_BYTES = 5 * 1024 * 1024


def parse_goal_gpx(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_GPX_BYTES:
        raise ValueError("El GPX está vacío o supera el límite de 5 MB")
    # ElementTree does not resolve external entities; reject declarations proactively.
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("El GPX no puede contener entidades XML")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ValueError("El archivo no contiene XML/GPX válido") from error
    if root.tag.rsplit("}", 1)[-1] != "gpx":
        raise ValueError("El XML debe tener un elemento raíz GPX")
    points: list[tuple[float, float, float | None]] = []
    for point in root.findall(".//{*}trkpt") + root.findall(".//{*}rtept"):
        try:
            lat, lon = float(point.attrib["lat"]), float(point.attrib["lon"])
        except (KeyError, ValueError) as error:
            raise ValueError("El GPX contiene una coordenada inválida") from error
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("El GPX contiene coordenadas fuera de rango")
        elevation = point.findtext("{*}ele")
        points.append((lat, lon, float(elevation) if elevation is not None else None))
    if not points:
        raise ValueError("El GPX no contiene puntos de ruta")
    def meters(a: tuple[float, float, float | None], b: tuple[float, float, float | None]) -> float:
        dlat, dlon = radians(b[0] - a[0]), radians(b[1] - a[1])
        h = sin(dlat / 2) ** 2 + cos(radians(a[0])) * cos(radians(b[0])) * sin(dlon / 2) ** 2
        return 6_371_000 * 2 * asin(sqrt(h))
    return {
        "route_distance_meters": round(sum(meters(a, b) for a, b in zip(points, points[1:])), 1),
        "route_elevation_gain_meters": round(sum(max(0, b[2] - a[2]) for a, b in zip(points, points[1:]) if a[2] is not None and b[2] is not None), 1),
        "route_start_latitude": points[0][0], "route_start_longitude": points[0][1],
        "route_end_latitude": points[-1][0], "route_end_longitude": points[-1][1],
        "route_bounds": {"min_lat": min(p[0] for p in points), "max_lat": max(p[0] for p in points), "min_lon": min(p[1] for p in points), "max_lon": max(p[1] for p in points)},
    }

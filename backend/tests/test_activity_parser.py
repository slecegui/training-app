from pathlib import Path

from app.services.activity_parser import parse_activity_file


def test_parses_gpx_metrics(tmp_path: Path) -> None:
    source = tmp_path / "run.gpx"
    source.write_text(
        "<gpx><trk><name>Morning run</name><trkseg>"
        "<trkpt><ele>10</ele><time>2026-09-01T08:00:00Z</time>"
        "<extensions><hr>140</hr></extensions></trkpt>"
        "<trkpt><ele>25</ele><time>2026-09-01T08:10:00Z</time>"
        "<extensions><hr>150</hr><cad>170</cad></extensions></trkpt>"
        "</trkseg></trk></gpx>"
    )
    result = parse_activity_file(source, "gpx")
    assert result["name"] == "Morning run"
    assert result["duration_seconds"] == 600
    assert result["elevation_gain_meters"] == 15
    assert result["average_heart_rate"] == 145

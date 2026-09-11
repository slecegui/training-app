import importlib.util
from datetime import datetime
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
)


def load_migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260911_0005_goal_routes.py"
    spec = importlib.util.spec_from_file_location("goal_routes_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_goal_route_migration_copies_legacy_single_route() -> None:
    engine = create_engine("sqlite://")
    metadata = MetaData()
    goals = Table(
        "goals",
        metadata,
        # Only the legacy columns read by this migration are needed.
        Column("id", Integer, primary_key=True),
        Column("route_original_filename", String(255)),
        Column("route_stored_filename", String(255)),
        Column("route_uploaded_at", DateTime(timezone=True)),
        Column("route_size_bytes", Integer),
        Column("route_distance_meters", Float),
        Column("route_elevation_gain_meters", Float),
        Column("route_start_latitude", Float),
        Column("route_start_longitude", Float),
        Column("route_end_latitude", Float),
        Column("route_end_longitude", Float),
        Column("route_bounds", JSON),
    )
    metadata.create_all(engine)
    legacy_name = "a" * 32 + ".gpx"

    with engine.begin() as connection:
        connection.execute(
            insert(goals).values(
                id=7,
                route_original_filename="single-stage.gpx",
                route_stored_filename=legacy_name,
                route_uploaded_at=datetime(2026, 9, 11),
                route_size_bytes=123,
                route_distance_meters=456.7,
                route_elevation_gain_meters=89.0,
                route_start_latitude=40.1,
                route_start_longitude=-3.1,
                route_end_latitude=40.2,
                route_end_longitude=-3.2,
                route_bounds={"min_lat": 40.1},
            )
        )
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            load_migration().upgrade()

        migrated = (
            connection.execute(select(Table("goal_routes", MetaData(), autoload_with=connection)))
            .mappings()
            .one()
        )
        assert migrated["goal_id"] == 7
        assert migrated["original_filename"] == "single-stage.gpx"
        assert migrated["stored_filename"] == legacy_name
        assert migrated["distance_meters"] == 456.7
        assert migrated["display_order"] == 0

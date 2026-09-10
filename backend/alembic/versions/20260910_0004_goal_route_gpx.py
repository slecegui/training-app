"""add private GPX route metadata to goals

Revision ID: 20260910_0004
Revises: 87c7668bbc0c
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0004"
down_revision = "87c7668bbc0c"
branch_labels = None
depends_on = None

def upgrade() -> None:
    for name, column in (("route_original_filename", sa.String(255)), ("route_stored_filename", sa.String(255)), ("route_size_bytes", sa.Integer()), ("route_uploaded_at", sa.DateTime(timezone=True)), ("route_distance_meters", sa.Float()), ("route_elevation_gain_meters", sa.Float()), ("route_start_latitude", sa.Float()), ("route_start_longitude", sa.Float()), ("route_end_latitude", sa.Float()), ("route_end_longitude", sa.Float()), ("route_bounds", sa.JSON())):
        op.add_column("goals", sa.Column(name, column, nullable=True))

def downgrade() -> None:
    for name in ("route_bounds", "route_end_longitude", "route_end_latitude", "route_start_longitude", "route_start_latitude", "route_elevation_gain_meters", "route_distance_meters", "route_uploaded_at", "route_size_bytes", "route_stored_filename", "route_original_filename"):
        op.drop_column("goals", name)

"""add one-to-many GPX routes to goals

Revision ID: 20260911_0005
Revises: 20260910_0004
"""

from alembic import op
import sqlalchemy as sa


revision = "20260911_0005"
down_revision = "20260910_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goal_routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False, unique=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage_label", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("elevation_gain_meters", sa.Float(), nullable=True),
        sa.Column("start_latitude", sa.Float(), nullable=True),
        sa.Column("start_longitude", sa.Float(), nullable=True),
        sa.Column("end_latitude", sa.Float(), nullable=True),
        sa.Column("end_longitude", sa.Float(), nullable=True),
        sa.Column("bounds", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_goal_routes_goal_id", "goal_routes", ["goal_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO goal_routes (
                goal_id, original_filename, stored_filename, uploaded_at,
                display_order, stage_label, size_bytes, distance_meters,
                elevation_gain_meters, start_latitude, start_longitude,
                end_latitude, end_longitude, bounds
            )
            SELECT
                id, COALESCE(route_original_filename, route_stored_filename), route_stored_filename, COALESCE(route_uploaded_at, CURRENT_TIMESTAMP),
                0, NULL, COALESCE(route_size_bytes, 0), route_distance_meters,
                route_elevation_gain_meters, route_start_latitude, route_start_longitude,
                route_end_latitude, route_end_longitude, route_bounds
            FROM goals
            WHERE route_stored_filename IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_goal_routes_goal_id", table_name="goal_routes")
    op.drop_table("goal_routes")

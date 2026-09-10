"""Add local authentication and complete profile and goal fields.

Revision ID: 20260909_0003
Revises: 20260909_0002
"""

import sqlalchemy as sa

from alembic import op

revision = "20260909_0003"
down_revision = "20260909_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column(
        "athlete_profiles", sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}")
    )
    op.add_column(
        "goals", sa.Column("goal_type", sa.String(80), nullable=False, server_default="event")
    )
    op.add_column("goals", sa.Column("target_distance_meters", sa.Float(), nullable=True))
    op.add_column("goals", sa.Column("target_elevation_meters", sa.Float(), nullable=True))
    op.add_column(
        "goals",
        sa.Column("success_metric", sa.String(255), nullable=False, server_default="Completar"),
    )
    op.create_index(
        "uq_goals_one_active_per_user",
        "goals",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_goals_one_active_per_user", table_name="goals")
    op.drop_column("goals", "success_metric")
    op.drop_column("goals", "target_elevation_meters")
    op.drop_column("goals", "target_distance_meters")
    op.drop_column("goals", "goal_type")
    op.drop_column("athlete_profiles", "preferences")
    op.drop_column("users", "password_hash")

"""initial users and activities
Revision ID: 20260909_0001
Revises:
"""

import sqlalchemy as sa

from alembic import op

revision = "20260909_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sport", sa.String(80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("distance_meters", sa.Float()),
        sa.Column("elevation_gain_meters", sa.Float()),
        sa.Column("average_heart_rate", sa.Integer()),
        sa.Column("average_power", sa.Integer()),
        sa.Column("average_cadence", sa.Integer()),
        sa.Column("calories", sa.Integer()),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("stored_filename", sa.String(255)),
        sa.Column("source_format", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_activities_user_id", "activities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_activities_user_id", table_name="activities")
    op.drop_table("activities")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

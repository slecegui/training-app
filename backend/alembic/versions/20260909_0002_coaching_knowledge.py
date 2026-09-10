"""Add private coaching knowledge entities.

Revision ID: 20260909_0002
Revises: 20260909_0001
"""

import sqlalchemy as sa

from alembic import op

revision = "20260909_0002"
down_revision = "20260909_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sports", sa.JSON(), nullable=False),
        sa.Column("experience_level", sa.String(50)),
        sa.Column("power_zones", sa.JSON(), nullable=False),
        sa.Column("heart_rate_zones", sa.JSON(), nullable=False),
        sa.Column("availability", sa.JSON(), nullable=False),
        sa.Column("injuries_or_constraints", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_athlete_profiles_user_id", "athlete_profiles", ["user_id"], unique=True)
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("target_date", sa.Date()),
        sa.Column("sport", sa.String(80)),
        sa.Column("priority", sa.String(30), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])
    op.create_index("ix_goals_is_active", "goals", ["is_active"])
    op.create_table(
        "wellness_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("sleep_hours", sa.Float()),
        sa.Column("fatigue", sa.Integer()),
        sa.Column("soreness", sa.Integer()),
        sa.Column("stress", sa.Integer()),
        sa.Column("mood", sa.Integer()),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_wellness_entries_user_id", "wellness_entries", ["user_id"])
    op.create_index("ix_wellness_entries_entry_date", "wellness_entries", ["entry_date"])
    op.create_table(
        "coach_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("input_context", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_coach_decisions_user_id", "coach_decisions", ["user_id"])
    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_versions_version", "knowledge_versions", ["version"], unique=True)


def downgrade() -> None:
    for index, table in [
        ("ix_knowledge_versions_version", "knowledge_versions"),
        ("ix_coach_decisions_user_id", "coach_decisions"),
        ("ix_wellness_entries_entry_date", "wellness_entries"),
        ("ix_wellness_entries_user_id", "wellness_entries"),
        ("ix_goals_is_active", "goals"),
        ("ix_goals_user_id", "goals"),
        ("ix_athlete_profiles_user_id", "athlete_profiles"),
    ]:
        op.drop_index(index, table_name=table)
    for table in [
        "knowledge_versions",
        "coach_decisions",
        "wellness_entries",
        "goals",
        "athlete_profiles",
    ]:
        op.drop_table(table)

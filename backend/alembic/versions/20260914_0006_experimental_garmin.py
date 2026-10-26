"""Experimental per-user Garmin activity connection.

Revision ID: 20260914_0006
Revises: 20260911_0005
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_0006"
down_revision = "20260911_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("activities") as batch:
        batch.add_column(sa.Column("source_provider", sa.String(30), nullable=True))
        batch.add_column(sa.Column("external_activity_id", sa.String(100), nullable=True))
        batch.create_unique_constraint(
            "uq_activity_external_source",
            ["user_id", "source_provider", "external_activity_id"],
        )
    op.create_table(
        "garmin_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encrypted_tokens", sa.Text(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(255), nullable=True),
    )
    op.create_index("ix_garmin_connections_user_id", "garmin_connections", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_garmin_connections_user_id", table_name="garmin_connections")
    op.drop_table("garmin_connections")
    with op.batch_alter_table("activities") as batch:
        batch.drop_constraint("uq_activity_external_source", type_="unique")
        batch.drop_column("external_activity_id")
        batch.drop_column("source_provider")

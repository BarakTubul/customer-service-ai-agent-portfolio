"""add demo card fields to users

Revision ID: 20260407_0006
Revises: 20260406_0005
Create Date: 2026-04-07 00:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260407_0006"
down_revision = "20260406_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("demo_card_number", sa.String(length=19), nullable=True))
    op.add_column("users", sa.Column("demo_card_assigned_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "demo_card_assigned_at")
    op.drop_column("users", "demo_card_number")

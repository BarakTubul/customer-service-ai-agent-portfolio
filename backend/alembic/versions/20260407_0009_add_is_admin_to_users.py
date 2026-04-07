"""add is_admin to users

Revision ID: 20260407_0009
Revises: 20260407_0008
Create Date: 2026-04-07 02:25:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260407_0009"
down_revision = "20260407_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("users", "is_admin", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_admin")

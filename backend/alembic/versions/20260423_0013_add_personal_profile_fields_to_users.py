"""add personal profile fields to users

Revision ID: 20260423_0013
Revises: 20260421_0012
Create Date: 2026-04-23 14:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260423_0013"
down_revision = "20260421_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("address", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "address")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "full_name")

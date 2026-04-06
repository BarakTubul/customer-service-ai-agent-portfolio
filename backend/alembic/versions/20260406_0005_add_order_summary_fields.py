"""add order summary fields

Revision ID: 20260406_0005
Revises: 20260331_0004
Create Date: 2026-04-06 00:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260406_0005"
down_revision = "20260331_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("ordered_items_summary", sa.String(length=512), nullable=True))
    op.add_column("orders", sa.Column("total_cents", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "total_cents")
    op.drop_column("orders", "ordered_items_summary")

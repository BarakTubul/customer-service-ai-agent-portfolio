"""add user balance and order payment state

Revision ID: 20260421_0012
Revises: 20260419_0011
Create Date: 2026-04-21 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260421_0012"
down_revision = "20260419_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("balance_cents", sa.Integer(), nullable=False, server_default="100000"),
    )
    op.add_column(
        "orders",
        sa.Column("payment_state", sa.String(length=32), nullable=False, server_default="captured"),
    )


def downgrade() -> None:
    op.drop_column("orders", "payment_state")
    op.drop_column("users", "balance_cents")

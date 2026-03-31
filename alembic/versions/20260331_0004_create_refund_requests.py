"""create refund requests table

Revision ID: 20260331_0004
Revises: 20260329_0003
Create Date: 2026-03-31 00:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260331_0004"
down_revision = "20260329_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refund_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("refund_request_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("simulation_scenario_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_refund_requests_id", "refund_requests", ["id"])
    op.create_index("ix_refund_requests_refund_request_id", "refund_requests", ["refund_request_id"], unique=True)
    op.create_index("ix_refund_requests_idempotency_key", "refund_requests", ["idempotency_key"], unique=True)
    op.create_index("ix_refund_requests_user_id", "refund_requests", ["user_id"])
    op.create_index("ix_refund_requests_order_id", "refund_requests", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_refund_requests_order_id", table_name="refund_requests")
    op.drop_index("ix_refund_requests_user_id", table_name="refund_requests")
    op.drop_index("ix_refund_requests_idempotency_key", table_name="refund_requests")
    op.drop_index("ix_refund_requests_refund_request_id", table_name="refund_requests")
    op.drop_index("ix_refund_requests_id", table_name="refund_requests")
    op.drop_table("refund_requests")

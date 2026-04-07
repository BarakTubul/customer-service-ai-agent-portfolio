"""add manual review escalation fields to refund requests

Revision ID: 20260407_0008
Revises: 20260407_0007
Create Date: 2026-04-07 01:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260407_0008"
down_revision = "20260407_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refund_requests", sa.Column("escalation_status", sa.String(length=32), nullable=True))
    op.add_column("refund_requests", sa.Column("escalation_queue_name", sa.String(length=64), nullable=True))
    op.add_column("refund_requests", sa.Column("escalation_sla_deadline_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refund_requests", sa.Column("escalation_payload_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("refund_requests", "escalation_payload_json")
    op.drop_column("refund_requests", "escalation_sla_deadline_at")
    op.drop_column("refund_requests", "escalation_queue_name")
    op.drop_column("refund_requests", "escalation_status")

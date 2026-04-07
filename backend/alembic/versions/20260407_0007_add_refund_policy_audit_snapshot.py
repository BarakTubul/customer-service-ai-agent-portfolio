"""add policy audit snapshot fields to refund requests

Revision ID: 20260407_0007
Revises: 20260407_0006
Create Date: 2026-04-07 01:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260407_0007"
down_revision = "20260407_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refund_requests", sa.Column("policy_version", sa.String(length=32), nullable=True))
    op.add_column("refund_requests", sa.Column("policy_reference", sa.String(length=128), nullable=True))
    op.add_column("refund_requests", sa.Column("resolution_action", sa.String(length=32), nullable=True))
    op.add_column("refund_requests", sa.Column("decision_reason_codes", sa.Text(), nullable=True))
    op.add_column("refund_requests", sa.Column("refundable_amount_currency", sa.String(length=8), nullable=True))
    op.add_column("refund_requests", sa.Column("refundable_amount_value", sa.Float(), nullable=True))
    op.add_column("refund_requests", sa.Column("explanation_template_key", sa.String(length=128), nullable=True))
    op.add_column("refund_requests", sa.Column("explanation_params_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("refund_requests", "explanation_params_json")
    op.drop_column("refund_requests", "explanation_template_key")
    op.drop_column("refund_requests", "refundable_amount_value")
    op.drop_column("refund_requests", "refundable_amount_currency")
    op.drop_column("refund_requests", "decision_reason_codes")
    op.drop_column("refund_requests", "resolution_action")
    op.drop_column("refund_requests", "policy_reference")
    op.drop_column("refund_requests", "policy_version")

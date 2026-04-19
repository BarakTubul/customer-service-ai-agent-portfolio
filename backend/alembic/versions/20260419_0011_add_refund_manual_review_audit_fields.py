"""add refund manual review audit fields

Revision ID: 20260419_0011
Revises: 20260408_0010
Create Date: 2026-04-19 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260419_0011"
down_revision = "20260408_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refund_requests", sa.Column("claimed_by_admin_user_id", sa.Integer(), nullable=True))
    op.add_column("refund_requests", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refund_requests", sa.Column("decided_by_admin_user_id", sa.Integer(), nullable=True))
    op.add_column("refund_requests", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refund_requests", sa.Column("reviewer_note", sa.Text(), nullable=True))

    op.create_foreign_key(
        "fk_refund_requests_claimed_by_admin_user_id_users",
        "refund_requests",
        "users",
        ["claimed_by_admin_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_refund_requests_decided_by_admin_user_id_users",
        "refund_requests",
        "users",
        ["decided_by_admin_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_refund_requests_decided_by_admin_user_id_users", "refund_requests", type_="foreignkey")
    op.drop_constraint("fk_refund_requests_claimed_by_admin_user_id_users", "refund_requests", type_="foreignkey")

    op.drop_column("refund_requests", "reviewer_note")
    op.drop_column("refund_requests", "decided_at")
    op.drop_column("refund_requests", "decided_by_admin_user_id")
    op.drop_column("refund_requests", "claimed_at")
    op.drop_column("refund_requests", "claimed_by_admin_user_id")

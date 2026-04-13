"""create support conversations and messages

Revision ID: 20260408_0010
Revises: 20260407_0009
Create Date: 2026-04-08 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260408_0010"
down_revision = "20260407_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("customer_user_id", sa.Integer(), nullable=False),
        sa.Column("source_session_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("assigned_admin_user_id", sa.Integer(), nullable=True),
        sa.Column("escalation_reason_code", sa.String(length=64), nullable=True),
        sa.Column("escalation_reference_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_admin_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_support_conversations_id"), "support_conversations", ["id"], unique=False)
    op.create_index(
        op.f("ix_support_conversations_conversation_id"),
        "support_conversations",
        ["conversation_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_support_conversations_customer_user_id"),
        "support_conversations",
        ["customer_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_conversations_assigned_admin_user_id"),
        "support_conversations",
        ["assigned_admin_user_id"],
        unique=False,
    )

    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=False),
        sa.Column("sender_role", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["support_conversations.conversation_id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_support_messages_id"), "support_messages", ["id"], unique=False)
    op.create_index(op.f("ix_support_messages_message_id"), "support_messages", ["message_id"], unique=True)
    op.create_index(
        op.f("ix_support_messages_conversation_id"),
        "support_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_messages_sender_user_id"),
        "support_messages",
        ["sender_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_support_messages_sender_user_id"), table_name="support_messages")
    op.drop_index(op.f("ix_support_messages_conversation_id"), table_name="support_messages")
    op.drop_index(op.f("ix_support_messages_message_id"), table_name="support_messages")
    op.drop_index(op.f("ix_support_messages_id"), table_name="support_messages")
    op.drop_table("support_messages")

    op.drop_index(op.f("ix_support_conversations_assigned_admin_user_id"), table_name="support_conversations")
    op.drop_index(op.f("ix_support_conversations_customer_user_id"), table_name="support_conversations")
    op.drop_index(op.f("ix_support_conversations_conversation_id"), table_name="support_conversations")
    op.drop_index(op.f("ix_support_conversations_id"), table_name="support_conversations")
    op.drop_table("support_conversations")

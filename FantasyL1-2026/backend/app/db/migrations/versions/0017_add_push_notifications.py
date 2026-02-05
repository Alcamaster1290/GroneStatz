"""add push notifications tables

Revision ID: 0017_add_push_notifications
Revises: 0016_add_favorite_team_id
Create Date: 2026-02-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_add_push_notifications"
down_revision = "0016_add_favorite_team_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_device_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("device_id", sa.String(length=191), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column(
            "app_channel",
            sa.String(length=30),
            nullable=False,
            server_default="mobile",
        ),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("user_id", "device_id", name="uq_push_device_tokens_user_device"),
    )
    op.create_index(
        "ix_push_device_tokens_user_id",
        "push_device_tokens",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "round_push_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=False),
        sa.Column(
            "device_token_id",
            sa.Integer(),
            sa.ForeignKey("push_device_tokens.id"),
            nullable=False,
        ),
        sa.Column(
            "notification_type",
            sa.String(length=40),
            nullable=False,
            server_default="round_deadline",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "round_id",
            "device_token_id",
            "notification_type",
            name="uq_round_push_notifications_dedupe",
        ),
    )
    op.create_index(
        "ix_round_push_notifications_round_id",
        "round_push_notifications",
        ["round_id"],
        unique=False,
    )
    op.create_index(
        "ix_round_push_notifications_device_token_id",
        "round_push_notifications",
        ["device_token_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_round_push_notifications_device_token_id",
        table_name="round_push_notifications",
    )
    op.drop_index(
        "ix_round_push_notifications_round_id",
        table_name="round_push_notifications",
    )
    op.drop_table("round_push_notifications")

    op.drop_index("ix_push_device_tokens_user_id", table_name="push_device_tokens")
    op.drop_table("push_device_tokens")

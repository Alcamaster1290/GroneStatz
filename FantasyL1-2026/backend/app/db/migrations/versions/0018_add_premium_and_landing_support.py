"""add premium tables and app config

Revision ID: 0018_add_premium_and_landing_support
Revises: 0017_add_push_notifications
Create Date: 2026-02-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0018_add_premium_and_landing_support"
down_revision = "0017_add_push_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("season_id", sa.Integer(), sa.ForeignKey("seasons.id"), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="active"),
        sa.Column("plan_code", sa.String(length=24), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=True),
        sa.Column("end_round_id", sa.Integer(), sa.ForeignKey("rounds.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("status IN ('active','expired','canceled')", name="ck_subscriptions_status"),
        sa.CheckConstraint(
            "plan_code IN ('FREE','PREMIUM_2R','PREMIUM_4R','PREMIUM_APERTURA')",
            name="ck_subscriptions_plan_code",
        ),
    )
    op.create_index(
        "idx_subscriptions_user_status",
        "subscriptions",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_subscriptions_ends_at",
        "subscriptions",
        ["ends_at"],
        unique=False,
    )
    op.create_index(
        "uniq_active_subscription_per_user",
        "subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id"), nullable=True),
        sa.Column("provider", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(8, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="PEN"),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("provider_ref", sa.String(length=120), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("provider IN ('yape','stripe','manual')", name="ck_payment_events_provider"),
        sa.CheckConstraint(
            "status IN ('pending','paid','failed','refunded')",
            name="ck_payment_events_status",
        ),
    )
    op.execute(
        """
        CREATE INDEX idx_payment_events_user_created
        ON payment_events (user_id, created_at DESC)
        """
    )
    op.create_index(
        "idx_payment_events_provider_ref",
        "payment_events",
        ["provider", "provider_ref"],
        unique=False,
    )

    op.create_table(
        "app_config",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.String(length=255), nullable=False),
    )
    op.execute(
        """
        INSERT INTO app_config (key, value) VALUES
            ('CURRENT_SEASON_YEAR', '2026'),
            ('APERTURA_PREMIUM_LAST_SELL_ROUND', '12'),
            ('APERTURA_TOTAL_ROUNDS', '18')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("app_config")

    op.drop_index("idx_payment_events_provider_ref", table_name="payment_events")
    op.execute("DROP INDEX IF EXISTS idx_payment_events_user_created")
    op.drop_table("payment_events")

    op.drop_index("uniq_active_subscription_per_user", table_name="subscriptions")
    op.drop_index("idx_subscriptions_ends_at", table_name="subscriptions")
    op.drop_index("idx_subscriptions_user_status", table_name="subscriptions")
    op.drop_table("subscriptions")

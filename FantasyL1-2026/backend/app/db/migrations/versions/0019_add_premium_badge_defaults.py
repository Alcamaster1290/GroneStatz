"""add premium badge defaults to app_config

Revision ID: 0019_add_premium_badge_defaults
Revises: 0018_add_premium_and_landing_support
Create Date: 2026-02-20 00:30:00.000000
"""

from alembic import op


revision = "0019_add_premium_badge_defaults"
down_revision = "0018_add_premium_and_landing_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO app_config (key, value) VALUES
            ('PREMIUM_BADGE_ENABLED', 'true'),
            ('PREMIUM_BADGE_TEXT', 'P'),
            ('PREMIUM_BADGE_COLOR', '#7C3AED'),
            ('PREMIUM_BADGE_SHAPE', 'circle')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM app_config
        WHERE key IN (
            'PREMIUM_BADGE_ENABLED',
            'PREMIUM_BADGE_TEXT',
            'PREMIUM_BADGE_COLOR',
            'PREMIUM_BADGE_SHAPE'
        )
        """
    )


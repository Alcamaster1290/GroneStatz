"""drop unique transfer constraint to allow multiple transfers per round

Revision ID: 0014_drop_transfer_unique_add_transfer_fees
Revises: 0013_add_password_reset_tokens
Create Date: 2026-01-28 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0014_drop_transfer_unique_add_transfer_fees"
down_revision = "0013_add_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE fantasy_transfers DROP CONSTRAINT IF EXISTS fantasy_transfers_fantasy_team_id_round_id_key"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE fantasy_transfers ADD CONSTRAINT fantasy_transfers_fantasy_team_id_round_id_key UNIQUE (fantasy_team_id, round_id)"
    )

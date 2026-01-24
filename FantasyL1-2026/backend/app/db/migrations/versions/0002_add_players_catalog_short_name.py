"""add short_name to players_catalog

Revision ID: 0002_short_name
Revises: 0001_init
Create Date: 2026-01-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_short_name"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("players_catalog")]
    if "short_name" not in columns:
        op.add_column("players_catalog", sa.Column("short_name", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("players_catalog", "short_name")

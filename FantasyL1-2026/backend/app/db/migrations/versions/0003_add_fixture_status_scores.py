"""add fixture status and scores

Revision ID: 0003_fixture_status_scores
Revises: 0002_short_name
Create Date: 2026-01-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_fixture_status_scores"
down_revision = "0002_short_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {col["name"] for col in inspector.get_columns("fixtures")}

    if "status" not in columns:
        op.add_column(
            "fixtures",
            sa.Column("status", sa.String(length=20), nullable=False, server_default="Programado"),
        )
        op.alter_column("fixtures", "status", server_default=None)

    if "home_score" not in columns:
        op.add_column("fixtures", sa.Column("home_score", sa.Integer(), nullable=True))

    if "away_score" not in columns:
        op.add_column("fixtures", sa.Column("away_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("fixtures", "away_score")
    op.drop_column("fixtures", "home_score")
    op.drop_column("fixtures", "status")

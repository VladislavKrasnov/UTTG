"""drop health rows of providers that no longer exist

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM provider_health WHERE id IN ('jpl-horizons', 'esa')")


def downgrade() -> None:
    return None

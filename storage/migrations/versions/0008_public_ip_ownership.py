"""remove API-key persistence and use IP-scoped webhook ownership

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webhooks", sa.Column("owner_ip_fingerprint", sa.String(length=64)))
    op.create_index("ix_webhooks_owner_ip_fingerprint", "webhooks", ["owner_ip_fingerprint"])
    op.drop_constraint("fk_webhooks_owner_api_key", "webhooks", type_="foreignkey")
    op.drop_index("ix_webhooks_owner_api_key_id", table_name="webhooks")
    op.drop_column("webhooks", "owner_api_key_id")
    op.drop_table("api_keys")
    op.drop_table("request_metrics")


def downgrade() -> None:
    raise RuntimeError("The public-access migration intentionally has no downgrade")

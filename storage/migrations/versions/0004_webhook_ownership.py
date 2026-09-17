import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webhooks", sa.Column("secret_ciphertext", sa.Text(), nullable=True))
    op.add_column("webhooks", sa.Column("owner_api_key_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_webhooks_owner_api_key",
        "webhooks",
        "api_keys",
        ["owner_api_key_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_webhooks_owner_api_key_id", "webhooks", ["owner_api_key_id"])


def downgrade() -> None:
    op.drop_index("ix_webhooks_owner_api_key_id", table_name="webhooks")
    op.drop_constraint("fk_webhooks_owner_api_key", "webhooks", type_="foreignkey")
    op.drop_column("webhooks", "owner_api_key_id")
    op.drop_column("webhooks", "secret_ciphertext")

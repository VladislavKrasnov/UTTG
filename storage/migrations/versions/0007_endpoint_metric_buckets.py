import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "endpoint_metric_buckets",
        sa.Column("bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("request_count", sa.BigInteger(), nullable=False),
        sa.Column("server_error_count", sa.BigInteger(), nullable=False),
        sa.Column("duration_sum_ms", sa.Float(), nullable=False),
        sa.Column("duration_max_ms", sa.Float(), nullable=False),
        sa.Column("response_bytes", sa.BigInteger(), nullable=False),
        sa.Column("cache_hit_count", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("bucket", "route", "method"),
    )
    op.create_index(
        "ix_endpoint_metric_buckets_route_bucket",
        "endpoint_metric_buckets",
        ["route", "bucket"],
    )
    op.execute(
        "SELECT create_hypertable('endpoint_metric_buckets', 'bucket', if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT add_retention_policy("
        "'endpoint_metric_buckets', INTERVAL '90 days', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("endpoint_metric_buckets")

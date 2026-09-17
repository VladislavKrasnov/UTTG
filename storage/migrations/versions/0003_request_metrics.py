import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "request_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("response_bytes", sa.BigInteger(), nullable=False),
        sa.Column("api_key_id", sa.String(), nullable=True),
        sa.Column("ip_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("cache_state", sa.String(length=16), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )
    op.create_index("ix_request_metrics_timestamp", "request_metrics", ["timestamp"])
    op.create_index("ix_request_metrics_route_timestamp", "request_metrics", ["route", "timestamp"])
    op.create_index(
        "ix_request_metrics_api_key_timestamp", "request_metrics", ["api_key_id", "timestamp"]
    )
    op.execute("SELECT create_hypertable('request_metrics', 'timestamp', if_not_exists => TRUE)")
    op.execute(
        "SELECT add_retention_policy('request_metrics', INTERVAL '30 days', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("request_metrics")

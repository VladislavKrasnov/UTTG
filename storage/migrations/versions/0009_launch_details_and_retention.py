"""store launch operator details and bound time-series growth

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_LAUNCH_TEXT_COLUMNS = (
    "operator",
    "vehicle",
    "pad",
    "location",
    "mission_description",
    "weather_summary",
    "info_url",
)
_RETENTION = (
    ("orbital_elements", "45 days"),
    ("space_weather_indices", "120 days"),
    ("solar_wind", "120 days"),
    ("endpoint_metric_buckets", "30 days"),
)


def upgrade() -> None:
    for column in _LAUNCH_TEXT_COLUMNS:
        op.add_column("launches", sa.Column(column, sa.String()))
    op.add_column("launches", sa.Column("latitude", sa.Float()))
    op.add_column("launches", sa.Column("longitude", sa.Float()))
    op.create_index(
        "ix_orbital_elements_norad_epoch_desc",
        "orbital_elements",
        ["norad_id", sa.text("epoch DESC")],
    )
    for table, interval in _RETENTION:
        op.execute(
            f"SELECT add_retention_policy('{table}', INTERVAL '{interval}', if_not_exists => TRUE)"
        )


def downgrade() -> None:
    for table, _interval in _RETENTION:
        op.execute(f"SELECT remove_retention_policy('{table}', if_exists => TRUE)")
    op.drop_index("ix_orbital_elements_norad_epoch_desc", table_name="orbital_elements")
    op.drop_column("launches", "longitude")
    op.drop_column("launches", "latitude")
    for column in reversed(_LAUNCH_TEXT_COLUMNS):
        op.drop_column("launches", column)

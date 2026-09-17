"""complete

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_health",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("hashed_key", sa.String(), nullable=False),
        sa.Column("scopes", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_hashed_key", "api_keys", ["hashed_key"], unique=True)

    op.create_table(
        "launches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_launches_window_start", "launches", ["window_start"])

    op.create_table(
        "conjunction_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("norad_id_1", sa.Integer(), nullable=False),
        sa.Column("norad_id_2", sa.Integer(), nullable=False),
        sa.Column("tca", sa.DateTime(timezone=True), nullable=False),
        sa.Column("miss_distance", sa.Float(), nullable=False),
        sa.Column("probability", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["norad_id_1"], ["satellites.norad_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conjunction_events_norad_id_1", "conjunction_events", ["norad_id_1"])
    op.create_index("ix_conjunction_events_tca", "conjunction_events", ["tca"])

    op.create_table(
        "satellite_decays",
        sa.Column("norad_id", sa.Integer(), nullable=False),
        sa.Column("decay_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("norad_id"),
        sa.ForeignKeyConstraint(["norad_id"], ["satellites.norad_id"], ondelete="CASCADE"),
    )

    op.create_table(
        "near_earth_objects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("absolute_magnitude_h", sa.Float(), nullable=True),
        sa.Column("estimated_diameter_min_km", sa.Float(), nullable=True),
        sa.Column("estimated_diameter_max_km", sa.Float(), nullable=True),
        sa.Column("is_potentially_hazardous", sa.Boolean(), nullable=False),
        sa.Column("is_sentry_object", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "close_approaches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("neo_id", sa.String(), nullable=False),
        sa.Column("close_approach_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("relative_velocity_kms", sa.Float(), nullable=False),
        sa.Column("miss_distance_au", sa.Float(), nullable=False),
        sa.Column("orbiting_body", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["neo_id"], ["near_earth_objects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_close_approaches_neo_id", "close_approaches", ["neo_id"])
    op.create_index("ix_close_approaches_date", "close_approaches", ["close_approach_date"])

    op.create_table(
        "space_weather_indices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kp_index", sa.Float(), nullable=False),
        sa.Column("ap_index", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )
    op.create_index("ix_space_weather_indices_timestamp", "space_weather_indices", ["timestamp"])
    op.execute(
        "SELECT create_hypertable('space_weather_indices', 'timestamp', if_not_exists => TRUE)"
    )

    op.create_table(
        "solar_wind",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("speed_km_s", sa.Float(), nullable=False),
        sa.Column("density_cm3", sa.Float(), nullable=False),
        sa.Column("temperature_k", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )
    op.create_index("ix_solar_wind_timestamp", "solar_wind", ["timestamp"])
    op.execute("SELECT create_hypertable('solar_wind', 'timestamp', if_not_exists => TRUE)")

    op.create_table(
        "reentry_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("norad_id", sa.Integer(), nullable=False),
        sa.Column("expected_reentry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["norad_id"], ["satellites.norad_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_reentry_events_norad_id", "reentry_events", ["norad_id"])

    op.create_table(
        "eo_collections",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("events", sa.Text(), nullable=False),
        sa.Column("secret_hash", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("webhook_id", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["webhook_id"], ["webhooks.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])
    op.create_index("ix_webhook_deliveries_attempted_at", "webhook_deliveries", ["attempted_at"])

    op.add_column("orbital_elements", sa.Column("tle_line1", sa.String(), nullable=True))
    op.add_column("orbital_elements", sa.Column("tle_line2", sa.String(), nullable=True))

    op.execute(
        """
        INSERT INTO provider_health (id, status, updated_at)
        VALUES
            ('space-track',    'unknown', now()),
            ('celestrak',      'unknown', now()),
            ('nasa-neows',     'unknown', now()),
            ('noaa-swpc',      'unknown', now()),
            ('the-space-devs', 'unknown', now()),
            ('jpl-horizons',   'unknown', now()),
            ('esa',            'unknown', now())
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_table("eo_collections")
    op.drop_table("reentry_events")
    op.drop_table("solar_wind")
    op.drop_table("space_weather_indices")
    op.drop_table("close_approaches")
    op.drop_table("near_earth_objects")
    op.drop_table("satellite_decays")
    op.drop_table("conjunction_events")
    op.drop_table("launches")
    op.drop_table("api_keys")
    op.drop_table("provider_health")
    op.drop_column("orbital_elements", "tle_line2")
    op.drop_column("orbital_elements", "tle_line1")

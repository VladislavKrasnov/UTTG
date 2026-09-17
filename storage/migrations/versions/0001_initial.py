"""initial

Revision ID: 0001
Revises:
Create Date: 2026-09-21 20:20:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    op.create_table(
        "satellites",
        sa.Column("norad_id", sa.Integer(), nullable=False),
        sa.Column("cospar_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("operator", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("object_type", sa.String(), nullable=True),
        sa.Column("orbit_class", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
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
    )
    op.create_index(op.f("ix_satellites_cospar_id"), "satellites", ["cospar_id"], unique=False)

    op.create_table(
        "orbital_elements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("norad_id", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inclination", sa.Float(), nullable=True),
        sa.Column("right_ascension", sa.Float(), nullable=True),
        sa.Column("eccentricity", sa.Float(), nullable=True),
        sa.Column("argument_of_perigee", sa.Float(), nullable=True),
        sa.Column("mean_anomaly", sa.Float(), nullable=True),
        sa.Column("mean_motion", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["norad_id"],
            ["satellites.norad_id"],
        ),
        sa.PrimaryKeyConstraint("id", "epoch"),
    )
    op.execute("SELECT create_hypertable('orbital_elements', 'epoch');")

    op.create_index(op.f("ix_orbital_elements_epoch"), "orbital_elements", ["epoch"], unique=False)
    op.create_index(
        op.f("ix_orbital_elements_norad_id"), "orbital_elements", ["norad_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("orbital_elements")
    op.drop_table("satellites")

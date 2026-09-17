from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM solar_wind current_row
        USING solar_wind duplicate
        WHERE current_row.timestamp = duplicate.timestamp
          AND current_row.ctid < duplicate.ctid
        """
    )
    op.create_index(
        "uq_solar_wind_timestamp",
        "solar_wind",
        ["timestamp"],
        unique=True,
    )
    op.execute(
        """
        DELETE FROM close_approaches current_row
        USING close_approaches duplicate
        WHERE current_row.neo_id = duplicate.neo_id
          AND current_row.close_approach_date = duplicate.close_approach_date
          AND current_row.orbiting_body = duplicate.orbiting_body
          AND current_row.ctid < duplicate.ctid
        """
    )
    op.create_index(
        "uq_close_approach_identity",
        "close_approaches",
        ["neo_id", "close_approach_date", "orbiting_body"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_close_approach_identity", table_name="close_approaches")
    op.drop_index("uq_solar_wind_timestamp", table_name="solar_wind")

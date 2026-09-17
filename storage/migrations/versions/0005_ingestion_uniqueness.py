from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM space_weather_indices current_row
        USING space_weather_indices duplicate
        WHERE current_row.timestamp = duplicate.timestamp
          AND current_row.ctid < duplicate.ctid
        """
    )
    op.create_index(
        "uq_space_weather_indices_timestamp",
        "space_weather_indices",
        ["timestamp"],
        unique=True,
    )
    op.create_index(
        "uq_orbital_elements_source_epoch",
        "orbital_elements",
        ["norad_id", "provider", "epoch"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_orbital_elements_source_epoch", table_name="orbital_elements")
    op.drop_index("uq_space_weather_indices_timestamp", table_name="space_weather_indices")

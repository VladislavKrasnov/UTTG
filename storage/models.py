from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from storage.database import Base


class Satellite(Base):
    __tablename__ = "satellites"

    norad_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cospar_id: Mapped[str | None] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    operator: Mapped[str | None] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    object_type: Mapped[str | None] = mapped_column(String)
    orbit_class: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class OrbitalElement(Base):
    __tablename__ = "orbital_elements"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    norad_id: Mapped[int] = mapped_column(Integer, ForeignKey("satellites.norad_id"), index=True)
    epoch: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, index=True)
    inclination: Mapped[float | None] = mapped_column(Float)
    right_ascension: Mapped[float | None] = mapped_column(Float)
    eccentricity: Mapped[float | None] = mapped_column(Float)
    argument_of_perigee: Mapped[float | None] = mapped_column(Float)
    mean_anomaly: Mapped[float | None] = mapped_column(Float)
    mean_motion: Mapped[float | None] = mapped_column(Float)
    tle_line1: Mapped[str | None] = mapped_column(String)
    tle_line2: Mapped[str | None] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ConjunctionEvent(Base):
    __tablename__ = "conjunction_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    norad_id_1: Mapped[int] = mapped_column(Integer, ForeignKey("satellites.norad_id"), index=True)
    norad_id_2: Mapped[int] = mapped_column(Integer, index=True)
    tca: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    miss_distance: Mapped[float] = mapped_column(Float)
    probability: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SatelliteDecay(Base):
    __tablename__ = "satellite_decays"

    norad_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("satellites.norad_id"), primary_key=True
    )
    decay_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class NearEarthObject(Base):
    __tablename__ = "near_earth_objects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    absolute_magnitude_h: Mapped[float | None] = mapped_column(Float)
    estimated_diameter_min_km: Mapped[float | None] = mapped_column(Float)
    estimated_diameter_max_km: Mapped[float | None] = mapped_column(Float)
    is_potentially_hazardous: Mapped[bool] = mapped_column(Boolean)
    is_sentry_object: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CloseApproach(Base):
    __tablename__ = "close_approaches"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    neo_id: Mapped[str] = mapped_column(String, ForeignKey("near_earth_objects.id"), index=True)
    close_approach_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    relative_velocity_kms: Mapped[float] = mapped_column(Float)
    miss_distance_au: Mapped[float] = mapped_column(Float)
    orbiting_body: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SpaceWeatherIndex(Base):
    __tablename__ = "space_weather_indices"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, index=True
    )
    kp_index: Mapped[float] = mapped_column(Float)
    ap_index: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SolarWind(Base):
    __tablename__ = "solar_wind"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, index=True
    )
    speed_km_s: Mapped[float] = mapped_column(Float)
    density_cm3: Mapped[float] = mapped_column(Float)
    temperature_k: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ReentryEvent(Base):
    __tablename__ = "reentry_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    norad_id: Mapped[int] = mapped_column(Integer, ForeignKey("satellites.norad_id"), index=True)
    expected_reentry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class EarthObservationCollection(Base):
    __tablename__ = "eo_collections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Launch(Base):
    __tablename__ = "launches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(String)
    events: Mapped[str] = mapped_column(Text)
    secret_hash: Mapped[str | None] = mapped_column(String)
    secret_ciphertext: Mapped[str | None] = mapped_column(Text)
    # Webhooks are owned by a keyed IP digest. Raw client addresses are never
    # stored, and ownership has no connection to application API keys.
    owner_ip_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    webhook_id: Mapped[str] = mapped_column(String, ForeignKey("webhooks.id"), index=True)
    payload: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ProviderHealth(Base):
    __tablename__ = "provider_health"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class EndpointMetricBucket(Base):
    __tablename__ = "endpoint_metric_buckets"

    bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    route: Mapped[str] = mapped_column(String(255), primary_key=True)
    method: Mapped[str] = mapped_column(String(8), primary_key=True)
    request_count: Mapped[int] = mapped_column(BigInteger)
    server_error_count: Mapped[int] = mapped_column(BigInteger)
    duration_sum_ms: Mapped[float] = mapped_column(Float)
    duration_max_ms: Mapped[float] = mapped_column(Float)
    response_bytes: Mapped[int] = mapped_column(BigInteger)
    cache_hit_count: Mapped[int] = mapped_column(BigInteger)

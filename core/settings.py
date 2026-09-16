from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: Literal["development", "test", "production"] = "development"
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    database_url: str
    valkey_url: str
    nats_url: str
    ip_fingerprint_secret: str = Field(min_length=12)
    webhook_encryption_key: str | None = None
    trusted_proxies: str = "127.0.0.1"
    cors_origins: str = "https://uttg.example.com"
    database_pool_size: int = Field(default=20, ge=2, le=200)
    database_max_overflow: int = Field(default=10, ge=0, le=200)
    database_pool_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    database_statement_timeout_ms: int = Field(default=3000, ge=100, le=60000)
    cache_compute_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    cache_wait_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    cache_max_value_bytes: int = Field(default=2_000_000, ge=1024, le=16_000_000)
    cache_background_refresh_limit: int = Field(default=32, ge=1, le=512)
    webhook_delivery_concurrency: int = Field(default=32, ge=1, le=256)
    webhook_batch_size: int = Field(default=32, ge=1, le=256)
    webhook_max_attempts: int = Field(default=5, ge=1, le=12)
    webhook_max_per_ip: int = Field(default=5, ge=1, le=100)
    webhook_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    webhook_max_body_bytes: int = Field(default=262_144, ge=1024, le=2_000_000)
    analytics_queue_size: int = Field(default=20_000, ge=100, le=200_000)
    analytics_batch_size: int = Field(default=500, ge=10, le=5000)
    analytics_flush_seconds: float = Field(default=0.5, gt=0, le=10)
    request_body_max_bytes: int = Field(default=1_048_576, ge=1024, le=16_000_000)
    otel_exporter_otlp_endpoint: str | None = None
    nasa_api_key: str | None = None
    space_track_identity: str | None = None
    space_track_password: str | None = None
    the_space_devs_api_key: str | None = None
    enable_celestrak: bool = True
    enable_noaa_swpc: bool = True
    enable_jpl: bool = True
    enable_esa: bool = False
    enable_space_devs_public_api: bool = True
    http_proxy: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="UTTG_",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment != "production":
            return self
        weak_values = {
            "change-this-secret-for-ip-hashing",
            "testipsecret",
        }
        if len(self.ip_fingerprint_secret) < 32 or self.ip_fingerprint_secret in weak_values:
            raise ValueError("UTTG_IP_FINGERPRINT_SECRET must be a unique 32+ character secret")
        if not self.webhook_encryption_key or len(self.webhook_encryption_key) < 32:
            raise ValueError("UTTG_WEBHOOK_ENCRYPTION_KEY must be a unique 32+ character secret")
        if self.webhook_encryption_key == self.ip_fingerprint_secret:
            raise ValueError("Webhook encryption and IP fingerprint secrets must be independent")
        if "*" in {origin.strip() for origin in self.cors_origins.split(",")}:
            raise ValueError("Wildcard CORS origins are forbidden in production")
        return self


settings = Settings()  # type: ignore[call-arg]  # Values are loaded from UTTG_* variables.

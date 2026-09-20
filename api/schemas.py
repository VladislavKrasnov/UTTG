from datetime import datetime

from pydantic import BaseModel


# Orbital Element Schema
class OrbitalElementResponse(BaseModel):
    norad_id: int
    epoch: datetime
    inclination: float | None
    right_ascension: float | None
    eccentricity: float | None
    argument_of_perigee: float | None
    mean_anomaly: float | None
    mean_motion: float | None
    provider: str


# Position Schema
class PositionResponse(BaseModel):
    norad_id: int
    timestamp: datetime
    latitude: float
    longitude: float
    altitude: float


# Conjunction Schema
class ConjunctionResponse(BaseModel):
    id: str
    norad_id_1: int
    norad_id_2: int
    tca: datetime
    miss_distance: float
    probability: float | None


# Decay Schema
class DecayResponse(BaseModel):
    norad_id: int
    decay_date: datetime


# NEO Schema
class NearEarthObjectResponse(BaseModel):
    id: str
    name: str
    absolute_magnitude_h: float | None
    estimated_diameter_min_km: float | None
    estimated_diameter_max_km: float | None
    is_potentially_hazardous: bool
    is_sentry_object: bool


class CloseApproachResponse(BaseModel):
    neo_id: str
    close_approach_date: datetime
    relative_velocity_kms: float
    miss_distance_au: float
    orbiting_body: str


class SpaceWeatherIndexResponse(BaseModel):
    timestamp: datetime
    kp_index: float
    ap_index: float | None


class SolarWindResponse(BaseModel):
    timestamp: datetime
    speed_km_s: float
    density_cm3: float
    temperature_k: float


class LaunchResponse(BaseModel):
    id: str
    name: str
    status: str | None
    window_start: datetime | None
    window_end: datetime | None
    provider: str | None


class ReentryEventResponse(BaseModel):
    id: str
    norad_id: int
    expected_reentry_time: datetime
    latitude: float | None
    longitude: float | None


class EoCollectionResponse(BaseModel):
    id: str
    name: str
    provider: str

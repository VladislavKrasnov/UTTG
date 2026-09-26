from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_KNOWN_SITE_COORDINATES: tuple[tuple[str, float, float], ...] = (
    ("cape canaveral", 28.4889, -80.5778),
    ("kennedy", 28.5729, -80.6490),
    ("vandenberg", 34.7420, -120.5724),
    ("starbase", 25.9972, -97.1566),
    ("boca chica", 25.9972, -97.1566),
    ("wallops", 37.8337, -75.4881),
    ("mahia", -39.2615, 177.8649),
    ("baikonur", 45.9650, 63.3050),
    ("plesetsk", 62.9271, 40.5777),
    ("vostochny", 51.8844, 128.3339),
    ("jiuquan", 40.9581, 100.2914),
    ("xichang", 28.2463, 102.0269),
    ("taiyuan", 38.8491, 111.6081),
    ("wenchang", 19.6145, 110.9510),
    ("yellow sea", 34.9000, 121.2000),
    ("haiyang", 36.6880, 121.2500),
    ("tanegashima", 30.4009, 130.9753),
    ("uchinoura", 31.2510, 131.0820),
    ("satish dhawan", 13.7199, 80.2304),
    ("sriharikota", 13.7199, 80.2304),
    ("kourou", 5.2360, -52.7686),
    ("guiana", 5.2360, -52.7686),
    ("esrange", 67.8932, 21.1069),
    ("andøya", 69.2945, 16.0208),
    ("naro", 34.4317, 127.5350),
)


@dataclass(frozen=True, slots=True)
class UpcomingLaunch:
    id: str
    name: str
    status: str | None
    window_start: datetime
    window_end: datetime | None
    provider: str
    operator: str | None
    vehicle: str | None
    pad: str | None
    location: str | None
    latitude: float | None
    longitude: float | None
    mission_description: str | None
    weather_summary: str | None
    info_url: str | None


def parse_timestamp(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def coordinate(value: Any, bound: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if -bound <= number <= bound else None


def known_site_coordinates(location: str | None) -> tuple[float | None, float | None]:
    if not location:
        return None, None
    normalized = location.casefold()
    for keyword, latitude, longitude in _KNOWN_SITE_COORDINATES:
        if keyword in normalized:
            return latitude, longitude
    return None, None


def bounded_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.split())
    return collapsed[:limit] or None

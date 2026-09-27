from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sgp4.api import Satrec

from providers.transport import ProviderTransport

_REVOLUTIONS_PER_DAY_PER_RADIAN_PER_MINUTE = 1440.0 / (2.0 * math.pi)
_JULIAN_UNIX_EPOCH = 2440587.5
_NOT_MODIFIED_MARKER = "has not updated since your last successful"
_ALLOWED_GROUPS = frozenset({"active", "stations", "visual", "gnss", "weather", "last-30-days"})


class CelestrakNotModifiedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TwoLineElementSet:
    norad_id: int
    name: str
    cospar_id: str | None
    epoch: datetime
    inclination: float
    right_ascension: float
    eccentricity: float
    argument_of_perigee: float
    mean_anomaly: float
    mean_motion: float
    tle_line1: str
    tle_line2: str


def _international_designator(line1: str) -> str | None:
    raw = line1[9:17].strip()
    if len(raw) < 5 or not raw[:2].isdigit():
        return None
    century = "19" if int(raw[:2]) >= 57 else "20"
    return f"{century}{raw[:2]}-{raw[2:]}"


def _epoch(satellite: Satrec) -> datetime:
    days_since_unix = (satellite.jdsatepoch - _JULIAN_UNIX_EPOCH) + satellite.jdsatepochF
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(days=days_since_unix)


def parse_tle_catalog(text: str) -> list[TwoLineElementSet]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    records: list[TwoLineElementSet] = []
    index = 0
    while index + 1 < len(lines):
        if lines[index].startswith("1 ") and lines[index + 1].startswith("2 "):
            name, line1, line2 = "", lines[index], lines[index + 1]
            index += 2
        elif (
            index + 2 < len(lines)
            and lines[index + 1].startswith("1 ")
            and lines[index + 2].startswith("2 ")
        ):
            name = lines[index].removeprefix("0 ").strip()
            line1, line2 = lines[index + 1], lines[index + 2]
            index += 3
        else:
            index += 1
            continue
        try:
            satellite = Satrec.twoline2rv(line1, line2)
        except ValueError:
            continue
        if satellite.error != 0 or satellite.satnum <= 0:
            continue
        records.append(
            TwoLineElementSet(
                norad_id=satellite.satnum,
                name=name or str(satellite.satnum),
                cospar_id=_international_designator(line1),
                epoch=_epoch(satellite),
                inclination=math.degrees(satellite.inclo),
                right_ascension=math.degrees(satellite.nodeo),
                eccentricity=satellite.ecco,
                argument_of_perigee=math.degrees(satellite.argpo),
                mean_anomaly=math.degrees(satellite.mo),
                mean_motion=satellite.no_kozai * _REVOLUTIONS_PER_DAY_PER_RADIAN_PER_MINUTE,
                tle_line1=line1,
                tle_line2=line2,
            )
        )
    return records


class CelestrakClient:
    def __init__(self) -> None:
        self._transport = ProviderTransport(
            "celestrak",
            "https://celestrak.org",
            concurrency=1,
            maximum_response_bytes=16_000_000,
        )

    async def get_group(self, group: str = "active") -> list[TwoLineElementSet]:
        if group not in _ALLOWED_GROUPS:
            raise ValueError("Unsupported CelesTrak group")
        text = await self._transport.get_text(
            "/NORAD/elements/gp.php", {"GROUP": group, "FORMAT": "TLE"}
        )
        if _NOT_MODIFIED_MARKER in text[:512]:
            raise CelestrakNotModifiedError(group)
        return parse_tle_catalog(text)

    async def close(self) -> None:
        await self._transport.close()

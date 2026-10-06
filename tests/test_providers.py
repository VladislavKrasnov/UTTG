from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path
from typing import Any

import pytest

from providers.celestrak import parse_tle_catalog
from providers.jpl import parse_close_approaches, parse_designations
from providers.launch_records import known_site_coordinates
from providers.noaa import parse_planetary_k, parse_solar_wind
from providers.rocketlaunch import parse_rocketlaunch_launches
from providers.spacedevs import parse_spacedevs_launches

FIXTURES = Path(__file__).parent / "fixtures"


def _json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def test_celestrak_tle_catalog_keeps_lines_for_sgp4() -> None:
    records = parse_tle_catalog((FIXTURES / "stations.tle").read_text())
    iss = next(record for record in records if record.norad_id == 25544)
    assert iss.name == "ISS (ZARYA)"
    assert iss.cospar_id == "1998-067A"
    assert iss.tle_line1.startswith("1 25544U")
    assert iss.tle_line2.startswith("2 25544")
    assert 51.0 < iss.inclination < 52.0
    assert 15.0 < iss.mean_motion < 16.0
    assert iss.epoch.tzinfo is UTC
    assert len({record.norad_id for record in records}) == len(records)


def test_celestrak_parser_skips_corrupt_lines() -> None:
    text = "BROKEN\n1 garbage\n2 garbage\n" + (FIXTURES / "stations.tle").read_text()
    assert parse_tle_catalog(text)[0].norad_id == 25544


def test_noaa_kp_uses_numeric_estimate_instead_of_letter_suffix() -> None:
    records = _json("noaa_kp.json")
    observations = parse_planetary_k(records)
    assert observations
    assert all(0.0 <= item.kp_index <= 9.0 for item in observations)
    assert observations[-1].kp_index == round(records[-2]["estimated_kp"], 2)
    assert observations == sorted(observations, key=lambda item: item.timestamp)


def test_noaa_kp_skips_provisional_latest_minute() -> None:
    records = [
        {"time_tag": "2026-10-18T04:13:00", "kp_index": 0, "estimated_kp": 0.33},
        {"time_tag": "2026-10-18T04:14:00", "kp_index": 0, "estimated_kp": 0.0},
    ]
    assert [item.kp_index for item in parse_planetary_k(records)] == [0.33]


def test_noaa_solar_wind_ignores_inactive_and_null_sources() -> None:
    records = _json("noaa_wind.json")
    observations = parse_solar_wind(records)
    assert observations
    assert all(item.speed_km_s >= 100.0 for item in observations)
    active_times = {
        record["time_tag"] for record in records if record.get("active") and record["proton_speed"]
    }
    assert len(observations) <= len(active_times)


def test_noaa_solar_wind_rejects_null_rows() -> None:
    assert (
        parse_solar_wind(
            [
                {
                    "time_tag": "2026-10-17T20:00:00",
                    "active": True,
                    "proton_speed": None,
                    "proton_density": 1.0,
                    "proton_temperature": 1.0,
                }
            ]
        )
        == []
    )


def test_rocketlaunch_records_carry_operator_vehicle_and_site() -> None:
    launches = parse_rocketlaunch_launches(_json("rll.json"))
    assert len(launches) == 5
    first = launches[0]
    assert first.id.startswith("rll-")
    assert first.operator == "SpaceX"
    assert first.vehicle == "Falcon 9"
    assert first.latitude is not None and first.longitude is not None
    assert first.weather_summary and "°C" in first.weather_summary
    assert first.info_url and first.info_url.startswith("https://www.rocketlaunch.live/launch/")
    assert all(launch.window_start.tzinfo is not None for launch in launches)


def test_spacedevs_records_carry_pad_coordinates() -> None:
    launches = parse_spacedevs_launches(_json("ll2.json"))
    assert launches
    assert all(launch.operator for launch in launches)
    assert all(launch.latitude is not None for launch in launches)


def test_launch_parsers_tolerate_malformed_payloads() -> None:
    assert parse_rocketlaunch_launches({"result": [None, {"id": 1}, "x"]}) == []
    assert parse_spacedevs_launches({"results": [{"id": "a", "net": "not-a-date"}]}) == []


@pytest.mark.parametrize(
    ("location", "expected_latitude"),
    [("Cape Canaveral SFS, United States", 28.4889), ("Unknown Atoll", None), (None, None)],
)
def test_known_site_coordinates(location: str | None, expected_latitude: float | None) -> None:
    assert known_site_coordinates(location)[0] == expected_latitude


def test_jpl_close_approaches_estimate_diameter_from_magnitude() -> None:
    records = parse_close_approaches(_json("cad.json"))
    assert records
    first = records[0]
    assert first.approach_at.tzinfo is UTC
    assert first.miss_distance_au < 0.05
    assert first.diameter_min_km is not None and first.diameter_max_km is not None
    assert first.diameter_min_km <= first.diameter_max_km


def test_jpl_designation_sets_support_both_payload_shapes() -> None:
    assert parse_designations(_json("sentry.json"), "des")
    assert len(parse_designations(_json("cad_pha.json"), "des")) == _json("cad_pha.json")["count"]
    assert parse_close_approaches({"fields": ["des"], "data": [["x"]]}) == []


async def test_celestrak_not_modified_reply_is_not_parsed_as_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from providers.celestrak import CelestrakClient, CelestrakNotModifiedError

    client = CelestrakClient()
    reply = (FIXTURES / "celestrak_not_modified.txt").read_text()

    async def fake_get_text(path: str, params: dict[str, Any]) -> str:
        return reply

    monkeypatch.setattr(client._transport, "get_text", fake_get_text)
    try:
        with pytest.raises(CelestrakNotModifiedError):
            await client.get_group("active")
    finally:
        await client.close()
    assert parse_tle_catalog(reply) == []

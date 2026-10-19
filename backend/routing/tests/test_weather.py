from datetime import datetime
from zoneinfo import ZoneInfo

from routing.weather import parse_open_meteo


def test_parser_converts_centimeters_of_snow_and_keeps_miles_per_hour():
    series = parse_open_meteo(
        {
            "timezone": "America/Chicago",
            "hourly_units": {
                "wind_speed_10m": "mp/h",
                "rain": "inch",
                "snowfall": "cm",
            },
            "hourly": {
                "time": ["2026-10-20T08:00", "2026-10-20T09:00"],
                "wind_speed_10m": [36, None],
                "rain": [0.1, 0],
                "snowfall": [2.54, 0],
            },
        }
    )
    assert series.timezone == "America/Chicago"
    assert series.wind_mph[0] == 36
    assert series.wind_mph[1] is None
    assert series.rain_in_hr[0] == 0.1
    assert series.snow_in_hr[0] == 1

    eight = datetime(2026, 10, 20, 8, 20, tzinfo=ZoneInfo("America/Chicago"))
    reading = series.reading_at(eight)
    assert reading is not None
    assert reading[0] == 36

    outside = datetime(2026, 10, 22, 8, tzinfo=ZoneInfo("America/Chicago"))
    assert series.reading_at(outside) is None

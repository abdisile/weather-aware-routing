from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from routing.providers import Place, RawRoute, RouteSet
from routing.sampling import Step
from routing.trip import TripRequest, build_trip
from routing.weather import HourlySeries


CHICAGO = ZoneInfo("America/Chicago")


class FixedGeocoder:
    def geocode(self, text: str) -> Place:
        if "Dallas" in text:
            return Place("Dallas, TX", 32.7767, -96.7970)
        return Place("Chicago, IL", 41.8781, -87.6298)


class ScriptedRouter:
    def __init__(self, routes):
        self._routes = routes

    def routes(self, origin, destination, load_lb):
        del origin, destination, load_lb
        return RouteSet(tuple(self._routes), provider="test", profile="driving")


class ScriptedForecast:
    def __init__(self, series_for):
        self.series_for = series_for

    def hourly_for(self, points):
        found = {}
        for lat, lon in points:
            key = (round(lat, 2), round(lon, 2))
            found[key] = self.series_for(key)
        return found


def _series(wind: float, rain: float, snow: float) -> HourlySeries:
    start = datetime(2026, 10, 20, 0, 0, tzinfo=CHICAGO)
    times = tuple(start + timedelta(hours=hour) for hour in range(24 * 7))
    count = len(times)
    return HourlySeries(
        timezone="America/Chicago",
        times=times,
        wind_mph=tuple(wind for _ in range(count)),
        rain_in_hr=tuple(rain for _ in range(count)),
        snow_in_hr=tuple(snow for _ in range(count)),
    )


def _route(lat: float, lon: float, miles: float, hours: float, via: str) -> RawRoute:
    return RawRoute(
        geometry=((lon, lat), (lon, lat)),
        steps=(Step(miles, hours * 3600, via),),
        distance_miles=miles,
        duration_seconds=hours * 3600,
        via=via,
    )


def _forecast_for(key: tuple[float, float]) -> HourlySeries:
    lat, lon = key
    if abs(lat - 32.1) < 0.05 and abs(lon + 96.1) < 0.05:
        return _series(wind=40, rain=0, snow=0)
    if abs(lat - 35.2) < 0.05 and abs(lon + 94.2) < 0.05:
        return _series(wind=5, rain=0, snow=2.5)
    return _series(wind=5, rain=0, snow=0)


def test_load_above_40000_lb_flips_the_recommendation():
    routes = [
        _route(32.1, -96.1, miles=40, hours=5, via="I-35"),
        _route(35.2, -94.2, miles=15, hours=6, via="US-69"),
    ]
    request = TripRequest("Dallas, TX", "Chicago, IL", "2026-10-20T08:00", 20_000, 25)
    light = build_trip(
        request,
        geocoder=FixedGeocoder(),
        router=ScriptedRouter(routes),
        forecast=ScriptedForecast(_forecast_for),
    )
    assert light["recommended_route_id"] == "route-1"
    assert "0 severe miles" in light["recommendation_reason"]
    assert light["routes"][0]["checkpoints"][0]["eta_label"] == "Tue 8:00 AM"
    assert light["heatmap"]["points"]
    assert len(light["heatmap"]["points"][0]["risk_by_hour"]) == 49

    heavy_request = TripRequest("Dallas, TX", "Chicago, IL", "2026-10-20T08:00", 45_000, 25)
    heavy = build_trip(
        heavy_request,
        geocoder=FixedGeocoder(),
        router=ScriptedRouter(routes),
        forecast=ScriptedForecast(_forecast_for),
    )
    assert heavy["recommended_route_id"] == "route-2"
    assert heavy["routes"][0]["id"] == "route-2"
    windy = next(route for route in heavy["routes"] if route["id"] == "route-1")
    assert windy["checkpoints"][0]["risk"] == "severe"
    assert any("40,000" in reason for reason in windy["checkpoints"][0]["reasons"])


def test_parse_request_rejects_an_interval_outside_the_brief():
    from routing.providers import TripError
    from routing.trip import parse_request

    try:
        parse_request(
            {
                "origin": "Dallas, TX",
                "destination": "Chicago, IL",
                "departure": "2026-10-20T08:00",
                "load_lb": 1000,
                "sample_miles": 15,
            }
        )
    except TripError as exc:
        assert exc.status == 400
        assert "10, 25, or 50" in str(exc)
    else:
        raise AssertionError("expected a 400")

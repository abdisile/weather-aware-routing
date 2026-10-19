"""Build the trip payload from geocoding, routes, and an hourly forecast."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from routing.corridor import corridor_points
from routing.providers import Place, RawRoute, RouteSet, TripError
from routing.risk import (
    RankedRoute,
    RiskLevel,
    rank_explanations,
    rank_routes,
    recommendation_reason,
    score_checkpoint,
    score_segments,
)
from routing.sampling import SamplePoint, build_samples, haversine_miles
from routing.weather import HourlySeries

FORECAST_HOURS = 49
SAMPLE_INTERVALS = {10, 25, 50}


class Geocoder(Protocol):
    def geocode(self, text: str) -> Place: ...


class Router(Protocol):
    def routes(self, origin: Place, destination: Place, load_lb: float) -> RouteSet: ...


class Forecast(Protocol):
    def hourly_for(self, points: list[tuple[float, float]]) -> dict[tuple[float, float], HourlySeries]: ...


class PlacePayload(TypedDict):
    label: str
    lat: float
    lon: float


class SegmentPayload(TypedDict):
    miles: float
    risk: str


class CheckpointPayload(TypedDict):
    mile: float
    lat: float
    lon: float
    eta: str
    eta_label: str
    wind_mph: float | None
    rain_in_hr: float | None
    snow_in_hr: float | None
    risk: str
    reasons: list[str]


class RoutePayload(TypedDict):
    id: str
    name: str
    via: str
    distance_miles: float
    duration_seconds: float
    geometry: list[list[float]]
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    unknown_miles: float
    average_risk: float | None
    segments: list[SegmentPayload]
    checkpoints: list[CheckpointPayload]
    rank_reason: str


class HeatmapPointPayload(TypedDict):
    lat: float
    lon: float
    risk_by_hour: list[str]


class HeatmapPayload(TypedDict):
    points: list[HeatmapPointPayload]


class TripPayload(TypedDict):
    origin: PlacePayload
    destination: PlacePayload
    departure: str
    timezone: str
    load_lb: float
    sample_miles: int
    routing_provider: str
    routing_profile: str
    recommended_route_id: str
    recommendation_reason: str
    route_note: str | None
    routes: list[RoutePayload]
    heatmap: HeatmapPayload


SeriesByPoint = dict[tuple[float, float], HourlySeries]


@dataclass(frozen=True)
class TripRequest:
    origin_text: str
    destination_text: str
    departure_naive: str
    load_lb: float
    sample_miles: int


def parse_request(data: object) -> TripRequest:
    if not isinstance(data, dict):
        raise TripError("Request body must be an object.")
    origin = str(data.get("origin") or "").strip()
    destination = str(data.get("destination") or "").strip()
    if not origin:
        raise TripError("Enter an origin.")
    if not destination:
        raise TripError("Enter a destination.")
    departure = str(data.get("departure") or "").strip()
    if not departure:
        raise TripError("Enter a departure time.")
    try:
        load_lb = float(data.get("load_lb"))
    except (TypeError, ValueError) as exc:
        raise TripError("Enter a load weight in pounds.") from exc
    if load_lb < 0 or load_lb > 200_000:
        raise TripError("Load weight must be between 0 and 200,000 lb.")
    try:
        sample_miles = int(data.get("sample_miles"))
    except (TypeError, ValueError) as exc:
        raise TripError("Sample interval must be 10, 25, or 50 miles.") from exc
    if sample_miles not in SAMPLE_INTERVALS:
        raise TripError("Sample interval must be 10, 25, or 50 miles.")
    return TripRequest(origin, destination, departure, load_lb, sample_miles)


def build_trip(
    request: TripRequest,
    *,
    geocoder: Geocoder,
    router: Router,
    forecast: Forecast,
) -> TripPayload:
    origin = geocoder.geocode(request.origin_text)
    destination = geocoder.geocode(request.destination_text)
    if _same_place(origin, destination):
        raise TripError("Origin and destination resolve to the same place.")

    route_set = router.routes(origin, destination, request.load_lb)
    raw_routes = route_set.routes[:3]
    if not raw_routes:
        raise TripError("No driving route was found between those places.")

    prepared = [_prepare_route(index, raw, request.sample_miles) for index, raw in enumerate(raw_routes, start=1)]
    corridor = corridor_points([list(item.raw.geometry) for item in prepared])
    lookup_points = [(sample.lat, sample.lon) for item in prepared for sample in item.samples]
    lookup_points.extend(corridor)
    series_by_key = forecast.hourly_for(lookup_points)

    origin_series = _series_for(series_by_key, prepared[0].samples[0].lat, prepared[0].samples[0].lon)
    if origin_series is None:
        raise TripError("Weather service did not return a forecast for the origin.", 502)
    departure = _parse_departure(request.departure_naive, origin_series.timezone)

    serialized: dict[str, RoutePayload] = {}
    ranked_input: list[RankedRoute] = []
    for item in prepared:
        route_id = f"route-{item.index}"
        name = f"Route {item.index}"
        checkpoints, levels = _checkpoints(
            item,
            series_by_key,
            departure,
            request.load_lb,
        )
        score = score_segments(levels)
        ranked_input.append(RankedRoute(route_id, name, item.raw.duration_seconds, score))
        serialized[route_id] = {
            "id": route_id,
            "name": name,
            "via": item.raw.via,
            "distance_miles": round(item.raw.distance_miles, 1),
            "duration_seconds": round(item.raw.duration_seconds, 1),
            "geometry": [[round(lon, 5), round(lat, 5)] for lon, lat in item.raw.geometry],
            "no_travel_miles": round(score.no_travel_miles, 2),
            "severe_miles": round(score.severe_miles, 2),
            "high_miles": round(score.high_miles, 2),
            "moderate_miles": round(score.moderate_miles, 2),
            "low_miles": round(score.low_miles, 2),
            "unknown_miles": round(score.unknown_miles, 2),
            "average_risk": None if score.average_risk is None else round(score.average_risk, 2),
            "segments": [
                {"miles": round(segment.miles, 2), "risk": segment.label}
                for segment in score.segments
            ],
            "checkpoints": checkpoints,
            "rank_reason": "",
        }

    ranked = rank_routes(ranked_input)
    explanations = rank_explanations(ranked)
    for route_id, text in explanations.items():
        serialized[route_id]["rank_reason"] = text
    reason = recommendation_reason(ranked)
    routes = [serialized[route.route_id] for route in ranked]
    note = None
    if len(routes) < 3:
        label = "route" if len(routes) == 1 else "routes"
        note = f"The routing service returned {len(routes)} {label}."

    return {
        "origin": {"label": origin.label, "lat": origin.lat, "lon": origin.lon},
        "destination": {
            "label": destination.label,
            "lat": destination.lat,
            "lon": destination.lon,
        },
        "departure": departure.isoformat(),
        "timezone": origin_series.timezone,
        "load_lb": request.load_lb,
        "sample_miles": request.sample_miles,
        "routing_provider": route_set.provider,
        "routing_profile": route_set.profile,
        "recommended_route_id": ranked[0].route_id,
        "recommendation_reason": reason,
        "route_note": note,
        "routes": routes,
        "heatmap": {
            "points": _heatmap(corridor, series_by_key, departure, request.load_lb),
        },
    }


@dataclass(frozen=True)
class _Prepared:
    index: int
    raw: RawRoute
    samples: list[SamplePoint]


def _prepare_route(index: int, raw: RawRoute, interval: int) -> _Prepared:
    if not raw.geometry:
        raise TripError("A route came back without a line to sample.", 502)
    samples = build_samples(
        list(raw.geometry),
        list(raw.steps),
        total_miles=raw.distance_miles,
        total_seconds=raw.duration_seconds,
        interval=interval,
    )
    return _Prepared(index, raw, samples)


def _checkpoints(
    item: _Prepared,
    series_by_key: SeriesByPoint,
    departure: datetime,
    load_lb: float,
) -> tuple[list[CheckpointPayload], list[tuple[float, RiskLevel | None]]]:
    checkpoints = []
    levels = []
    for sample in item.samples:
        eta = departure + timedelta(seconds=sample.eta_offset_seconds)
        series = _series_for(series_by_key, sample.lat, sample.lon)
        reading = series.reading_at(eta) if series is not None else None
        wind, rain, snow = reading if reading is not None else (None, None, None)
        risk = score_checkpoint(
            wind_mph=wind,
            rain_in_hr=rain,
            snow_in_hr=snow,
            load_lb=load_lb,
        )
        levels.append((sample.mile, risk.level))
        checkpoints.append(
            {
                "mile": round(sample.mile, 2),
                "lat": round(sample.lat, 5),
                "lon": round(sample.lon, 5),
                "eta": eta.isoformat(),
                "eta_label": _format_eta(eta),
                "wind_mph": _round(wind, 1),
                "rain_in_hr": _round(rain, 2),
                "snow_in_hr": _round(snow, 2),
                "risk": risk.label,
                "reasons": list(risk.reasons),
            }
        )
    return checkpoints, levels


def _heatmap(
    points: list[tuple[float, float]],
    series_by_key: SeriesByPoint,
    departure: datetime,
    load_lb: float,
) -> list[HeatmapPointPayload]:
    painted = []
    for lat, lon in points:
        series = _series_for(series_by_key, lat, lon)
        labels = []
        for hour in range(FORECAST_HOURS):
            instant = departure + timedelta(hours=hour)
            reading = series.reading_at(instant) if series is not None else None
            if reading is None:
                labels.append("unknown")
                continue
            wind, rain, snow = reading
            labels.append(
                score_checkpoint(
                    wind_mph=wind,
                    rain_in_hr=rain,
                    snow_in_hr=snow,
                    load_lb=load_lb,
                ).label
            )
        painted.append(
            {
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "risk_by_hour": labels,
            }
        )
    return painted


def _series_for(series_by_key: SeriesByPoint, lat: float, lon: float) -> HourlySeries | None:
    return series_by_key.get((round(lat, 2), round(lon, 2)))


def _parse_departure(value: str, timezone_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise TripError("Departure must be a date and time.") from exc
    if parsed.tzinfo is not None:
        return parsed
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise TripError("Could not resolve the origin timezone.") from exc
    return parsed.replace(tzinfo=zone)


def _same_place(origin: Place, destination: Place) -> bool:
    return haversine_miles(origin.lat, origin.lon, destination.lat, destination.lon) < 1


def _format_eta(moment: datetime) -> str:
    hour = moment.hour % 12 or 12
    suffix = "AM" if moment.hour < 12 else "PM"
    return f"{moment.strftime('%a')} {hour}:{moment.minute:02d} {suffix}"


def _round(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)

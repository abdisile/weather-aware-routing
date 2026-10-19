"""Geocoding, driving routes, and batched forecasts."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import requests

from routing.sampling import Step
from routing.weather import HourlySeries, parse_open_meteo

MILES_PER_METER = 1 / 1609.344
ORS_BASE = "https://api.openrouteservice.org"
OSRM_BASE = "https://router.project-osrm.org"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "spotter-truck-routing/1.0 (weather-aware truck routing assessment)"


class TripError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RawRoute:
    geometry: tuple[tuple[float, float], ...]
    steps: tuple[Step, ...]
    distance_miles: float
    duration_seconds: float
    via: str


@dataclass(frozen=True)
class RouteSet:
    routes: tuple[RawRoute, ...]
    provider: str
    profile: str


class MemoryCache:
    def __init__(self, ttl_seconds: float = 1800):
        self.ttl_seconds = ttl_seconds
        self._values: dict[tuple[float, float], tuple[float, HourlySeries]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple[float, float]) -> HourlySeries | None:
        with self._lock:
            item = self._values.get(key)
            if item is None:
                return None
            expires, value = item
            if expires < time.monotonic():
                del self._values[key]
                return None
            return value

    def set(self, key: tuple[float, float], value: HourlySeries) -> None:
        with self._lock:
            self._values[key] = (time.monotonic() + self.ttl_seconds, value)


class NominatimGeocoder:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def geocode(self, text: str) -> Place:
        response = self.session.get(
            NOMINATIM_URL,
            params={"q": text, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        _raise_for_status(response, "Geocoder")
        payload = response.json()
        if not payload:
            raise TripError(f'No place found for "{text}".')
        hit = payload[0]
        label = hit.get("display_name") or text
        return Place(label=label, lat=float(hit["lat"]), lon=float(hit["lon"]))


class OpenRouteService:
    def __init__(self, api_key: str, session: requests.Session | None = None):
        self.api_key = api_key
        self.session = session or requests.Session()

    def geocode(self, text: str) -> Place:
        response = self.session.get(
            f"{ORS_BASE}/geocode/search",
            params={"text": text, "size": 1},
            headers=self._headers(),
            timeout=20,
        )
        _raise_for_status(response, "OpenRouteService geocoder")
        features = response.json().get("features") or []
        if not features:
            raise TripError(f'No place found for "{text}".')
        feature = features[0]
        lon, lat = feature["geometry"]["coordinates"][:2]
        label = (feature.get("properties") or {}).get("label") or text
        return Place(label=label, lat=float(lat), lon=float(lon))

    def routes(self, origin: Place, destination: Place, load_lb: float) -> RouteSet:
        attempts = (
            ("driving-hgv", True),
            ("driving-hgv", False),
            ("driving-car", False),
        )
        last_error: TripError | None = None
        for profile, with_weight in attempts:
            try:
                return self._routes(origin, destination, load_lb, profile, with_weight)
            except TripError as exc:
                if exc.status in {401, 403}:
                    raise
                last_error = exc
        if last_error:
            raise last_error
        raise TripError("OpenRouteService did not return a route.", 502)

    def _routes(
        self,
        origin: Place,
        destination: Place,
        load_lb: float,
        profile: str,
        with_weight: bool,
    ) -> RouteSet:
        body: dict = {
            "coordinates": [
                [origin.lon, origin.lat],
                [destination.lon, destination.lat],
            ],
            "alternative_routes": {
                "target_count": 2,
                "share_factor": 0.6,
                "weight_factor": 1.4,
            },
            "units": "mi",
            "instructions": True,
        }
        if with_weight:
            tons = round(load_lb / 2204.6226218, 2)
            body["options"] = {"profile_params": {"restrictions": {"vehicle_weight": tons}}}
        response = self.session.post(
            f"{ORS_BASE}/v2/directions/{profile}/geojson",
            json=body,
            headers=self._headers(),
            timeout=30,
        )
        _raise_for_status(response, "OpenRouteService")
        features = response.json().get("features") or []
        routes = tuple(parse_ors_feature(feature) for feature in features[:3])
        if not routes:
            raise TripError("No driving route was found between those places.")
        return RouteSet(routes=routes, provider="openrouteservice", profile=profile)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self.api_key, "User-Agent": USER_AGENT}


class OsrmRouter:
    def __init__(self, session: requests.Session | None = None, base_url: str = OSRM_BASE):
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def routes(self, origin: Place, destination: Place, load_lb: float) -> RouteSet:
        del load_lb
        response = self.session.get(
            f"{self.base_url}/route/v1/driving/{origin.lon},{origin.lat};{destination.lon},{destination.lat}",
            params={
                "alternatives": "true",
                "overview": "full",
                "geometries": "geojson",
                "steps": "true",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        _raise_for_status(response, "Routing service")
        payload = response.json()
        if payload.get("code") not in {None, "Ok"}:
            raise TripError("No driving route was found between those places.")
        routes = tuple(parse_osrm_route(route) for route in (payload.get("routes") or [])[:3])
        if not routes:
            raise TripError("No driving route was found between those places.")
        return RouteSet(routes=routes, provider="osrm", profile="driving")


class OpenMeteo:
    def __init__(
        self,
        session: requests.Session | None = None,
        cache: MemoryCache | None = None,
    ):
        self.session = session or requests.Session()
        self.cache = cache or MemoryCache()

    def hourly_for(self, points: list[tuple[float, float]]) -> dict[tuple[float, float], HourlySeries]:
        unique: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for lat, lon in points:
            key = (round(lat, 2), round(lon, 2))
            if key in seen:
                continue
            seen.add(key)
            unique.append(key)

        missing = [key for key in unique if self.cache.get(key) is None]
        for chunk in _chunks(missing, 60):
            for key, series in self._fetch_chunk(chunk).items():
                self.cache.set(key, series)

        found: dict[tuple[float, float], HourlySeries] = {}
        for key in unique:
            series = self.cache.get(key)
            if series is not None:
                found[key] = series
        return found

    def _fetch_chunk(self, keys: list[tuple[float, float]]) -> dict[tuple[float, float], HourlySeries]:
        params = {
            "latitude": ",".join(str(lat) for lat, _lon in keys),
            "longitude": ",".join(str(lon) for _lat, lon in keys),
            "hourly": "wind_speed_10m,rain,snowfall",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_hours": 96,
        }
        last_error: requests.RequestException | None = None
        response = None
        for attempt in range(3):
            try:
                response = self.session.get(
                    OPEN_METEO_URL,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=(20, 45),
                )
                break
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(0.4 * (attempt + 1))
        if response is None:
            raise TripError("The weather service did not respond. Try the trip again.", 502) from last_error
        _raise_for_status(response, "Weather service")
        payload = response.json()
        items = payload if isinstance(payload, list) else [payload]
        if len(items) != len(keys):
            raise TripError("Weather service returned an unexpected number of locations.", 502)
        return {key: parse_open_meteo(item) for key, item in zip(keys, items)}


_SHARED_WEATHER = OpenMeteo()


class AppServices:
    """ORS when a key is configured, public OSRM otherwise.

    The forecast client is process-wide so repeated trips reuse the 30-minute cache.
    """

    def __init__(self, ors_api_key: str = "", session: requests.Session | None = None):
        self.ors = OpenRouteService(ors_api_key, session=session) if ors_api_key else None
        self.nominatim = NominatimGeocoder(session=session)
        self.osrm = OsrmRouter(session=session)
        self.weather = _SHARED_WEATHER

    def geocode(self, text: str) -> Place:
        if self.ors is not None:
            try:
                return self.ors.geocode(text)
            except TripError as exc:
                if exc.status in {401, 403}:
                    raise
        return self.nominatim.geocode(text)

    def routes(self, origin: Place, destination: Place, load_lb: float) -> RouteSet:
        if self.ors is not None:
            try:
                return self.ors.routes(origin, destination, load_lb)
            except TripError as exc:
                if exc.status in {401, 403}:
                    raise
        return self.osrm.routes(origin, destination, load_lb)


def parse_ors_feature(feature: dict) -> RawRoute:
    geometry = _geometry(feature.get("geometry") or {})
    properties = feature.get("properties") or {}
    summary = properties.get("summary") or {}
    steps: list[Step] = []
    for segment in properties.get("segments") or []:
        for step in segment.get("steps") or []:
            steps.append(
                Step(
                    distance_miles=float(step.get("distance") or 0),
                    duration_seconds=float(step.get("duration") or 0),
                    name=str(step.get("name") or ""),
                )
            )
    distance = float(summary.get("distance") or sum(step.distance_miles for step in steps))
    duration = float(summary.get("duration") or sum(step.duration_seconds for step in steps))
    return RawRoute(
        geometry=tuple(geometry),
        steps=tuple(steps),
        distance_miles=distance,
        duration_seconds=duration,
        via=via_label(steps),
    )


def parse_osrm_route(route: dict) -> RawRoute:
    geometry = _geometry(route.get("geometry") or {})
    steps: list[Step] = []
    for leg in route.get("legs") or []:
        for step in leg.get("steps") or []:
            steps.append(
                Step(
                    distance_miles=float(step.get("distance") or 0) * MILES_PER_METER,
                    duration_seconds=float(step.get("duration") or 0),
                    name=str(step.get("name") or ""),
                )
            )
    distance = float(route.get("distance") or 0) * MILES_PER_METER
    duration = float(route.get("duration") or 0)
    return RawRoute(
        geometry=tuple(geometry),
        steps=tuple(steps),
        distance_miles=distance,
        duration_seconds=duration,
        via=via_label(steps),
    )


def via_label(steps: list[Step]) -> str:
    ranked = sorted(steps, key=lambda step: step.distance_miles, reverse=True)
    names: list[str] = []
    for step in ranked:
        name = step.name.strip()
        if not name or name.lower() in {"-", "unnamed"}:
            continue
        if name not in names:
            names.append(name)
        if len(names) == 2:
            break
    return " · ".join(names)


def _geometry(geometry: dict) -> list[tuple[float, float]]:
    coordinates = geometry.get("coordinates") or []
    points: list[tuple[float, float]] = []
    for point in coordinates:
        if len(point) < 2:
            continue
        points.append((float(point[0]), float(point[1])))
    return points


def _chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _raise_for_status(response: requests.Response, service: str) -> None:
    if response.ok:
        return
    detail = ""
    try:
        payload = response.json()
        error = payload.get("error")
        if isinstance(error, dict):
            detail = error.get("message") or ""
        elif isinstance(error, str):
            detail = error
    except Exception:
        detail = ""
    message = f"{service} returned {response.status_code}."
    if detail:
        message = f"{message} {detail}"
    status = 502 if response.status_code >= 500 else response.status_code
    if response.status_code in {401, 403}:
        status = response.status_code
        message = f"{service} rejected the API key."
    raise TripError(message, status)

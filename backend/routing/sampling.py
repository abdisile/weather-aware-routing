"""Place weather samples along a driving geometry and clock them with step durations."""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_MILES = 3958.7613


@dataclass(frozen=True)
class Step:
    distance_miles: float
    duration_seconds: float
    name: str


@dataclass(frozen=True)
class SamplePoint:
    mile: float
    lat: float
    lon: float
    eta_offset_seconds: float


def sample_miles(total_miles: float, interval: float) -> list[float]:
    """Origin, every `interval` miles, and the destination."""
    if interval <= 0:
        raise ValueError("Sample interval must be positive.")
    total = max(0.0, total_miles)
    if total == 0:
        return [0.0]
    points = [0.0]
    mile = interval
    while mile < total - 1e-6:
        points.append(mile)
        mile += interval
    if points[-1] < total - 1e-6:
        points.append(total)
    return points


def cumulative_time(steps: list[Step]) -> list[tuple[float, float]]:
    """Return (miles, seconds) from the origin through the end of each step."""
    profile = [(0.0, 0.0)]
    miles = 0.0
    seconds = 0.0
    for step in steps:
        miles += max(0.0, step.distance_miles)
        seconds += max(0.0, step.duration_seconds)
        profile.append((miles, seconds))
    return profile


def eta_offset_at_mile(profile: list[tuple[float, float]], mile: float) -> float:
    if not profile:
        return 0.0
    if mile <= profile[0][0]:
        return profile[0][1]
    for (start_mile, start_time), (end_mile, end_time) in zip(profile, profile[1:]):
        if mile <= end_mile or end_mile == profile[-1][0]:
            span = end_mile - start_mile
            if span <= 0:
                return end_time
            fraction = min(1.0, max(0.0, (mile - start_mile) / span))
            return start_time + fraction * (end_time - start_time)
    return profile[-1][1]


def samples_along(
    coordinates: list[tuple[float, float]],
    target_miles: list[float],
    *,
    total_miles: float,
) -> list[tuple[float, float, float]]:
    """Interpolate (mile, lat, lon) at each target mile.

    `coordinates` are (lon, lat), GeoJSON order. Geometry length is scaled
    to `total_miles` so the samples match the routing engine's distance.
    """
    if not coordinates:
        raise ValueError("Route geometry is empty.")
    if len(coordinates) == 1 or total_miles <= 0:
        lon, lat = coordinates[0]
        return [(mile, lat, lon) for mile in target_miles]

    cumulative = [0.0]
    for start, end in zip(coordinates, coordinates[1:]):
        cumulative.append(cumulative[-1] + _haversine_miles(start, end))
    raw_total = cumulative[-1]
    if raw_total <= 0:
        lon, lat = coordinates[0]
        return [(mile, lat, lon) for mile in target_miles]

    scale = total_miles / raw_total
    scaled = [mile * scale for mile in cumulative]
    points: list[tuple[float, float, float]] = []
    cursor = 0
    for target in target_miles:
        while cursor < len(scaled) - 2 and scaled[cursor + 1] < target:
            cursor += 1
        start_mile = scaled[cursor]
        end_mile = scaled[min(cursor + 1, len(scaled) - 1)]
        start = coordinates[cursor]
        end = coordinates[min(cursor + 1, len(coordinates) - 1)]
        span = end_mile - start_mile
        fraction = 0.0 if span <= 0 else min(1.0, max(0.0, (target - start_mile) / span))
        lon = start[0] + fraction * (end[0] - start[0])
        lat = start[1] + fraction * (end[1] - start[1])
        points.append((target, lat, lon))
    return points


def build_samples(
    coordinates: list[tuple[float, float]],
    steps: list[Step],
    *,
    total_miles: float,
    total_seconds: float,
    interval: float,
) -> list[SamplePoint]:
    profile = cumulative_time(steps)
    if len(profile) == 1 or profile[-1][0] <= 0:
        profile = [(0.0, 0.0), (total_miles, total_seconds)]
    miles = sample_miles(total_miles, interval)
    located = samples_along(coordinates, miles, total_miles=total_miles)
    samples: list[SamplePoint] = []
    for mile, lat, lon in located:
        samples.append(
            SamplePoint(
                mile=mile,
                lat=lat,
                lon=lon,
                eta_offset_seconds=eta_offset_at_mile(profile, mile),
            )
        )
    return samples


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return _haversine_miles((lon1, lat1), (lon2, lat2))


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    y = math.sin(delta_lon) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def destination(lat: float, lon: float, bearing: float, distance_miles: float) -> tuple[float, float]:
    if distance_miles == 0:
        return lat, lon
    delta = distance_miles / EARTH_MILES
    theta = math.radians(bearing)
    phi1 = math.radians(lat)
    lambda1 = math.radians(lon)
    phi2 = math.asin(
        math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540.0) % 360.0 - 180.0


def _haversine_miles(start: tuple[float, float], end: tuple[float, float]) -> float:
    lon1, lat1 = start
    lon2, lat2 = end
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_MILES * math.asin(min(1.0, math.sqrt(a)))

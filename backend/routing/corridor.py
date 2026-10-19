"""Sample a band around the routes for the forecast heatmap."""

from __future__ import annotations

from routing.sampling import bearing_degrees, destination, haversine_miles


def corridor_points(
    geometries: list[list[tuple[float, float]]],
    *,
    spacing_miles: float = 30.0,
    offset_miles: float = 12.0,
    cap: int = 140,
) -> list[tuple[float, float]]:
    """Return (lat, lon) points along each route and to either side.

    `geometries` use GeoJSON (lon, lat) order. The cap keeps the weather
    request small enough that the first response stays interactive.
    """
    raw: list[tuple[float, float]] = []
    for coordinates in geometries:
        if not coordinates:
            continue
        anchors = _anchors(coordinates, spacing_miles)
        for index, (lon, lat) in enumerate(anchors):
            raw.append((lat, lon))
            neighbor = anchors[index + 1] if index + 1 < len(anchors) else anchors[index - 1]
            if neighbor == (lon, lat):
                continue
            heading = bearing_degrees(lat, lon, neighbor[1], neighbor[0])
            raw.append(destination(lat, lon, heading - 90, offset_miles))
            raw.append(destination(lat, lon, heading + 90, offset_miles))

    unique: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for lat, lon in raw:
        key = (round(lat, 2), round(lon, 2))
        if key in seen:
            continue
        seen.add(key)
        unique.append((lat, lon))

    if len(unique) <= cap:
        return unique
    stride = max(1, len(unique) // cap)
    trimmed = unique[::stride]
    return trimmed[:cap]


def _anchors(
    coordinates: list[tuple[float, float]],
    spacing_miles: float,
) -> list[tuple[float, float]]:
    anchors = [coordinates[0]]
    walked = 0.0
    next_mark = spacing_miles
    for start, end in zip(coordinates, coordinates[1:]):
        segment = haversine_miles(start[1], start[0], end[1], end[0])
        if segment <= 0:
            continue
        while walked + segment >= next_mark:
            fraction = (next_mark - walked) / segment
            lon = start[0] + fraction * (end[0] - start[0])
            lat = start[1] + fraction * (end[1] - start[1])
            anchors.append((lon, lat))
            next_mark += spacing_miles
        walked += segment
    if anchors[-1] != coordinates[-1]:
        anchors.append(coordinates[-1])
    return anchors

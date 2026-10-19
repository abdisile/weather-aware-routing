"""Weather and load risk for a truck route.

The rules match the assessment sheet. Shared band edges take the worse
class. A checkpoint is the worst condition present. A segment takes the
worse of its endpoints, and exposure is measured in miles.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4
    NO_TRAVEL = 5

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    RiskLevel.LOW: "low",
    RiskLevel.MODERATE: "moderate",
    RiskLevel.HIGH: "high",
    RiskLevel.SEVERE: "severe",
    RiskLevel.NO_TRAVEL: "no_travel",
}

LABEL_TO_LEVEL = {level.label: level for level in RiskLevel}


def classify_wind(mph: float, load_lb: float) -> tuple[RiskLevel, str]:
    shown = _fmt_number(mph)
    if mph >= 55:
        return RiskLevel.NO_TRAVEL, f"Wind {shown} mph is No Travel for any load"
    if mph >= 45:
        if load_lb > 30_000:
            return (
                RiskLevel.NO_TRAVEL,
                f"Wind {shown} mph with load over 30,000 lb is No Travel",
            )
        return RiskLevel.SEVERE, f"Wind {shown} mph"
    if mph >= 35:
        if load_lb > 40_000:
            return (
                RiskLevel.SEVERE,
                f"Wind {shown} mph with load over 40,000 lb is Severe",
            )
        return RiskLevel.HIGH, f"Wind {shown} mph"
    if mph >= 25:
        return RiskLevel.MODERATE, f"Wind {shown} mph"
    return RiskLevel.LOW, f"Wind {shown} mph"


def classify_rain(inches_per_hour: float) -> tuple[RiskLevel, str]:
    shown = _fmt_number(inches_per_hour)
    if inches_per_hour > 1.0:
        return RiskLevel.NO_TRAVEL, f"Rain {shown} in/hr"
    if inches_per_hour >= 0.50:
        return RiskLevel.SEVERE, f"Rain {shown} in/hr"
    if inches_per_hour >= 0.25:
        return RiskLevel.HIGH, f"Rain {shown} in/hr"
    if inches_per_hour >= 0.10:
        return RiskLevel.MODERATE, f"Rain {shown} in/hr"
    return RiskLevel.LOW, f"Rain {shown} in/hr"


def classify_snow(inches_per_hour: float) -> tuple[RiskLevel, str]:
    shown = _fmt_number(inches_per_hour)
    if inches_per_hour > 3.0:
        return RiskLevel.NO_TRAVEL, f"Snow {shown} in/hr"
    if inches_per_hour >= 2.0:
        return RiskLevel.SEVERE, f"Snow {shown} in/hr"
    if inches_per_hour >= 1.0:
        return RiskLevel.HIGH, f"Snow {shown} in/hr"
    if inches_per_hour >= 0.5:
        return RiskLevel.MODERATE, f"Snow {shown} in/hr"
    return RiskLevel.LOW, f"Snow {shown} in/hr"


@dataclass(frozen=True)
class CheckpointRisk:
    level: RiskLevel | None
    reasons: tuple[str, ...]

    @property
    def label(self) -> str:
        if self.level is None:
            return "unknown"
        return self.level.label


def score_checkpoint(
    *,
    wind_mph: float | None,
    rain_in_hr: float | None,
    snow_in_hr: float | None,
    load_lb: float,
) -> CheckpointRisk:
    """Score one sample. Any missing condition makes the checkpoint unknown."""
    if wind_mph is None or rain_in_hr is None or snow_in_hr is None:
        return CheckpointRisk(None, ("Forecast unavailable at this checkpoint",))

    scored = (
        classify_wind(wind_mph, load_lb),
        classify_rain(rain_in_hr),
        classify_snow(snow_in_hr),
    )
    level = max(item[0] for item in scored)
    reasons = tuple(reason for item_level, reason in scored if item_level == level)
    return CheckpointRisk(level, reasons)


@dataclass(frozen=True)
class Segment:
    miles: float
    level: RiskLevel | None

    @property
    def label(self) -> str:
        if self.level is None:
            return "unknown"
        return self.level.label


@dataclass(frozen=True)
class RouteScore:
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    unknown_miles: float
    scored_miles: float
    average_risk: float | None
    segments: tuple[Segment, ...]

    def sort_key(self, duration_seconds: float) -> tuple[float, ...]:
        # Unscored routes sort after every route that has weather.
        unscored = 0.0 if self.scored_miles > 0 else 1.0
        average = self.average_risk if self.average_risk is not None else 999.0
        return (
            unscored,
            self.no_travel_miles,
            self.severe_miles,
            self.high_miles,
            average,
            duration_seconds,
        )


def score_segments(samples: list[tuple[float, RiskLevel | None]]) -> RouteScore:
    """Turn cumulative-mile samples into mile exposure.

    `samples` is ordered (mile_from_origin, level). The mile value is the
    distance along the route, not a count of checkpoints.
    """
    if len(samples) < 2:
        return RouteScore(0, 0, 0, 0, 0, 0, 0, None, ())

    raw: list[Segment] = []
    for (start_mile, start_level), (end_mile, end_level) in zip(samples, samples[1:]):
        miles = max(0.0, end_mile - start_mile)
        if miles == 0:
            continue
        if start_level is None or end_level is None:
            level: RiskLevel | None = None
        else:
            level = max(start_level, end_level)
        raw.append(Segment(miles, level))

    merged = _merge_segments(raw)
    totals = {level: 0.0 for level in RiskLevel}
    unknown = 0.0
    weighted = 0.0
    scored = 0.0
    for segment in merged:
        if segment.level is None:
            unknown += segment.miles
            continue
        totals[segment.level] += segment.miles
        weighted += segment.miles * int(segment.level)
        scored += segment.miles

    average = weighted / scored if scored else None
    return RouteScore(
        no_travel_miles=totals[RiskLevel.NO_TRAVEL],
        severe_miles=totals[RiskLevel.SEVERE],
        high_miles=totals[RiskLevel.HIGH],
        moderate_miles=totals[RiskLevel.MODERATE],
        low_miles=totals[RiskLevel.LOW],
        unknown_miles=unknown,
        scored_miles=scored,
        average_risk=average,
        segments=tuple(merged),
    )


def _merge_segments(segments: list[Segment]) -> list[Segment]:
    merged: list[Segment] = []
    for segment in segments:
        if merged and merged[-1].level == segment.level:
            previous = merged[-1]
            merged[-1] = Segment(previous.miles + segment.miles, previous.level)
        else:
            merged.append(segment)
    return merged


@dataclass(frozen=True)
class RankedRoute:
    route_id: str
    name: str
    duration_seconds: float
    score: RouteScore


def rank_routes(routes: list[RankedRoute]) -> list[RankedRoute]:
    return sorted(routes, key=lambda route: route.score.sort_key(route.duration_seconds))


def rank_explanations(ranked: list[RankedRoute]) -> dict[str, str]:
    """Say, for each place, which ranking step separated it from its neighbor."""
    explanations: dict[str, str] = {}
    for index, route in enumerate(ranked):
        place = _place_label(index + 1)
        if index == 0 and len(ranked) == 1:
            text = f"{place}. This is the only route returned."
        elif index == 0:
            rival = ranked[1]
            text = f"{place}. {_placed_against(route, rival, ahead=True)}"
        else:
            text = f"{place}. {_placed_against(route, ranked[index - 1], ahead=False)}"
        explanations[route.route_id] = text
    return explanations


def _placed_against(route: RankedRoute, other: RankedRoute, *, ahead: bool) -> str:
    matched, better_phrase, worse_phrase, decided_on_time = _decision(route if ahead else other, other if ahead else route)
    phrase = better_phrase if ahead else worse_phrase
    relation = "Ahead of" if ahead else "Behind"
    sentence = f"{relation} {other.name} on {phrase}."
    if matched:
        sentence = f"{sentence} Same {_human_join(matched)}."
    if not decided_on_time:
        sentence = f"{sentence}{_time_aside(route, other)}"
    if route.score.unknown_miles > 0.05:
        sentence = (
            f"{sentence} {format_miles(route.score.unknown_miles)} miles had no forecast "
            "and were left out."
        )
    return sentence


def _decision(better: RankedRoute, worse: RankedRoute) -> tuple[list[str], str, str, bool]:
    """Matched steps, then why `better` is ahead and why `worse` is behind."""
    if better.score.scored_miles > 0 and worse.score.scored_miles <= 0:
        return [], "having scored weather", "having no scored weather", False
    matched: list[str] = []
    steps = (
        ("no-travel miles", better.score.no_travel_miles, worse.score.no_travel_miles),
        ("severe miles", better.score.severe_miles, worse.score.severe_miles),
        ("high miles", better.score.high_miles, worse.score.high_miles),
    )
    for label, won, lost in steps:
        if abs(won - lost) <= 1e-6:
            matched.append(label)
            continue
        return (
            matched,
            f"fewer {label} ({format_miles(won)} vs {format_miles(lost)})",
            f"more {label} ({format_miles(lost)} vs {format_miles(won)})",
            False,
        )
    won_avg = better.score.average_risk
    lost_avg = worse.score.average_risk
    if won_avg is not None and lost_avg is not None and abs(won_avg - lost_avg) > 1e-6:
        return (
            matched,
            f"lower average risk ({won_avg:.2f} vs {lost_avg:.2f})",
            f"higher average risk ({lost_avg:.2f} vs {won_avg:.2f})",
            False,
        )
    if won_avg is not None and lost_avg is not None:
        matched.append("average risk")
    gap = abs(worse.duration_seconds - better.duration_seconds)
    if gap >= 30:
        words = format_duration_words(gap)
        return matched, f"a shorter drive ({words})", f"a longer drive ({words})", True
    return matched, "an equal score", "an equal score", True


def _time_aside(route: RankedRoute, other: RankedRoute) -> str:
    gap = route.duration_seconds - other.duration_seconds
    if abs(gap) < 30:
        return ""
    words = format_duration_words(abs(gap))
    if gap > 0:
        return f" The drive is {words} longer."
    return f" The drive is {words} shorter."


def _human_join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _place_label(place: int) -> str:
    labels = {1: "1st", 2: "2nd", 3: "3rd"}
    return labels.get(place, f"{place}th")


def recommendation_reason(ranked: list[RankedRoute]) -> str:
    if not ranked:
        return "No routes were returned."
    winner = ranked[0]
    if len(ranked) == 1:
        return f"{winner.name} is the only route returned."

    rival = ranked[1]
    if winner.score.scored_miles <= 0 and rival.score.scored_miles <= 0:
        text = (
            "Forecast data did not cover these routes, so the shortest trip is shown."
        )
        return _with_unknown_note(text, winner)

    if winner.score.scored_miles > 0 and rival.score.scored_miles <= 0:
        text = (
            f"{winner.name} has weather along the trip. "
            f"{rival.name} does not, so it was left unscored."
        )
        return _with_unknown_note(text, winner)

    text = _first_difference(winner, rival)
    if _risk_tuple(winner) == _risk_tuple(rival) and winner.duration_seconds < rival.duration_seconds:
        text = (
            f"Risk matches {rival.name}. {winner.name} is shorter by "
            f"{format_duration_words(rival.duration_seconds - winner.duration_seconds)}."
        )
    elif _risk_tuple(winner) != _risk_tuple(rival) and winner.duration_seconds > rival.duration_seconds:
        text = (
            f"{text} It takes "
            f"{format_duration_words(winner.duration_seconds - rival.duration_seconds)} longer."
        )

    if winner.score.no_travel_miles > 0 and rival.score.no_travel_miles > 0:
        text = f"No route is clear. {text}"
    return _with_unknown_note(text, winner)


def _first_difference(winner: RankedRoute, rival: RankedRoute) -> str:
    pairs = (
        ("no-travel", winner.score.no_travel_miles, rival.score.no_travel_miles),
        ("severe", winner.score.severe_miles, rival.score.severe_miles),
        ("high", winner.score.high_miles, rival.score.high_miles),
    )
    for label, won, lost in pairs:
        if abs(won - lost) > 1e-6:
            return (
                f"{winner.name} has {format_miles(won)} {label} miles. "
                f"{rival.name} has {format_miles(lost)}."
            )
    if winner.score.average_risk is not None and rival.score.average_risk is not None:
        if abs(winner.score.average_risk - rival.score.average_risk) > 1e-6:
            return (
                f"{winner.name} has a lower average risk "
                f"({winner.score.average_risk:.2f} vs {rival.score.average_risk:.2f})."
            )
    return f"{winner.name} and {rival.name} score the same on weather."


def _risk_tuple(route: RankedRoute) -> tuple[float, ...]:
    average = route.score.average_risk if route.score.average_risk is not None else 999.0
    return (
        route.score.no_travel_miles,
        route.score.severe_miles,
        route.score.high_miles,
        round(average, 4),
    )


def _with_unknown_note(text: str, winner: RankedRoute) -> str:
    if winner.score.unknown_miles <= 0.05:
        return text
    return (
        f"{text} {format_miles(winner.score.unknown_miles)} miles had no forecast "
        "and were left out of the score."
    )


def format_miles(miles: float) -> str:
    rounded = round(miles, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


def format_duration_words(seconds: float) -> str:
    minutes = max(1, int(round(seconds / 60))) if seconds >= 30 else 0
    if minutes == 0:
        return "under a minute"
    hours, mins = divmod(minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    if mins:
        parts.append(f"{mins} minute" if mins == 1 else f"{mins} minutes")
    return " ".join(parts)


def format_clock(seconds: float) -> str:
    minutes = int(round(seconds / 60))
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} hr {mins} min"
    if hours:
        return f"{hours} hr"
    return f"{mins} min"


def _fmt_number(value: float) -> str:
    rounded = round(value, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.1f}"

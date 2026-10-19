import pytest

from routing.risk import (
    RankedRoute,
    RiskLevel,
    classify_rain,
    classify_snow,
    classify_wind,
    rank_explanations,
    rank_routes,
    recommendation_reason,
    score_checkpoint,
    score_segments,
)


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        (24.9, RiskLevel.LOW),
        (25, RiskLevel.MODERATE),
        (34.9, RiskLevel.MODERATE),
        (35, RiskLevel.HIGH),
        (44.9, RiskLevel.HIGH),
        (45, RiskLevel.SEVERE),
        (54.9, RiskLevel.SEVERE),
        (55, RiskLevel.NO_TRAVEL),
    ],
)
def test_wind_bands_at_a_light_load(mph, expected):
    level, _reason = classify_wind(mph, load_lb=10_000)
    assert level is expected


def test_load_upgrades_wind_only_above_the_printed_cutovers():
    severe, _ = classify_wind(46, load_lb=30_000)
    blocked, blocked_reason = classify_wind(46, load_lb=30_001)
    high, _ = classify_wind(36, load_lb=40_000)
    upgraded, upgraded_reason = classify_wind(36, load_lb=40_001)
    any_load, any_reason = classify_wind(55, load_lb=10_000)

    assert severe is RiskLevel.SEVERE
    assert blocked is RiskLevel.NO_TRAVEL
    assert "30,000" in blocked_reason
    assert high is RiskLevel.HIGH
    assert upgraded is RiskLevel.SEVERE
    assert "40,000" in upgraded_reason
    assert any_load is RiskLevel.NO_TRAVEL
    assert "any load" in any_reason


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0.09, RiskLevel.LOW),
        (0.10, RiskLevel.MODERATE),
        (0.25, RiskLevel.HIGH),
        (0.50, RiskLevel.SEVERE),
        (1.00, RiskLevel.SEVERE),
        (1.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_rain_bands(amount, expected):
    level, _reason = classify_rain(amount)
    assert level is expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0.49, RiskLevel.LOW),
        (0.5, RiskLevel.MODERATE),
        (1.0, RiskLevel.HIGH),
        (2.0, RiskLevel.SEVERE),
        (3.0, RiskLevel.SEVERE),
        (3.1, RiskLevel.NO_TRAVEL),
    ],
)
def test_snow_bands(amount, expected):
    level, _reason = classify_snow(amount)
    assert level is expected


def test_checkpoint_uses_the_worst_condition():
    risk = score_checkpoint(wind_mph=55, rain_in_hr=0.01, snow_in_hr=0, load_lb=10_000)
    assert risk.level is RiskLevel.NO_TRAVEL
    assert any("Wind" in reason for reason in risk.reasons)
    assert not any(reason.startswith("Rain") for reason in risk.reasons)


def test_missing_forecast_is_unknown_rather_than_calm():
    risk = score_checkpoint(wind_mph=None, rain_in_hr=0, snow_in_hr=0, load_lb=10_000)
    assert risk.level is None
    assert risk.label == "unknown"


def test_exposure_is_miles_not_checkpoint_count():
    long_severe = score_segments([(0, RiskLevel.SEVERE), (50, RiskLevel.SEVERE)])
    short_severe = score_segments(
        [
            (0, RiskLevel.SEVERE),
            (2, RiskLevel.SEVERE),
            (4, RiskLevel.SEVERE),
            (6, RiskLevel.SEVERE),
            (8, RiskLevel.SEVERE),
            (10, RiskLevel.SEVERE),
        ]
    )
    assert long_severe.severe_miles == pytest.approx(50)
    assert short_severe.severe_miles == pytest.approx(10)
    ranked = rank_routes(
        [
            RankedRoute("long", "Long", 3_600, long_severe),
            RankedRoute("short", "Short", 7_200, short_severe),
        ]
    )
    assert ranked[0].route_id == "short"


def test_segment_takes_the_worse_endpoint_and_weights_the_average_by_miles():
    score = score_segments(
        [
            (0, RiskLevel.LOW),
            (10, RiskLevel.LOW),
            (20, RiskLevel.SEVERE),
        ]
    )
    assert score.low_miles == pytest.approx(10)
    assert score.severe_miles == pytest.approx(10)
    assert score.average_risk == pytest.approx(2.5)


def test_unknown_miles_stay_out_of_the_average():
    score = score_segments(
        [
            (0, RiskLevel.LOW),
            (10, RiskLevel.LOW),
            (30, None),
        ]
    )
    assert score.low_miles == pytest.approx(10)
    assert score.unknown_miles == pytest.approx(20)
    assert score.average_risk == pytest.approx(1)


def test_no_travel_outranks_severe_miles():
    clear_of_block = score_segments([(0, RiskLevel.SEVERE), (40, RiskLevel.SEVERE)])
    blocked = score_segments([(0, RiskLevel.NO_TRAVEL), (5, RiskLevel.NO_TRAVEL)])
    ranked = rank_routes(
        [
            RankedRoute("blocked", "Blocked", 1_000, blocked),
            RankedRoute("severe", "Severe", 9_000, clear_of_block),
        ]
    )
    assert ranked[0].route_id == "severe"


def test_equal_risk_breaks_the_tie_on_travel_time():
    calm = score_segments([(0, RiskLevel.LOW), (10, RiskLevel.LOW)])
    ranked = rank_routes(
        [
            RankedRoute("slow", "Slow", 7_200, calm),
            RankedRoute("fast", "Fast", 3_600, calm),
        ]
    )
    assert ranked[0].route_id == "fast"
    reason = recommendation_reason(ranked)
    assert "shorter" in reason
    assert "Fast" in reason


def test_heavy_load_can_flip_the_winner_when_high_becomes_severe():
    """40 mph over 40 miles is only High under 40,000 lb.

    The same stretch becomes Severe above that load, and then loses to a
    shorter Severe snow exposure.
    """
    windy = score_segments([(0, RiskLevel.HIGH), (40, RiskLevel.HIGH)])
    snowy = score_segments([(0, RiskLevel.SEVERE), (15, RiskLevel.SEVERE)])
    light = rank_routes(
        [
            RankedRoute("windy", "Windy", 18_000, windy),
            RankedRoute("snowy", "Snowy", 21_600, snowy),
        ]
    )
    assert light[0].route_id == "windy"

    windy_heavy = score_segments([(0, RiskLevel.SEVERE), (40, RiskLevel.SEVERE)])
    heavy = rank_routes(
        [
            RankedRoute("windy", "Windy", 18_000, windy_heavy),
            RankedRoute("snowy", "Snowy", 21_600, snowy),
        ]
    )
    assert heavy[0].route_id == "snowy"
    reason = recommendation_reason(heavy)
    assert "No route is clear" not in reason
    assert "15 severe miles" in reason
    assert "40" in reason


def test_reason_says_when_no_route_is_clear():
    blocked = score_segments([(0, RiskLevel.NO_TRAVEL), (8, RiskLevel.NO_TRAVEL)])
    worse = score_segments([(0, RiskLevel.NO_TRAVEL), (20, RiskLevel.NO_TRAVEL)])
    ranked = rank_routes(
        [
            RankedRoute("worse", "Worse", 1_000, worse),
            RankedRoute("less", "Less", 2_000, blocked),
        ]
    )
    reason = recommendation_reason(ranked)
    assert reason.startswith("No route is clear.")
    assert "Less" in reason


def test_each_place_explains_the_step_that_separated_it():
    calm = score_segments([(0, RiskLevel.LOW), (10, RiskLevel.LOW)])
    ranked = rank_routes(
        [
            RankedRoute("slow", "Slow", 7_200, calm),
            RankedRoute("fast", "Fast", 3_600, calm),
        ]
    )
    notes = rank_explanations(ranked)
    assert notes["fast"].startswith("1st.")
    assert "shorter drive" in notes["fast"]
    assert "Same" in notes["fast"]
    assert "longer drive" in notes["slow"]

    windy = score_segments([(0, RiskLevel.SEVERE), (40, RiskLevel.SEVERE)])
    snowy = score_segments([(0, RiskLevel.SEVERE), (15, RiskLevel.SEVERE)])
    heavy = rank_routes(
        [
            RankedRoute("windy", "Windy", 18_000, windy),
            RankedRoute("snowy", "Snowy", 21_600, snowy),
        ]
    )
    notes = rank_explanations(heavy)
    assert "fewer severe miles (15 vs 40)" in notes["snowy"]
    assert "longer" in notes["snowy"]
    assert "more severe miles (40 vs 15)" in notes["windy"]
    assert "shorter" in notes["windy"]

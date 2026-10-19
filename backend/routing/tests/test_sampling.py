import pytest

from routing.corridor import corridor_points
from routing.sampling import Step, build_samples, eta_offset_at_mile, haversine_miles, sample_miles


def test_sample_miles_include_the_ends_and_stop_at_the_destination():
    assert sample_miles(80, 50) == [0, 50, 80]
    assert sample_miles(50, 50) == [0, 50]
    assert sample_miles(10, 25) == [0, 10]


def test_eta_follows_step_duration_instead_of_one_speed_for_the_whole_trip():
    profile = [(0, 0), (10, 3_600), (40, 7_200)]
    assert eta_offset_at_mile(profile, 0) == 0
    assert eta_offset_at_mile(profile, 10) == pytest.approx(3_600)
    assert eta_offset_at_mile(profile, 25) == pytest.approx(5_400)


def test_halfway_checkpoint_on_a_four_hour_route_is_two_hours_in():
    start = (-96.0, 32.0)
    end = (-96.0, 33.0)
    miles = haversine_miles(32.0, -96.0, 33.0, -96.0)
    samples = build_samples(
        [start, end],
        [Step(miles, 4 * 3_600, "I-35")],
        total_miles=miles,
        total_seconds=4 * 3_600,
        interval=miles / 2,
    )
    assert len(samples) == 3
    assert samples[1].mile == pytest.approx(miles / 2)
    assert samples[1].eta_offset_seconds == pytest.approx(2 * 3_600)
    assert samples[1].lat == pytest.approx(32.5, abs=0.02)
    assert samples[-1].mile == pytest.approx(miles)


def test_corridor_offsets_sit_about_twelve_miles_off_the_line():
    geometry = [(-96.0, 32.0), (-96.0, 33.0)]
    points = corridor_points([geometry], spacing_miles=40, offset_miles=12, cap=250)
    center = (32.0, -96.0)
    distances = [haversine_miles(center[0], center[1], lat, lon) for lat, lon in points]
    assert any(distance == pytest.approx(12, abs=0.4) for distance in distances)
    assert len(points) <= 250

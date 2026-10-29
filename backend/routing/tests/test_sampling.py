"""Unit tests for sampling + ETA. Pure — no Django, no network."""
from datetime import datetime, timedelta, timezone

import pytest

from routing.core.sampling import Checkpoint, eta_at, haversine_mi, walk_polyline


def test_haversine_known_distance():
    # ~ NYC (40.7128,-74.0060) to Philadelphia (39.9526,-75.1652) ~ 80 miles.
    d = haversine_mi(40.7128, -74.0060, 39.9526, -75.1652)
    assert 78 < d < 84


def test_walk_places_marks_every_interval():
    # A straight east-west leg long enough for several marks.
    pts = [(40.0, -100.0), (40.0, -98.0)]  # ~106 miles at this latitude
    cps, total = walk_polyline(pts, interval_mi=25)
    miles = [round(c.mile) for c in cps]
    assert miles[0] == 0                      # origin
    assert 25 in miles and 50 in miles and 75 in miles
    assert cps[-1].mile == pytest.approx(total, abs=1e-2)  # destination included
    assert total > 100


def test_segment_miles_sum_to_total():
    pts = [(39.0, -104.9), (39.1, -100.0), (39.1, -94.6)]
    cps, total = walk_polyline(pts, interval_mi=10)
    assert sum(c.segment_mi for c in cps) == pytest.approx(total, abs=0.05)


def test_eta_is_proportional_to_distance():
    dep = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    # Halfway along a 4-hour trip -> +2h.
    arr = eta_at(dep, mile=50, total_mi=100, total_duration_s=4 * 3600)
    assert arr == dep + timedelta(hours=2)


def test_eta_monotonic_increasing():
    dep = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    etas = [eta_at(dep, m, 100, 3600) for m in (0, 25, 50, 75, 100)]
    assert etas == sorted(etas)


def test_walk_rejects_degenerate_input():
    with pytest.raises(ValueError):
        walk_polyline([(0.0, 0.0)], interval_mi=10)
    with pytest.raises(ValueError):
        walk_polyline([(0.0, 0.0), (1.0, 1.0)], interval_mi=0)

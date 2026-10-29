"""Unit tests for the risk engine. Pure — no Django, no network."""
from routing.core.risk import (
    Risk,
    aggregate_route,
    classify_checkpoint,
    classify_rain,
    classify_snow,
    classify_wind,
    recommend,
)


# --- Band boundaries ------------------------------------------------------------

def test_wind_bands():
    assert classify_wind(0) == Risk.LOW
    assert classify_wind(24.9) == Risk.LOW
    assert classify_wind(25) == Risk.MODERATE
    assert classify_wind(34) == Risk.MODERATE
    assert classify_wind(35) == Risk.HIGH
    assert classify_wind(44) == Risk.HIGH
    assert classify_wind(45) == Risk.SEVERE
    assert classify_wind(54) == Risk.SEVERE
    assert classify_wind(54.9) == Risk.SEVERE  # closes the 54->55 gap
    assert classify_wind(55) == Risk.NO_TRAVEL


def test_rain_bands():
    assert classify_rain(0.09) == Risk.LOW
    assert classify_rain(0.10) == Risk.MODERATE
    assert classify_rain(0.25) == Risk.HIGH
    assert classify_rain(0.50) == Risk.SEVERE
    assert classify_rain(1.00) == Risk.SEVERE   # 1.00 is still Severe
    assert classify_rain(1.01) == Risk.NO_TRAVEL


def test_snow_bands():
    assert classify_snow(0.49) == Risk.LOW
    assert classify_snow(0.5) == Risk.MODERATE
    assert classify_snow(1.0) == Risk.HIGH
    assert classify_snow(2.0) == Risk.SEVERE
    assert classify_snow(3.0) == Risk.SEVERE    # 3.0 is still Severe
    assert classify_snow(3.1) == Risk.NO_TRAVEL


# --- Worst-of-three + load overrides -------------------------------------------

def test_worst_of_three_wins():
    r = classify_checkpoint(wind_mph=10, rain_in=0.30, snow_in=0.0, load_lb=10_000)
    assert r.level == Risk.HIGH  # rain drives it


def test_load_escalates_high_to_severe():
    # 38 mph wind (High) + 45,000 lb -> Severe
    r = classify_checkpoint(wind_mph=38, rain_in=0, snow_in=0, load_lb=45_000)
    assert r.level == Risk.SEVERE
    assert any("Load" in reason for reason in r.reasons)


def test_no_escalation_under_weight_threshold():
    # 38 mph wind (High) + 40,000 lb (not > 40k) -> stays High
    r = classify_checkpoint(wind_mph=38, rain_in=0, snow_in=0, load_lb=40_000)
    assert r.level == Risk.HIGH


def test_load_escalates_severe_to_no_travel():
    # 48 mph wind (Severe) + 31,000 lb (> 30k) -> No Travel
    r = classify_checkpoint(wind_mph=48, rain_in=0, snow_in=0, load_lb=31_000)
    assert r.level == Risk.NO_TRAVEL


def test_severe_stays_severe_under_weight():
    r = classify_checkpoint(wind_mph=48, rain_in=0, snow_in=0, load_lb=30_000)
    assert r.level == Risk.SEVERE


def test_extreme_wind_is_no_travel_any_load():
    r = classify_checkpoint(wind_mph=60, rain_in=0, snow_in=0, load_lb=0)
    assert r.level == Risk.NO_TRAVEL


def test_base_can_exceed_load_override():
    # Severe rain + low wind: load override (Low) must not downgrade the Severe base.
    r = classify_checkpoint(wind_mph=10, rain_in=0.6, snow_in=0, load_lb=50_000)
    assert r.level == Risk.SEVERE


# --- Aggregation + recommendation ----------------------------------------------

def test_aggregate_counts_miles_by_level():
    s = aggregate_route(
        [(Risk.LOW, 10), (Risk.HIGH, 10), (Risk.SEVERE, 10), (Risk.NO_TRAVEL, 10)],
        duration_min=120,
    )
    assert s.severe_miles == 10
    assert s.high_miles == 10
    assert s.no_travel_miles == 10
    assert s.has_no_travel is True


def test_recommend_prefers_fewest_severe_miles():
    a = aggregate_route([(Risk.SEVERE, 30)], duration_min=60)   # 30 severe
    b = aggregate_route([(Risk.SEVERE, 10)], duration_min=90)   # 10 severe, slower
    idx, why = recommend([a, b])
    assert idx == 1
    assert "Severe" in why


def test_recommend_breaks_ties_on_duration():
    a = aggregate_route([(Risk.LOW, 100)], duration_min=120)
    b = aggregate_route([(Risk.LOW, 100)], duration_min=90)
    idx, why = recommend([a, b])
    assert idx == 1
    assert "travel time" in why


def test_recommend_avoids_no_travel_routes():
    a = aggregate_route([(Risk.NO_TRAVEL, 5), (Risk.LOW, 95)], duration_min=60)
    b = aggregate_route([(Risk.HIGH, 50), (Risk.LOW, 50)], duration_min=200)
    idx, why = recommend([a, b])
    assert idx == 1  # pick the slower, higher-risk route over one with a No-Travel segment
    assert "No-Travel" in why

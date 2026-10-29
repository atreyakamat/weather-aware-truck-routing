"""Integration test for POST /api/plan with HERE + Open-Meteo mocked."""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import flexpolyline
import responses
from rest_framework.test import APIClient

from routing.services import here, weather

DEPARTURE = "2026-10-30T08:00:00+00:00"

# Denver-ish -> Kansas City-ish, ~550 mi apart.
ORIGIN = (39.00, -104.90)
DEST = (39.10, -94.60)


def _line(a, b, n=25):
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def _geocode_cb(request):
    q = parse_qs(urlparse(request.url).query)["q"][0].lower()
    lat, lng = DEST if "kansas" in q or "kc" in q else ORIGIN
    body = {"items": [{"position": {"lat": lat, "lng": lng}}]}
    import json
    return (200, {}, json.dumps(body))


def _routes_cb(request):
    import json
    poly = flexpolyline.encode(_line(ORIGIN, DEST))
    meters = 550 * 1609.344
    routes = [
        {"sections": [{"polyline": poly, "summary": {"length": meters, "duration": 9 * 3600}}]},
        {"sections": [{"polyline": poly, "summary": {"length": meters, "duration": 8 * 3600}}]},
    ]
    return (200, {}, json.dumps({"routes": routes}))


def _weather_cb(request):
    import json
    qs = parse_qs(urlparse(request.url).query)
    n = len(qs["latitude"][0].split(","))
    base = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc)
    times = [(base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(96)]
    block = {
        "hourly_units": {"rain": "inch", "snowfall": "cm", "wind_speed_10m": "mph"},
        "hourly": {
            "time": times,
            "wind_speed_10m": [12.0] * len(times),
            "wind_gusts_10m": [18.0] * len(times),
            "rain": [0.0] * len(times),
            "snowfall": [0.0] * len(times),
        },
    }
    payload = [block for _ in range(n)]  # one block per requested coordinate
    return (200, {}, json.dumps(payload))


@responses.activate
def test_plan_happy_path(settings):
    settings.HERE_API_KEY = "test-key"
    responses.add_callback(responses.GET, here.GEOCODE_URL, callback=_geocode_cb, content_type="application/json")
    responses.add_callback(responses.GET, here.ROUTES_URL, callback=_routes_cb, content_type="application/json")
    responses.add_callback(responses.GET, weather.FORECAST_URL, callback=_weather_cb, content_type="application/json")

    client = APIClient()
    resp = client.post("/api/plan", {
        "origin": "Denver, CO",
        "destination": "Kansas City, MO",
        "departure": DEPARTURE,
        "load_weight_lb": 42000,
        "sample_interval_miles": 25,
    }, format="json")

    assert resp.status_code == 200, resp.content
    body = resp.json()

    # Three-ish routes (HERE mock returns 2; both present).
    assert len(body["routes"]) == 2
    route = body["routes"][0]

    # Checkpoints spaced ~25 mi with monotonically increasing ETAs.
    miles = [c["mile"] for c in route["checkpoints"]]
    assert miles[0] == 0.0
    assert miles == sorted(miles)
    etas = [c["eta"] for c in route["checkpoints"]]
    assert etas == sorted(etas)

    # Recommendation is valid and, with equal (low) risk, picks the faster route.
    assert body["recommended_id"] in (0, 1)
    assert body["recommended_id"] == 1  # route 1 is 8h vs 9h
    assert "travel time" in body["deciding_criterion"]

    # Corridor heatmap: 0..48 inclusive, one risk value per corridor point.
    assert len(body["corridor"]["hours"]) == 49
    pts = body["corridor"]["points"]
    assert all(len(h["risk_by_point"]) == len(pts) for h in body["corridor"]["hours"])


@responses.activate
def test_plan_validation_error():
    client = APIClient()
    resp = client.post("/api/plan", {"origin": "A"}, format="json")
    assert resp.status_code == 400
    assert "destination" in resp.json()

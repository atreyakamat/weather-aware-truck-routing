"""POST /api/plan — orchestrates geocode -> routes -> sampling -> weather -> risk.

Keeps HTTP/JSON concerns here; all domain logic lives in routing.core (pure) and
routing.services (I/O). The HERE key never leaves the server.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import requests
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.conf import settings

from routing.core import risk as risk_mod
from routing.core.risk import LABELS, Risk
from routing.core.sampling import eta_at, walk_polyline
from routing.services import demo, here, weather
from .serializers import PlanRequestSerializer

HEATMAP_HOURS = 48  # 0..48 inclusive forecast slider


@api_view(["GET"])
def health(_request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan(request):
    serializer = PlanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data

    departure: datetime = data["departure"]
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)
    load_lb = data["load_weight_lb"]
    interval = data["sample_interval_miles"]

    use_demo = bool(request.data.get("demo")) or not settings.HERE_API_KEY
    try:
        if use_demo:
            origin = demo.geocode(data["origin"])
            destination = demo.geocode(data["destination"])
            here_routes = demo.demo_routes(origin, destination)
        else:
            origin = here.geocode(data["origin"])
            destination = here.geocode(data["destination"])
            here_routes = here.truck_routes(origin, destination, departure.isoformat())
    except (here.HereError, ValueError, requests.RequestException) as exc:
        return Response({"detail": f"routing failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

    # Sample each route into checkpoints.
    sampled = []  # list of (here.Route, checkpoints, total_mi)
    all_points: list[tuple[float, float]] = []
    for route in here_routes:
        checkpoints, total_mi = walk_polyline(route.polyline, interval)
        sampled.append((route, checkpoints, total_mi))
        all_points.extend((c.lat, c.lon) for c in checkpoints)

    # One weather fetch covering every checkpoint of every route.
    forecast_days = _forecast_days(departure)
    try:
        wx = weather.fetch(all_points, forecast_days=forecast_days)
    except requests.RequestException as exc:
        return Response({"detail": f"weather failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

    routes_out = []
    scores: list[risk_mod.RouteScore] = []
    for idx, (route, checkpoints, total_mi) in enumerate(sampled):
        cp_out = []
        levels_and_miles: list[tuple[Risk, float]] = []
        for c in checkpoints:
            series = weather.series_for(wx, c.lat, c.lon)
            arrival = eta_at(departure, c.mile, total_mi, route.duration_s)
            w, r, s = series.nearest(arrival)
            cr = risk_mod.classify_checkpoint(w, r, s, load_lb)
            levels_and_miles.append((cr.level, c.segment_mi))
            cp_out.append({
                "seq": c.seq,
                "lat": round(c.lat, 5),
                "lon": round(c.lon, 5),
                "mile": c.mile,
                "eta": arrival.isoformat(),
                "wind_mph": round(w, 1),
                "rain_in": round(r, 3),
                "snow_in": round(s, 3),
                "level": int(cr.level),
                "level_label": LABELS[cr.level],
                "reasons": cr.reasons,
            })
        score = risk_mod.aggregate_route(levels_and_miles, route.duration_s / 60.0)
        scores.append(score)
        routes_out.append({
            "id": idx,
            "label": route.label,
            "distance_mi": round(route.distance_mi, 1),
            "duration_min": round(route.duration_s / 60.0, 1),
            "geometry": [[round(lat, 5), round(lon, 5)] for lat, lon in route.polyline],
            "severe_miles": score.severe_miles,
            "high_miles": score.high_miles,
            "no_travel_miles": score.no_travel_miles,
            "avg_risk": score.avg_risk,
            "has_no_travel": score.has_no_travel,
            "checkpoints": cp_out,
        })

    recommended_id, criterion = risk_mod.recommend(scores)

    corridor = _build_corridor(sampled[recommended_id], wx, departure, load_lb)

    return Response({
        "recommended_id": recommended_id,
        "deciding_criterion": criterion,
        "demo_mode": use_demo,
        "origin": {"query": data["origin"], "lat": origin[0], "lon": origin[1]},
        "destination": {"query": data["destination"], "lat": destination[0], "lon": destination[1]},
        "departure": departure.isoformat(),
        "load_weight_lb": load_lb,
        "sample_interval_miles": interval,
        "routes": routes_out,
        "corridor": corridor,
    })


def _forecast_days(departure: datetime) -> int:
    """Enough days to cover departure + 48h of slider, capped at Open-Meteo's max (16)."""
    now = datetime.now(timezone.utc)
    end = departure + timedelta(hours=HEATMAP_HOURS)
    span_days = math.ceil((end - now).total_seconds() / 86400) + 1
    return max(1, min(16, span_days))


def _build_corridor(sampled_route, wx, departure: datetime, load_lb: float) -> dict:
    """Precompute 0..48h risk for the recommended route's checkpoints (heatmap slider)."""
    _route, checkpoints, _total = sampled_route
    points = [[round(c.lat, 5), round(c.lon, 5)] for c in checkpoints]
    hours = []
    for h in range(HEATMAP_HOURS + 1):
        when = departure + timedelta(hours=h)
        risk_by_point = []
        for c in checkpoints:
            series = weather.series_for(wx, c.lat, c.lon)
            w, r, s = series.nearest(when)
            cr = risk_mod.classify_checkpoint(w, r, s, load_lb)
            risk_by_point.append(int(cr.level))
        hours.append({"offset": h, "iso": when.isoformat(), "risk_by_point": risk_by_point})
    return {"points": points, "hours": hours}

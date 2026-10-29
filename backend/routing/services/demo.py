"""Keyless demo/fallback provider.

Used when HERE_API_KEY is not configured (or the request sets "demo": true) so the
app runs end-to-end without a routing key — useful for local trials and the video
walkthrough. Geocoding uses Open-Meteo's free geocoder; routes are *synthesised*
(a direct line plus a north and south detour). Weather is always the real
Open-Meteo forecast, so risk still varies realistically along the corridor.

This is clearly not truck-legal routing — the real HERE path (services/here.py) is
the primary provider; this only keeps the product usable without a key.
"""
from __future__ import annotations

import math

import requests

from routing.core.sampling import haversine_mi
from .here import Route

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT = 20
AVG_MPH = 55.0


def geocode(query: str) -> tuple[float, float]:
    resp = requests.get(GEOCODE_URL, params={"name": query, "count": 1}, timeout=TIMEOUT)
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        raise ValueError(f"could not geocode: {query!r}")
    return results[0]["latitude"], results[0]["longitude"]


def _polyline(origin, dest, bulge, n=60):
    """Straight interpolation with a sinusoidal perpendicular bulge (a fake detour)."""
    olat, olon = origin
    dlat, dlon = dest
    # Perpendicular unit direction in lat/lon space (good enough for a demo shape).
    dx, dy = dlat - olat, dlon - olon
    length = math.hypot(dx, dy) or 1.0
    perp = (-dy / length, dx / length)
    pts = []
    for i in range(n + 1):
        t = i / n
        offset = math.sin(t * math.pi) * bulge
        lat = olat + dx * t + perp[0] * offset
        lon = olon + dy * t + perp[1] * offset
        pts.append((lat, lon))
    return pts


def demo_routes(origin, dest) -> list[Route]:
    variants = [("Route 1 (direct)", 0.0), ("Route 2 (north)", 1.3), ("Route 3 (south)", -1.1)]
    routes = []
    for i, (label, bulge) in enumerate(variants):
        poly = _polyline(origin, dest, bulge)
        dist_mi = sum(haversine_mi(*poly[j], *poly[j + 1]) for j in range(len(poly) - 1))
        routes.append(Route(
            label=label,
            distance_mi=dist_mi,
            duration_s=dist_mi / AVG_MPH * 3600,
            polyline=poly,
        ))
    return routes

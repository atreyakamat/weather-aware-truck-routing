"""HERE Geocoding & Routing (v8) client.

Only this module knows the HERE API key; the frontend never sees it. Routes use
`transportMode=truck` with `alternatives` so we get up to 3 truck-legal options.
Route geometry comes back as a HERE *flexible polyline* per section, decoded with
the `flexpolyline` package.
"""
from __future__ import annotations

from dataclasses import dataclass

import flexpolyline
import requests

GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"
ROUTES_URL = "https://router.hereapi.com/v8/routes"
TIMEOUT = 20


class HereError(RuntimeError):
    pass


@dataclass
class Route:
    label: str
    distance_mi: float
    duration_s: float
    polyline: list[tuple[float, float]]  # [(lat, lon), ...]


def _key(api_key: str | None) -> str:
    from django.conf import settings

    key = api_key or settings.HERE_API_KEY
    if not key:
        raise HereError("HERE_API_KEY is not configured")
    return key


def geocode(query: str, api_key: str | None = None) -> tuple[float, float]:
    """Resolve a place/address string to (lat, lon)."""
    resp = requests.get(
        GEOCODE_URL,
        params={"q": query, "limit": 1, "apiKey": _key(api_key)},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        raise HereError(f"could not geocode: {query!r}")
    pos = items[0]["position"]
    return pos["lat"], pos["lng"]


def _decode_route(route_json: dict, index: int) -> Route:
    """Flatten a HERE route (one or more sections) into a single Route."""
    coords: list[tuple[float, float]] = []
    distance_m = 0.0
    duration_s = 0.0
    for section in route_json["sections"]:
        decoded = flexpolyline.decode(section["polyline"])  # [(lat, lon[, elev]), ...]
        for pt in decoded:
            coords.append((pt[0], pt[1]))
        summary = section["summary"]
        distance_m += summary["length"]
        duration_s += summary["duration"]
    return Route(
        label=f"Route {index + 1}",
        distance_mi=distance_m / 1609.344,
        duration_s=duration_s,
        polyline=coords,
    )


def truck_routes(
    origin: tuple[float, float],
    destination: tuple[float, float],
    departure_iso: str,
    alternatives: int = 2,
    api_key: str | None = None,
) -> list[Route]:
    """Return up to `alternatives + 1` truck routes between origin and destination."""
    olat, olon = origin
    dlat, dlon = destination
    params = {
        "transportMode": "truck",
        "origin": f"{olat},{olon}",
        "destination": f"{dlat},{dlon}",
        "departureTime": departure_iso,
        "alternatives": alternatives,
        "return": "polyline,summary",
        "apiKey": _key(api_key),
    }
    resp = requests.get(ROUTES_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    routes = resp.json().get("routes", [])
    if not routes:
        raise HereError("HERE returned no routes")
    return [_decode_route(r, i) for i, r in enumerate(routes)]

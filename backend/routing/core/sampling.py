"""Route sampling + ETA.

Pure functions (stdlib only). Walks a decoded polyline, drops a checkpoint every
N miles, and computes each checkpoint's estimated arrival time by interpolating
along the route's total duration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

EARTH_RADIUS_MI = 3958.7613


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two lat/lon points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


@dataclass
class Checkpoint:
    seq: int
    lat: float
    lon: float
    mile: float          # cumulative miles from origin
    segment_mi: float    # miles since the previous checkpoint (for risk aggregation)


def walk_polyline(points: list[tuple[float, float]], interval_mi: float) -> tuple[list[Checkpoint], float]:
    """Place checkpoints at mile 0 (origin), every `interval_mi`, and the destination.

    Returns (checkpoints, total_distance_mi). Linear interpolation between the two
    polyline vertices surrounding each mile mark.
    """
    if len(points) < 2:
        raise ValueError("polyline needs at least 2 points")
    if interval_mi <= 0:
        raise ValueError("interval must be positive")

    marks: list[tuple[float, float, float]] = [(points[0][0], points[0][1], 0.0)]
    cum = 0.0
    next_mark = interval_mi

    for i in range(len(points) - 1):
        (alat, alon), (blat, blon) = points[i], points[i + 1]
        d = haversine_mi(alat, alon, blat, blon)
        while d > 0 and cum + d >= next_mark - 1e-9:
            frac = (next_mark - cum) / d
            marks.append((alat + (blat - alat) * frac, alon + (blon - alon) * frac, next_mark))
            next_mark += interval_mi
        cum += d

    total = cum
    # Append destination unless the last mark already lands on it.
    if abs(marks[-1][2] - total) > 1e-6:
        marks.append((points[-1][0], points[-1][1], total))

    checkpoints: list[Checkpoint] = []
    prev_mile = 0.0
    for seq, (lat, lon, mile) in enumerate(marks):
        checkpoints.append(Checkpoint(seq=seq, lat=lat, lon=lon, mile=round(mile, 3),
                                      segment_mi=round(mile - prev_mile, 3)))
        prev_mile = mile
    return checkpoints, total


def eta_at(departure: datetime, mile: float, total_mi: float, total_duration_s: float) -> datetime:
    """Estimated arrival at `mile`, assuming time accrues proportionally to distance."""
    frac = (mile / total_mi) if total_mi > 0 else 0.0
    return departure + timedelta(seconds=frac * total_duration_s)

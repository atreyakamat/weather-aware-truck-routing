"""Weather-risk classification engine.

Pure functions only (stdlib). No network, no Django imports — so this module is
trivially unit-testable and is the single source of truth for the risk rules.

Bands use **lower-bound-inclusive** comparisons with explicit "No Travel" cutoffs,
which closes the gaps in the spec's printed ranges (e.g. wind 54->55).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


LABELS: dict[Risk, str] = {
    Risk.LOW: "Low",
    Risk.MODERATE: "Moderate",
    Risk.HIGH: "High",
    Risk.SEVERE: "Severe",
    Risk.NO_TRAVEL: "No Travel",
}


# --- Per-metric classification --------------------------------------------------

def classify_wind(mph: float) -> Risk:
    """Wind (mph): <25 Low | 25-34 Moderate | 35-44 High | 45-54 Severe | >=55 No Travel."""
    if mph >= 55:
        return Risk.NO_TRAVEL
    if mph >= 45:
        return Risk.SEVERE
    if mph >= 35:
        return Risk.HIGH
    if mph >= 25:
        return Risk.MODERATE
    return Risk.LOW


def classify_rain(in_per_hr: float) -> Risk:
    """Rain (in/hr): <0.10 Low | 0.10-0.25 Moderate | 0.25-0.50 High | 0.50-1.00 Severe | >1.00 No Travel."""
    if in_per_hr > 1.00:
        return Risk.NO_TRAVEL
    if in_per_hr >= 0.50:
        return Risk.SEVERE
    if in_per_hr >= 0.25:
        return Risk.HIGH
    if in_per_hr >= 0.10:
        return Risk.MODERATE
    return Risk.LOW


def classify_snow(in_per_hr: float) -> Risk:
    """Snow (in/hr): <0.5 Low | 0.5-1.0 Moderate | 1.0-2.0 High | 2.0-3.0 Severe | >3.0 No Travel."""
    if in_per_hr > 3.0:
        return Risk.NO_TRAVEL
    if in_per_hr >= 2.0:
        return Risk.SEVERE
    if in_per_hr >= 1.0:
        return Risk.HIGH
    if in_per_hr >= 0.5:
        return Risk.MODERATE
    return Risk.LOW


@dataclass
class CheckpointRisk:
    level: Risk
    wind_level: Risk
    rain_level: Risk
    snow_level: Risk
    reasons: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return LABELS[self.level]


def classify_checkpoint(wind_mph: float, rain_in: float, snow_in: float, load_lb: float) -> CheckpointRisk:
    """Classify one checkpoint: worst of wind/rain/snow, then apply load overrides.

    Load rules (escalations driven by wind band + load weight):
      * wind >=55           -> No Travel (any load)  [already handled by wind band]
      * wind 45-54 & >30,000 -> No Travel (Severe -> No Travel)
      * wind 35-44 & >40,000 -> Severe    (High  -> Severe)
    """
    wind = classify_wind(wind_mph)
    rain = classify_rain(rain_in)
    snow = classify_snow(snow_in)
    base = max(wind, rain, snow)

    reasons: list[str] = []
    for name, value, unit, lvl in (
        ("Wind", wind_mph, "mph", wind),
        ("Rain", rain_in, "in/hr", rain),
        ("Snow", snow_in, "in/hr", snow),
    ):
        if lvl == base and base > Risk.LOW:
            reasons.append(f"{name} {value:g} {unit} → {LABELS[lvl]}")

    override = Risk.LOW
    if 45 <= wind_mph < 55 and load_lb > 30_000:
        override = Risk.NO_TRAVEL
        reasons.append(
            f"Load {load_lb:,.0f} lb + wind {wind_mph:g} mph (45-54) → No Travel"
        )
    elif 35 <= wind_mph < 45 and load_lb > 40_000:
        override = Risk.SEVERE
        reasons.append(
            f"Load {load_lb:,.0f} lb + wind {wind_mph:g} mph (35-44) → Severe"
        )

    final = max(base, override)
    if final == Risk.LOW:
        reasons = ["Clear → Low"]
    return CheckpointRisk(level=final, wind_level=wind, rain_level=rain, snow_level=snow, reasons=reasons)


# --- Route aggregation ----------------------------------------------------------

@dataclass
class RouteScore:
    severe_miles: float
    high_miles: float
    no_travel_miles: float
    avg_risk: float
    has_no_travel: bool
    duration_min: float


def aggregate_route(levels_and_miles: list[tuple[Risk, float]], duration_min: float) -> RouteScore:
    """Aggregate a route's per-segment (level, miles) into a comparable score.

    `avg_risk` is length-weighted so a long calm stretch isn't outweighed by one
    short checkpoint. Checkpoints with 0 segment miles (e.g. the origin marker)
    still count toward avg_risk via a nominal unit weight so they aren't ignored.
    """
    severe = high = no_travel = 0.0
    weighted_sum = 0.0
    weight_total = 0.0
    has_no_travel = False
    for level, miles in levels_and_miles:
        if level == Risk.SEVERE:
            severe += miles
        elif level == Risk.HIGH:
            high += miles
        elif level == Risk.NO_TRAVEL:
            no_travel += miles
            has_no_travel = True
        w = miles if miles > 0 else 1.0
        weighted_sum += int(level) * w
        weight_total += w
    avg = weighted_sum / weight_total if weight_total else 0.0
    return RouteScore(
        severe_miles=round(severe, 2),
        high_miles=round(high, 2),
        no_travel_miles=round(no_travel, 2),
        avg_risk=round(avg, 3),
        has_no_travel=has_no_travel,
        duration_min=round(duration_min, 1),
    )


# --- Recommendation -------------------------------------------------------------

# (field name, human phrase) in spec priority order.
_CRITERIA = [
    ("has_no_travel", "avoids No-Travel segments"),
    ("severe_miles", "fewest Severe miles"),
    ("high_miles", "fewest High miles"),
    ("avg_risk", "lowest average risk"),
    ("duration_min", "shortest travel time"),
]


def _sort_key(score: RouteScore) -> tuple:
    return (
        int(score.has_no_travel),
        score.severe_miles,
        score.high_miles,
        score.avg_risk,
        score.duration_min,
    )


def recommend(scores: list[RouteScore]) -> tuple[int, str]:
    """Return (index_of_best_route, human deciding-criterion string).

    Ranking is lexicographic over the spec's priority order. The criterion names
    the first field on which the winner beats the runner-up.
    """
    if not scores:
        raise ValueError("no routes to rank")
    order = sorted(range(len(scores)), key=lambda i: _sort_key(scores[i]))
    best = order[0]
    if len(order) == 1:
        return best, "only route available"
    runner = order[1]
    b, r = scores[best], scores[runner]
    for field_name, phrase in _CRITERIA:
        bv, rv = getattr(b, field_name), getattr(r, field_name)
        if bv != rv:
            return best, phrase
    return best, "tie-break by travel time"

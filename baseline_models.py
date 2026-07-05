"""
baseline_models.py
Implements the three counterfactual/baseline models described in the research paper,
plus two hybrid combinations. Pure functions - given trip history, return kg CO2 avoided
(or None if the model cannot yet compute a value for that trip).

All three models operate on a chronological list of Trip objects for a single user, and
evaluate ONE trip at a time (the "current" trip), using only trips that happened before it
(no lookahead - this matters, a real system would never see future trips either).
"""

from typing import List, Optional
from collections import defaultdict

from trip_generator import Trip
from config import (
    MODE_EMISSION_FACTORS,
    CAR_EMISSION_FACTOR_KG_PER_KM,
    CO2_TO_TOKEN_RATE,
    HISTORICAL_WINDOW_DAYS,
    MIN_TRIPS_FOR_HISTORICAL_BASELINE,
    MIN_MODES_FOR_MATCH,
)


def trip_emissions(trip: Trip) -> float:
    """Actual emissions for a trip given its mode and distance."""
    factor = MODE_EMISSION_FACTORS.get(trip.mode, CAR_EMISSION_FACTOR_KG_PER_KM)
    return factor * trip.distance_km


# ---------------------------------------------------------------------------
# Model 1: Counterfactual (fixed reference mode - default: car)
# ---------------------------------------------------------------------------
def counterfactual_baseline(
    trip: Trip,
    history: List[Trip] = None,
    reference_mode: str = "car",
) -> Optional[float]:
    """
    Reduction = emissions if the reference mode (default: car) had been used, minus
    actual emissions. Works on trip 1, no history required.
    Weakness (per the paper): over-credits users who wouldn't have driven anyway.
    """
    reference_emissions = MODE_EMISSION_FACTORS[reference_mode] * trip.distance_km
    actual_emissions = trip_emissions(trip)
    reduction = reference_emissions - actual_emissions
    return max(0.0, reduction)  # no negative credit under this model


# ---------------------------------------------------------------------------
# Model 2: User-specific historical baseline (rolling average emissions/km)
# ---------------------------------------------------------------------------
def historical_baseline(
    trip: Trip,
    history: List[Trip],
    window_days: int = HISTORICAL_WINDOW_DAYS,
) -> Optional[float]:
    """
    Reduction = (user's rolling-average emissions per km) * this trip's distance,
    minus this trip's actual emissions. Requires a minimum trip count to activate
    (cold-start problem noted in the paper).
    """
    prior_trips = [t for t in history if t.day < trip.day and t.day >= trip.day - window_days]

    if len(prior_trips) < MIN_TRIPS_FOR_HISTORICAL_BASELINE:
        return None  # not enough history yet - cold start

    total_emissions = sum(trip_emissions(t) for t in prior_trips)
    total_distance = sum(t.distance_km for t in prior_trips)
    if total_distance == 0:
        return None

    avg_emissions_per_km = total_emissions / total_distance
    baseline_emissions = avg_emissions_per_km * trip.distance_km
    actual_emissions = trip_emissions(trip)
    reduction = baseline_emissions - actual_emissions
    return reduction  # NOTE: can be negative if this trip is worse than the user's own average


# ---------------------------------------------------------------------------
# Model 3: Matched-trip baseline (same OD pair, different mode)
# ---------------------------------------------------------------------------
def matched_trip_baseline(
    trip: Trip,
    history: List[Trip],
) -> Optional[float]:
    """
    Reduction = emissions of this user's own past trip(s) on the SAME OD pair but a
    DIFFERENT mode, minus this trip's emissions. Controls for route geometry.
    Only works once the user has traveled this OD pair in another mode. Sparse by design.
    """
    same_od_other_mode = [
        t for t in history
        if t.day < trip.day and t.od_pair == trip.od_pair and t.mode != trip.mode
    ]

    if len(same_od_other_mode) < 1:
        return None  # no match available yet

    # use the highest-emission prior mode on this OD pair as the comparison point
    comparison_trip = max(same_od_other_mode, key=trip_emissions)
    baseline_emissions = trip_emissions(comparison_trip)
    actual_emissions = trip_emissions(trip)
    reduction = baseline_emissions - actual_emissions
    return reduction


# ---------------------------------------------------------------------------
# Hybrid 1: Waterfall - use the most specific model that is currently computable
# ---------------------------------------------------------------------------
def hybrid_waterfall(trip: Trip, history: List[Trip]) -> Optional[float]:
    """
    Priority: matched-trip (most accurate, controls for route) > historical
    (personalized) > counterfactual (always available, fallback of last resort).

    KNOWN BEHAVIOR (not a bug - a real design tradeoff worth flagging to stakeholders):
    For zero-emission modes (walk/bike), historical and matched-trip will often
    return exactly 0.0 once they have enough data, because there is no *marginal*
    improvement left to detect against the user's own already-green history. Since
    0.0 is a valid computed value (not None), the waterfall latches onto it and never
    falls back to counterfactual - meaning already-sustainable users can get starved
    of ongoing reward under this priority order, even though they remain low-carbon.
    This is arguably correct per the models' own definitions (they measure marginal
    improvement, not absolute impact) - but it is a real engagement risk worth
    discussing with the team, not something to silently "fix" by hiding it.
    """
    matched = matched_trip_baseline(trip, history)
    if matched is not None:
        return matched

    historical = historical_baseline(trip, history)
    if historical is not None:
        return historical

    return counterfactual_baseline(trip, history)


# ---------------------------------------------------------------------------
# Hybrid 2: Weighted ensemble - blend whichever models are computable
# ---------------------------------------------------------------------------
def hybrid_weighted(
    trip: Trip,
    history: List[Trip],
    weights: dict = None,
) -> Optional[float]:
    """
    Blends all currently-computable models, weighted by a confidence score.
    Default weights favor matched-trip (most rigorous) when available, and fall
    back proportionally when it isn't.
    """
    weights = weights or {"matched": 0.5, "historical": 0.3, "counterfactual": 0.2}

    candidates = {
        "matched": matched_trip_baseline(trip, history),
        "historical": historical_baseline(trip, history),
        "counterfactual": counterfactual_baseline(trip, history),
    }
    available = {k: v for k, v in candidates.items() if v is not None}
    if not available:
        return None

    total_weight = sum(weights[k] for k in available)
    blended = sum(available[k] * (weights[k] / total_weight) for k in available)
    return blended


# ---------------------------------------------------------------------------
# Token conversion
# ---------------------------------------------------------------------------
def co2_to_tokens(kg_co2_avoided: float) -> float:
    """Applies the proposal's 1:5 conversion (1kg avoided = 5 tokens). Floors at 0."""
    if kg_co2_avoided is None:
        return 0.0
    return max(0.0, kg_co2_avoided) * CO2_TO_TOKEN_RATE


MODEL_REGISTRY = {
    "counterfactual": counterfactual_baseline,
    "historical": historical_baseline,
    "matched_trip": matched_trip_baseline,
    "hybrid_waterfall": hybrid_waterfall,
    "hybrid_weighted": hybrid_weighted,
}
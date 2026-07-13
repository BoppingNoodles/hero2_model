"""
baseline_models.py
Implements the original three counterfactual/baseline models, two hybrids, and the new
LIGHT-BASELINE model requested for the macro simulation. Pure functions - given trip
history, return kg CO2 avoided (or None if the model cannot yet compute a value).

IMPORTANT DISTINCTION requested by the team: the reward baseline (what determines how
many tokens a user gets) and the true environmental impact (what actually happened,
for reporting/additionality purposes) are now tracked SEPARATELY. A trip can earn a
softened reward under light_baseline while its true impact is still computed against
the full counterfactual - see true_environmental_impact() at the bottom of this file.
"""

from typing import List, Optional

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
# Equivalent to the "no-baseline" model the team asked to test: every verified
# sustainable trip earns Power measured against a fixed car reference, no history used.
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

    comparison_trip = max(same_od_other_mode, key=trip_emissions)
    baseline_emissions = trip_emissions(comparison_trip)
    actual_emissions = trip_emissions(trip)
    reduction = baseline_emissions - actual_emissions
    return reduction


# ---------------------------------------------------------------------------
# Hybrid 1: Waterfall
# ---------------------------------------------------------------------------
def hybrid_waterfall(trip: Trip, history: List[Trip]) -> Optional[float]:
    """
    Priority: matched-trip > historical > counterfactual (fallback of last resort).

    KNOWN BEHAVIOR (not a bug - a real design tradeoff): for zero-emission modes
    (walk/bike), historical and matched-trip will often return exactly 0.0 once they
    have enough data, since there is no further improvement to detect against an
    already-green history. Since 0.0 is a valid value (not None), the waterfall
    latches onto it and never falls back to counterfactual.
    """
    matched = matched_trip_baseline(trip, history)
    if matched is not None:
        return matched

    historical = historical_baseline(trip, history)
    if historical is not None:
        return historical

    return counterfactual_baseline(trip, history)


# ---------------------------------------------------------------------------
# Hybrid 2: Weighted ensemble
# ---------------------------------------------------------------------------
def hybrid_weighted(
    trip: Trip,
    history: List[Trip],
    weights: dict = None,
) -> Optional[float]:
    """Blends all currently-computable models, weighted by a confidence score."""
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
# NEW Model: Light-baseline (macro simulation request)
# ---------------------------------------------------------------------------
def _user_avg_emissions_per_km(trip: Trip, history: List[Trip], window_days: int = HISTORICAL_WINDOW_DAYS) -> Optional[float]:
    """Helper: user's own rolling average emissions/km, or None if not enough history."""
    prior_trips = [t for t in history if t.day < trip.day and t.day >= trip.day - window_days]
    if len(prior_trips) < MIN_TRIPS_FOR_HISTORICAL_BASELINE:
        return None
    total_distance = sum(t.distance_km for t in prior_trips)
    if total_distance == 0:
        return None
    return sum(trip_emissions(t) for t in prior_trips) / total_distance


def light_baseline(
    trip: Trip,
    history: List[Trip],
    baseline_factor: float,
    reference_mode: str = "car",
) -> Optional[float]:
    """
    Parameterized model requested for the macro simulation. The reward reference point
    is a blend between the fixed car reference and the user's own historical average:

        reference_per_km = (1 - factor) * car_factor + factor * user_avg_per_km

    factor = 0.0  -> identical to counterfactual ("no baseline" model - every verified
                     trip earns Power against the full car reference)
    factor = 1.0  -> reference is (almost) fully the user's own historical average
                     (closest to the pure historical model, but WITHOUT its cold-start
                     gap - see below)
    factor = 0.25 -> the company's proposed initial "soft baseline": only a quarter of
                     the user's own historical average is deducted from the reward

    Cold-start handling: if the user has no usable history yet, the historical term
    falls back to the car factor (i.e. behaves as if baseline_factor were 0 for that
    trip only). This means light_baseline NEVER returns None - unlike historical_baseline
    or matched_trip_baseline, it always produces a reward, which is required for the
    "no unlimited free-riding, but no cold-start gap either" balance the team is after.
    """
    car_factor = MODE_EMISSION_FACTORS[reference_mode]
    user_avg = _user_avg_emissions_per_km(trip, history)
    effective_user_avg = user_avg if user_avg is not None else car_factor  # cold-start fallback

    reference_per_km = (1 - baseline_factor) * car_factor + baseline_factor * effective_user_avg
    reference_emissions = reference_per_km * trip.distance_km
    actual_emissions = trip_emissions(trip)
    reduction = reference_emissions - actual_emissions
    return max(0.0, reduction)  # no negative reward, consistent with counterfactual


def true_environmental_impact(trip: Trip) -> float:
    """
    Always computes the FULL counterfactual reduction (car reference), regardless of
    which model is used to calculate the user-facing reward. This is what should be
    reported for environmental impact / additionality purposes, per the team's
    explicit instruction to keep these two calculations separate.
    """
    return counterfactual_baseline(trip)


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

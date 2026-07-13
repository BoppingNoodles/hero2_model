"""
token_model.py
Splits Power into the three components the team requested:

- verification Power: flat amount for any verified sustainable trip, regardless of
  emissions reduction (rewards participation itself)
- improvement Power: proportional to the emissions reduction ABOVE whichever reward
  baseline is active (light_baseline at the configured factor) - this is the only
  component affected by the baseline_factor sweep
- challenge Power: streak milestones and cumulative trip-count milestones (leaderboard
  bonuses are NOT modeled - see config.py note on why)

This module also flags "additional trips" - a proxy for trips that likely would NOT
have happened without the app, used for the macro simulation's "estimated additional
trips" metric.
"""

from dataclasses import dataclass
from typing import List, Optional

from trip_generator import Trip
from baseline_models import light_baseline, true_environmental_impact, co2_to_tokens
from config import (
    VERIFICATION_POWER_PER_TRIP,
    CHALLENGE_POWER_STREAK_MILESTONES,
    CHALLENGE_POWER_TRIP_MILESTONES,
)


@dataclass
class TokenBreakdown:
    verification_power: float
    improvement_power: float
    challenge_power: float
    true_co2_avoided_kg: float          # always computed against the FULL counterfactual
    reward_co2_avoided_kg: float        # computed against the active reward baseline (may be softened)
    is_additional_trip: bool            # proxy: did the user deviate from their true baseline_mode?

    @property
    def total_power(self) -> float:
        return self.verification_power + self.improvement_power + self.challenge_power


def compute_token_breakdown(
    trip: Trip,
    history: List[Trip],
    baseline_factor: float,
    streak_days: int,
    lifetime_trip_count: int,
    true_baseline_mode: str,
) -> TokenBreakdown:
    """
    Computes the full Power breakdown for a single trip.

    streak_days / lifetime_trip_count are passed in as "the value BEFORE this trip is
    counted" - milestone bonuses fire on the day a threshold is newly crossed.
    """
    # --- Verification Power: flat, always awarded for a verified trip ---
    verification_power = VERIFICATION_POWER_PER_TRIP

    # --- Improvement Power: based on the active (possibly softened) reward baseline ---
    reward_reduction = light_baseline(trip, history, baseline_factor)
    improvement_power = co2_to_tokens(reward_reduction)

    # --- Challenge Power: streak + trip-count milestones ---
    challenge_power = 0.0
    new_streak = streak_days + 1
    if new_streak in CHALLENGE_POWER_STREAK_MILESTONES:
        challenge_power += CHALLENGE_POWER_STREAK_MILESTONES[new_streak]

    new_trip_count = lifetime_trip_count + 1
    if new_trip_count in CHALLENGE_POWER_TRIP_MILESTONES:
        challenge_power += CHALLENGE_POWER_TRIP_MILESTONES[new_trip_count]

    # --- True environmental impact: always the full counterfactual, independent of reward ---
    true_reduction = true_environmental_impact(trip)

    # --- Additional trip proxy: did this trip deviate from the user's true baseline mode? ---
    is_additional = trip.mode != true_baseline_mode

    return TokenBreakdown(
        verification_power=verification_power,
        improvement_power=improvement_power,
        challenge_power=challenge_power,
        true_co2_avoided_kg=true_reduction,
        reward_co2_avoided_kg=reward_reduction if reward_reduction is not None else 0.0,
        is_additional_trip=is_additional,
    )

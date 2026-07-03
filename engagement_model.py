"""
engagement_model.py
Simulates how a synthetic user's engagement evolves in response to tokens earned.

This is the layer that turns "tokens earned" into "likelihood of continuing to engage" -
there is no real data behind this, so the logic here is an explicit, documented set of
assumptions grounded in the behavioral-science language already used in the Token
Framework Proposal (immediate reinforcement, streaks, near-goal boosts, drop-off
reduction). Treat the constants in config.py as the knobs for sensitivity analysis -
that's the point of this being a separate, simple module rather than baked into the
trip generator.

Model summary:
- engagement score in [0, 1], starts at ENGAGEMENT_START (or persona override)
- each day WITHOUT a rewarded trip: engagement decays by ENGAGEMENT_DECAY_PER_DAY
- each day WITH a rewarded trip: engagement gains, scaled by tokens earned with
  diminishing returns (saturating gain), boosted further while on an active streak
- engagement score is converted to a trip probability for the NEXT day, which the
  experiment runner feeds back into trip generation frequency
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict

from config import (
    ENGAGEMENT_START,
    ENGAGEMENT_DECAY_PER_DAY,
    ENGAGEMENT_REWARD_GAIN,
    ENGAGEMENT_REWARD_GAIN_SATURATION,
    STREAK_BONUS_MULTIPLIER,
    MIN_TRIP_PROBABILITY,
    MAX_TRIP_PROBABILITY,
)


@dataclass
class EngagementState:
    engagement: float
    streak_days: int = 0
    history: List[float] = field(default_factory=list)  # engagement score per day, for plotting

    def record(self):
        self.history.append(self.engagement)


def engagement_gain(tokens_earned: float) -> float:
    """
    Diminishing-returns gain from tokens earned in a day. Uses a bounded saturation
    curve so a 50-token day doesn't give 5x the engagement boost of a 10-token day -
    consistent with the proposal's use of milestone tiers rather than pure linear scaling.
    Approaches a max gain per day as tokens_earned grows large.
    """
    if tokens_earned <= 0:
        return 0.0
    max_gain = ENGAGEMENT_REWARD_GAIN * 5  # cap on how much a single day can move engagement
    return max_gain * (1 - math.exp(-tokens_earned / ENGAGEMENT_REWARD_GAIN_SATURATION))


def step_engagement(state: EngagementState, tokens_earned_today: float, had_trip_today: bool) -> EngagementState:
    """Advance engagement state by one simulated day."""
    if had_trip_today and tokens_earned_today > 0:
        state.streak_days += 1
        gain = engagement_gain(tokens_earned_today)
        if state.streak_days >= 3:
            gain *= STREAK_BONUS_MULTIPLIER
        state.engagement = min(1.0, state.engagement + gain)
    else:
        state.streak_days = 0
        state.engagement = max(0.0, state.engagement - ENGAGEMENT_DECAY_PER_DAY)

    state.record()
    return state


def engagement_to_trip_probability(engagement: float, base_frequency: float) -> float:
    """
    Converts current engagement score into tomorrow's trip probability, anchored
    around the persona's base trip frequency. Engagement acts as a multiplier on top
    of the base rate, clipped to a sane range so no user is ever at 0% or 100%.
    """
    # engagement of 0.5 = neutral (no change to base rate); above/below scales it
    multiplier = 0.5 + engagement  # ranges 0.5 to 1.5 as engagement goes 0 to 1
    prob = base_frequency * multiplier
    return max(MIN_TRIP_PROBABILITY, min(MAX_TRIP_PROBABILITY, prob))


def init_engagement_state(starting_engagement: float = None) -> EngagementState:
    return EngagementState(engagement=starting_engagement if starting_engagement is not None else ENGAGEMENT_START)
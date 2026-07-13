"""
engagement_model.py
Simulates how a synthetic user's engagement evolves in response to Power earned.

EXTENDED from v1 to incorporate:
1. Archetype-specific sensitivities: reward_sensitivity scales the effect of
   verification+improvement Power; gamification_sensitivity scales the effect of
   challenge Power. These are evaluated SEPARATELY, per the team's request to test
   whether gamification alone can sustain engagement independent of token value.
2. Habit conversion: after a long enough streak, a user may "convert" to intrinsically
   motivated/habitual behavior, after which daily decay is reduced.
3. Redemption tapering: a separate multiplier that shrinks the effective value of
   verification+improvement Power over time (simulating redeemable rewards losing
   value), while challenge Power is unaffected - this is what lets us test whether
   gamification mechanics alone can hold engagement up as real rewards shrink.

None of this is calibrated to real data - see README for how to treat these results.
"""

import math
from dataclasses import dataclass, field
from typing import List

from archetypes import Archetype
from config import (
    ENGAGEMENT_START,
    ENGAGEMENT_DECAY_PER_DAY,
    ENGAGEMENT_REWARD_GAIN,
    ENGAGEMENT_REWARD_GAIN_SATURATION,
    STREAK_BONUS_MULTIPLIER,
    MIN_TRIP_PROBABILITY,
    MAX_TRIP_PROBABILITY,
    HABIT_CONVERSION_STREAK_THRESHOLD,
    HABIT_DECAY_REDUCTION_FACTOR,
    REDEMPTION_TAPER_START_DAY,
    REDEMPTION_TAPER_END_DAY,
    REDEMPTION_TAPER_FLOOR,
)


@dataclass
class EngagementState:
    engagement: float
    streak_days: int = 0
    is_habitual: bool = False
    history: List[float] = field(default_factory=list)  # engagement score per day, for plotting

    def record(self):
        self.history.append(self.engagement)


def _saturating_gain(value: float, saturation: float) -> float:
    """Shared diminishing-returns curve used for both reward-driven and gamification-driven gain."""
    if value <= 0:
        return 0.0
    max_gain = ENGAGEMENT_REWARD_GAIN * 5
    return max_gain * (1 - math.exp(-value / saturation))


def redemption_value_multiplier(day: int) -> float:
    """
    Returns the current multiplier on redeemable (verification+improvement) Power's
    effective value, simulating the "redeemable rewards taper" scenario. Ramps
    linearly from 1.0 down to REDEMPTION_TAPER_FLOOR between the configured start
    and end days, then holds at the floor. Returns 1.0 (no taper) before the start day.
    Used only in the tapering experiment - the macro/baseline-sweep runs hold this at 1.0.
    """
    if day < REDEMPTION_TAPER_START_DAY:
        return 1.0
    if day >= REDEMPTION_TAPER_END_DAY:
        return REDEMPTION_TAPER_FLOOR
    progress = (day - REDEMPTION_TAPER_START_DAY) / (REDEMPTION_TAPER_END_DAY - REDEMPTION_TAPER_START_DAY)
    return 1.0 - progress * (1.0 - REDEMPTION_TAPER_FLOOR)


def step_engagement(
    state: EngagementState,
    verification_power: float,
    improvement_power: float,
    challenge_power: float,
    had_trip_today: bool,
    archetype: Archetype,
    taper_multiplier: float = 1.0,
) -> EngagementState:
    """
    Advance engagement state by one simulated day.

    Reward-driven Power (verification + improvement) and gamification-driven Power
    (challenge) are evaluated as two SEPARATE gain terms, each scaled by the archetype's
    corresponding sensitivity, then combined. taper_multiplier (from
    redemption_value_multiplier) discounts only the reward-driven term - challenge Power
    is deliberately unaffected, since streaks/leaderboards/milestones don't depend on
    redeemable value.
    """
    reward_power_today = (verification_power + improvement_power) * taper_multiplier
    had_any_power_today = had_trip_today and (verification_power + improvement_power + challenge_power) > 0

    if had_any_power_today:
        state.streak_days += 1

        reward_gain = _saturating_gain(reward_power_today, ENGAGEMENT_REWARD_GAIN_SATURATION) * archetype.reward_sensitivity
        gamification_gain = _saturating_gain(challenge_power, ENGAGEMENT_REWARD_GAIN_SATURATION) * archetype.gamification_sensitivity
        gain = reward_gain + gamification_gain

        if state.streak_days >= 3:
            gain *= STREAK_BONUS_MULTIPLIER

        state.engagement = min(1.0, state.engagement + gain)

        # Habit conversion check: once on a long enough streak, roll a daily chance
        # of converting to intrinsically-motivated/habitual behavior.
        if not state.is_habitual and state.streak_days >= HABIT_CONVERSION_STREAK_THRESHOLD:
            import random
            if random.random() < archetype.habit_conversion_probability:
                state.is_habitual = True
    else:
        state.streak_days = 0
        decay = ENGAGEMENT_DECAY_PER_DAY

        # Post-incentive decay: while redemption value is tapered, decay is scaled by
        # the archetype's post_incentive_decay_multiplier (reward-dependent archetypes
        # decay faster; gamification/impact-driven archetypes decay slower).
        if taper_multiplier < 1.0:
            decay *= archetype.post_incentive_decay_multiplier

        # Habitual users decay more slowly regardless of taper - intrinsic motivation
        # partially insulates them from missing a reward on any given day.
        if state.is_habitual:
            decay *= HABIT_DECAY_REDUCTION_FACTOR

        state.engagement = max(0.0, state.engagement - decay)

    state.record()
    return state


def engagement_to_trip_probability(engagement: float, base_frequency: float) -> float:
    """
    Converts current engagement score into tomorrow's trip probability, anchored
    around the persona's base trip frequency.
    """
    multiplier = 0.5 + engagement  # ranges 0.5 to 1.5 as engagement goes 0 to 1
    prob = base_frequency * multiplier
    return max(MIN_TRIP_PROBABILITY, min(MAX_TRIP_PROBABILITY, prob))


def init_engagement_state(starting_engagement: float = None) -> EngagementState:
    return EngagementState(engagement=starting_engagement if starting_engagement is not None else ENGAGEMENT_START)

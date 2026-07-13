"""
trip_generator.py
Simulates a stream of trips for a persona over N days.

Each user has a small pool of recurring origin-destination (OD) pairs - this matters
because the matched-trip baseline model only works when a user has traveled the SAME
OD pair using more than one mode. Random OD pairs every trip would make that model
useless, so OD pairs are drawn from a small fixed pool per user (see od_pool_size).

For the "reward_motivated" persona, mode choice probabilities drift toward whichever
mode most recently earned a lot of tokens - this is what lets that persona actually
respond to incentive structure differently across the three baseline models.
"""

import random
from dataclasses import dataclass
from typing import List, Dict, Optional

from personas import Persona
from config import RANDOM_SEED


@dataclass
class Trip:
    user_id: str
    day: int
    od_pair: str
    mode: str
    distance_km: float


def _generate_od_pool(persona: Persona, rng: random.Random) -> List[str]:
    """Create a fixed pool of OD pair labels for this user, e.g. 'home-work'."""
    return [f"od_{i}" for i in range(persona.od_pool_size)]


def _pick_mode(persona: Persona, mode_probs_override: Optional[Dict[str, float]], rng: random.Random) -> str:
    probs = mode_probs_override if mode_probs_override else persona.mode_probs
    modes = list(probs.keys())
    weights = list(probs.values())
    return rng.choices(modes, weights=weights, k=1)[0]


def update_mode_preference(
    current_probs: Dict[str, float],
    rewarded_mode: str,
    shift_amount: float = 0.03,
) -> Dict[str, float]:
    """
    Nudge mode probabilities toward a recently well-rewarded mode.
    Used in the reward-feedback loop for reward_motivated persona.
    Keeps probabilities normalized to sum to 1.0.
    """
    updated = dict(current_probs)
    if rewarded_mode not in updated:
        return updated

    updated[rewarded_mode] = min(0.9, updated[rewarded_mode] + shift_amount)
    remaining_modes = [m for m in updated if m != rewarded_mode]
    total_remaining = sum(updated[m] for m in remaining_modes)
    target_remaining = 1.0 - updated[rewarded_mode]

    if total_remaining > 0:
        for m in remaining_modes:
            updated[m] = (updated[m] / total_remaining) * target_remaining

    return updated

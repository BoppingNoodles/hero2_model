"""
Simulates a stream of trips for a persona over N days
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
 
 
def generate_trips(
    persona: Persona,
    n_days: int,
    user_id: str = None,
    reward_feedback: bool = False,
    seed: int = None,
) -> List[Trip]:
    """
    Generate a list of Trip objects for one synthetic user over n_days.
 
    reward_feedback: if True, mode probabilities drift toward recently-rewarded modes
                      each day (only meaningfully used for the reward_motivated persona,
                      but works for anyone). Requires the caller to pass token feedback
                      via update_mode_preference() between days - see run_experiment.py
                      for how this loop is wired up.
    """
    rng = random.Random(seed if seed is not None else RANDOM_SEED)
    user_id = user_id or persona.name
    od_pool = _generate_od_pool(persona, rng)
 
    trips = []
    current_mode_probs = dict(persona.mode_probs)
 
    for day in range(n_days):
        if rng.random() > persona.trip_frequency:
            continue  # no trip today
 
        od_pair = rng.choice(od_pool)
        mode = _pick_mode(persona, current_mode_probs if reward_feedback else None, rng)
        distance = rng.uniform(*persona.distance_km_range)
 
        trips.append(Trip(user_id=user_id, day=day, od_pair=od_pair, mode=mode, distance_km=round(distance, 2)))
 
    return trips
 
 
def update_mode_preference(
    current_probs: Dict[str, float],
    rewarded_mode: str,
    shift_amount: float = 0.03,
) -> Dict[str, float]:
    """
    Nudge mode probabilities toward a recently well-rewarded mode.
    Used by run_experiment.py in the reward-feedback loop for reward_motivated persona.
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
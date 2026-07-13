"""
personas.py
Defines synthetic user archetypes for TRANSPORT MODE BEHAVIOR. Pure data - no simulation logic here.

IMPORTANT - this is one of TWO layers of "who the user is" in this simulation:
- personas.py (this file): WHAT the user does - transport mode mix, trip frequency, routes
- archetypes.py: WHY the user is motivated - reward sensitivity, gamification sensitivity,
  habit formation, response to incentives tapering

The macro/micro simulations run every persona x archetype combination (5 x 5 = 25 synthetic
user types) so that "a Gamer who mostly carpools" and "a Mover who mostly carpools" can be
compared side by side, not just "carpooler" as a single monolithic user type.

Each persona specifies:
- mode_probs: probability distribution over transport modes on a given trip
- trip_frequency: probability of taking a trip on any given day
- od_pool_size: number of distinct origin-destination pairs this user regularly visits
                (smaller pool = more repeat OD pairs = matched-trip model activates sooner)
- baseline_mode: the mode this user would default to absent the app (used for "ground truth"
                 counterfactual comparison in analysis, AND as the proxy for whether a given
                 trip counts as an "additional"/incremental trip in the macro simulation)
- starting_engagement: initial engagement score override (optional, defaults to config value)
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Persona:
    name: str
    mode_probs: Dict[str, float]      # must sum to 1.0
    trip_frequency: float             # probability of a trip on a given day
    od_pool_size: int
    baseline_mode: str
    distance_km_range: tuple          # (min, max) trip distance, sampled uniformly
    starting_engagement: float = None  # None -> use config default

    def __post_init__(self):
        total = sum(self.mode_probs.values())
        assert abs(total - 1.0) < 1e-6, f"{self.name} mode_probs must sum to 1.0, got {total}"


PERSONAS = [
    Persona(
        name="walker_biker",
        mode_probs={"walk": 0.5, "bike": 0.4, "car": 0.1},
        trip_frequency=0.85,
        od_pool_size=4,
        baseline_mode="car",
        distance_km_range=(1, 8),
    ),
    Persona(
        name="carpooler",
        mode_probs={"carpool": 0.6, "car": 0.3, "bus": 0.1},
        trip_frequency=0.7,
        od_pool_size=3,
        baseline_mode="car",
        distance_km_range=(5, 20),
    ),
    Persona(
        name="transit_loyalist",
        # already sustainable before ever using the app - important edge case
        mode_probs={"bus": 0.5, "train": 0.4, "walk": 0.1},
        trip_frequency=0.9,
        od_pool_size=2,
        baseline_mode="bus",  # NOTE: this user's true counterfactual is NOT a car
        distance_km_range=(3, 15),
    ),
    Persona(
        name="casual_inconsistent",
        mode_probs={"car": 0.5, "walk": 0.2, "bike": 0.15, "bus": 0.15},
        trip_frequency=0.35,  # sporadic activity, high drop-off risk
        od_pool_size=6,
        baseline_mode="car",
        distance_km_range=(2, 12),
        starting_engagement=0.3,  # starts less engaged
    ),
    Persona(
        name="reward_motivated",
        # mode choice will actually shift in response to rewards (see trip_generator.py)
        mode_probs={"car": 0.4, "bike": 0.3, "carpool": 0.2, "bus": 0.1},
        trip_frequency=0.6,
        od_pool_size=4,
        baseline_mode="car",
        distance_km_range=(2, 10),
        starting_engagement=0.5,
    ),
]


def get_persona(name: str) -> Persona:
    for p in PERSONAS:
        if p.name == name:
            return p
    raise ValueError(f"Unknown persona: {name}")

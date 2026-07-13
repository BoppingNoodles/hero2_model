"""
simulate_user.py
The shared day-by-day simulation loop for ONE synthetic individual (one persona x one
archetype x one baseline_factor x one random seed), used by both the macro (baseline
sweep) and micro-to-macro (tapering) experiments so the core mechanics stay in one place.
"""

import random
from typing import List
import pandas as pd

from personas import Persona
from archetypes import Archetype
from trip_generator import Trip, _generate_od_pool, _pick_mode, update_mode_preference
from token_model import compute_token_breakdown
from engagement_model import (
    init_engagement_state,
    step_engagement,
    engagement_to_trip_probability,
    redemption_value_multiplier,
)
from config import SIMULATION_DAYS


def simulate_user(
    persona: Persona,
    archetype: Archetype,
    baseline_factor: float,
    n_days: int = SIMULATION_DAYS,
    seed: int = 0,
    apply_redemption_taper: bool = False,
    reward_feedback: bool = False,
) -> pd.DataFrame:
    """
    Simulates one synthetic individual (persona x archetype) for n_days under a given
    reward baseline_factor. Returns a day-by-day dataframe.

    apply_redemption_taper: if True, verification+improvement Power is discounted over
    time per redemption_value_multiplier() (the tapering experiment). If False (default,
    used for the macro baseline sweep), redemption value stays at 100% throughout.
    """
    rng = random.Random(seed)
    od_pool = _generate_od_pool(persona, rng)
    mode_probs = dict(persona.mode_probs)

    state = init_engagement_state(persona.starting_engagement)
    history: List[Trip] = []
    rows = []

    lifetime_trip_count = 0
    trip_probability_today = persona.trip_frequency

    for day in range(n_days):
        took_trip = rng.random() <= trip_probability_today

        verification_power = 0.0
        improvement_power = 0.0
        challenge_power = 0.0
        true_co2 = 0.0
        reward_co2 = 0.0
        is_additional = False
        mode_today = None
        distance_today = 0.0

        if took_trip:
            od_pair = rng.choice(od_pool)
            mode = _pick_mode(persona, mode_probs if reward_feedback else None, rng)
            distance = round(rng.uniform(*persona.distance_km_range), 2)
            trip = Trip(user_id=persona.name, day=day, od_pair=od_pair, mode=mode, distance_km=distance)

            breakdown = compute_token_breakdown(
                trip=trip,
                history=history,
                baseline_factor=baseline_factor,
                streak_days=state.streak_days,
                lifetime_trip_count=lifetime_trip_count,
                true_baseline_mode=persona.baseline_mode,
            )

            history.append(trip)
            lifetime_trip_count += 1
            mode_today = mode
            distance_today = distance
            verification_power = breakdown.verification_power
            improvement_power = breakdown.improvement_power
            challenge_power = breakdown.challenge_power
            true_co2 = breakdown.true_co2_avoided_kg
            reward_co2 = breakdown.reward_co2_avoided_kg
            is_additional = breakdown.is_additional_trip

            if reward_feedback and (verification_power + improvement_power) > 0:
                mode_probs = update_mode_preference(mode_probs, mode)

        taper_mult = redemption_value_multiplier(day) if apply_redemption_taper else 1.0

        state = step_engagement(
            state=state,
            verification_power=verification_power,
            improvement_power=improvement_power,
            challenge_power=challenge_power,
            had_trip_today=took_trip,
            archetype=archetype,
            taper_multiplier=taper_mult,
        )
        trip_probability_today = engagement_to_trip_probability(state.engagement, persona.trip_frequency)

        rows.append({
            "persona": persona.name,
            "archetype": archetype.name,
            "baseline_factor": baseline_factor,
            "day": day,
            "week": day // 7,
            "took_trip": took_trip,
            "mode": mode_today,
            "distance_km": distance_today,
            "verification_power": round(verification_power, 2),
            "improvement_power": round(improvement_power, 2),
            "challenge_power": round(challenge_power, 2),
            "total_power": round(verification_power + improvement_power + challenge_power, 2),
            "true_co2_avoided_kg": round(true_co2, 3),
            "reward_co2_avoided_kg": round(reward_co2, 3),
            "is_additional_trip": is_additional,
            "engagement": round(state.engagement, 4),
            "streak_days": state.streak_days,
            "is_habitual": state.is_habitual,
            "redemption_multiplier": round(taper_mult, 3),
        })

    return pd.DataFrame(rows)

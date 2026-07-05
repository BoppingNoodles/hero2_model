"""
run_experiment.py
Orchestrates the full experiment: for each (persona, model) pair, simulates trips
day-by-day, computes CO2 reduction and tokens via the chosen baseline model, feeds
tokens into the engagement model, and lets engagement feed back into next-day trip
probability (a closed loop - the whole point of this simulation).

Output: a single tidy pandas DataFrame, one row per user-day, saved to CSV.
Run this file directly to produce results/experiment_results.csv, then open
analysis.ipynb to explore it.
"""

import random
from typing import List
import pandas as pd

from personas import PERSONAS, Persona
from trip_generator import Trip, _generate_od_pool, _pick_mode, update_mode_preference
from baseline_models import MODEL_REGISTRY, co2_to_tokens
from engagement_model import init_engagement_state, step_engagement, engagement_to_trip_probability
from config import SIMULATION_DAYS, RANDOM_SEED


def simulate_persona_with_model(
    persona: Persona,
    model_name: str,
    n_days: int = SIMULATION_DAYS,
    seed: int = RANDOM_SEED,
    reward_feedback: bool = False,
) -> pd.DataFrame:
    """
    Runs one full day-by-day simulation for a single persona under a single baseline
    model, with engagement feeding back into trip probability each day. Returns a
    dataframe with one row per day (including no-trip days) for this user.
    """
    model_fn = MODEL_REGISTRY[model_name]
    rng = random.Random(seed)

    od_pool = _generate_od_pool(persona, rng)
    mode_probs = dict(persona.mode_probs)

    state = init_engagement_state(persona.starting_engagement)
    history: List[Trip] = []
    rows = []

    trip_probability_today = persona.trip_frequency

    for day in range(n_days):
        took_trip = rng.random() <= trip_probability_today
        tokens_today = 0.0
        co2_avoided_today = 0.0
        mode_today = None
        distance_today = 0.0

        if took_trip:
            od_pair = rng.choice(od_pool)
            mode = _pick_mode(persona, mode_probs if reward_feedback else None, rng)
            distance = round(rng.uniform(*persona.distance_km_range), 2)
            trip = Trip(user_id=persona.name, day=day, od_pair=od_pair, mode=mode, distance_km=distance)

            co2_avoided = model_fn(trip, history)
            tokens = co2_to_tokens(co2_avoided)

            history.append(trip)
            mode_today = mode
            distance_today = distance
            co2_avoided_today = co2_avoided if co2_avoided is not None else 0.0
            tokens_today = tokens

            if reward_feedback and tokens > 0:
                mode_probs = update_mode_preference(mode_probs, mode)

        state = step_engagement(state, tokens_today, took_trip)
        trip_probability_today = engagement_to_trip_probability(state.engagement, persona.trip_frequency)

        rows.append({
            "persona": persona.name,
            "model": model_name,
            "day": day,
            "took_trip": took_trip,
            "mode": mode_today,
            "distance_km": distance_today,
            "co2_avoided_kg": round(co2_avoided_today, 3),
            "tokens_earned": round(tokens_today, 2),
            "engagement": round(state.engagement, 4),
            "streak_days": state.streak_days,
            "next_day_trip_probability": round(trip_probability_today, 4),
        })

    return pd.DataFrame(rows)


def run_full_experiment(
    n_days: int = SIMULATION_DAYS,
    models: List[str] = None,
    reward_feedback_personas: List[str] = None,
) -> pd.DataFrame:
    """
    Runs every persona through every model and concatenates results.
    reward_feedback_personas: persona names that should have mode choice drift toward
    rewarded modes (defaults to just 'reward_motivated' if not specified).
    """
    models = models or list(MODEL_REGISTRY.keys())
    reward_feedback_personas = reward_feedback_personas or ["reward_motivated"]

    all_results = []
    for persona in PERSONAS:
        for model_name in models:
            use_feedback = persona.name in reward_feedback_personas
            df = simulate_persona_with_model(
                persona, model_name, n_days=n_days, reward_feedback=use_feedback
            )
            all_results.append(df)

    return pd.concat(all_results, ignore_index=True)


def summarize_results(df: pd.DataFrame) -> pd.DataFrame:
    """
    Produces a persona x model summary table: total tokens, avg engagement (last 14
    days), max streak, and number of trip days - the headline comparison metrics.
    """
    summaries = []
    for (persona, model), group in df.groupby(["persona", "model"]):
        last_14 = group[group["day"] >= group["day"].max() - 14]
        summaries.append({
            "persona": persona,
            "model": model,
            "total_tokens": group["tokens_earned"].sum(),
            "total_co2_avoided_kg": group["co2_avoided_kg"].sum(),
            "trip_days": int(group["took_trip"].sum()),
            "final_engagement": group["engagement"].iloc[-1],
            "avg_engagement_last_14d": last_14["engagement"].mean(),
            "max_streak": group["streak_days"].max(),
        })
    return pd.DataFrame(summaries).sort_values(["persona", "model"])


def run_multi_seed_experiment(
    n_seeds: int = 10,
    n_days: int = SIMULATION_DAYS,
    models: List[str] = None,
    reward_feedback_personas: List[str] = None,
    base_seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """
    Runs the full persona x model matrix multiple times with different random seeds,
    then averages the summary metrics across seeds. This is what makes the "which
    model is best" conclusion defensible - a single seed is one possible timeline,
    not a reliable estimate. Returns a persona x model table with mean and std
    for each headline metric, so you can see how much a result varies run to run.
    """
    models = models or list(MODEL_REGISTRY.keys())
    reward_feedback_personas = reward_feedback_personas or ["reward_motivated"]

    all_summaries = []
    for seed_offset in range(n_seeds):
        seed = base_seed + seed_offset
        run_results = []
        for persona in PERSONAS:
            for model_name in models:
                use_feedback = persona.name in reward_feedback_personas
                df = simulate_persona_with_model(
                    persona, model_name, n_days=n_days, seed=seed, reward_feedback=use_feedback
                )
                run_results.append(df)
        run_df = pd.concat(run_results, ignore_index=True)
        run_summary = summarize_results(run_df)
        run_summary["seed"] = seed
        all_summaries.append(run_summary)

    combined = pd.concat(all_summaries, ignore_index=True)

    agg = combined.groupby(["persona", "model"]).agg(
        total_tokens_mean=("total_tokens", "mean"),
        total_tokens_std=("total_tokens", "std"),
        avg_engagement_last_14d_mean=("avg_engagement_last_14d", "mean"),
        avg_engagement_last_14d_std=("avg_engagement_last_14d", "std"),
        max_streak_mean=("max_streak", "mean"),
        max_streak_std=("max_streak", "std"),
    ).reset_index()

    return agg.sort_values(["persona", "avg_engagement_last_14d_mean"], ascending=[True, False])


if __name__ == "__main__":
    import os

    print(f"Running experiment: {len(PERSONAS)} personas x {len(MODEL_REGISTRY)} models x {SIMULATION_DAYS} days...")
    results = run_full_experiment()

    os.makedirs("results", exist_ok=True)
    results.to_csv("results/experiment_results.csv", index=False)
    print(f"Saved {len(results)} rows to results/experiment_results.csv")

    summary = summarize_results(results)
    summary.to_csv("results/experiment_summary.csv", index=False)
    print("\nSingle-seed summary (total tokens, engagement, streaks by persona x model):")
    print(summary.to_string(index=False))

    print("\nRunning multi-seed experiment (10 seeds) for a more reliable comparison...")
    multi_seed_summary = run_multi_seed_experiment(n_seeds=10)
    multi_seed_summary.to_csv("results/experiment_summary_multiseed.csv", index=False)
    print("\nMulti-seed summary (mean +/- std across 10 seeds):")
    print(multi_seed_summary.to_string(index=False))
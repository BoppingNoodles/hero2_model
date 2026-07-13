"""
run_macro_experiment.py
MACRO SIMULATION (team's primary request):

Runs the reward baseline sweep at factor = 0% ("no baseline" - every verified trip earns
Power against the full car reference), 25% (the proposed soft-baseline candidate), 50%,
and 100%, across all 25 persona x archetype combinations.

For statistically meaningful weekly RETENTION (not just one trajectory's engagement
score), each persona x archetype x baseline_factor cell is simulated as a COHORT of
COHORT_SIZE independent synthetic individuals (same behavioral profile, different random
draws), and results are aggregated at the cohort level, week by week.

Weekly metrics produced, per the team's request:
- engagement (average across the cohort)
- retention (fraction of the cohort still "active" that week, engagement > 0.2)
- Power issued (total, and split by verification/improvement/challenge)
- reward cost (total Power issued - a proxy for token liability, no dollar value assumed)
- total sustainable trips
- estimated additional trips (trips that deviated from the user's true baseline mode)

Run this file directly to produce results/macro_weekly.csv and results/macro_summary.csv.
"""

import os
from typing import List
import pandas as pd

from personas import PERSONAS
from archetypes import ARCHETYPES
from simulate_user import simulate_user
from config import BASELINE_FACTORS, SIMULATION_DAYS, COHORT_SIZE, COHORT_BASE_SEED

ACTIVE_ENGAGEMENT_THRESHOLD = 0.2  # engagement above this counts as "retained" for the week


def run_macro_experiment(
    baseline_factors: List[float] = None,
    n_days: int = SIMULATION_DAYS,
    cohort_size: int = COHORT_SIZE,
) -> pd.DataFrame:
    """
    Runs the full macro sweep. Returns a single tidy dataframe, one row per
    (persona, archetype, baseline_factor, cohort_member, day) - the finest grain
    available, aggregated afterward by summarize_weekly().
    """
    baseline_factors = baseline_factors or BASELINE_FACTORS
    all_runs = []

    for persona in PERSONAS:
        for archetype in ARCHETYPES:
            for factor in baseline_factors:
                for member in range(cohort_size):
                    seed = COHORT_BASE_SEED + member
                    df = simulate_user(
                        persona=persona,
                        archetype=archetype,
                        baseline_factor=factor,
                        n_days=n_days,
                        seed=seed,
                        apply_redemption_taper=False,  # macro sweep: no tapering, full redemption value throughout
                    )
                    df["cohort_member"] = member
                    all_runs.append(df)

    return pd.concat(all_runs, ignore_index=True)


def summarize_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates the raw day-level cohort data into weekly metrics per
    (persona, archetype, baseline_factor, week) - the level the requested charts operate at.
    """
    rows = []
    group_cols = ["persona", "archetype", "baseline_factor", "week"]
    for keys, group in df.groupby(group_cols):
        persona, archetype, factor, week = keys
        cohort_size = group["cohort_member"].nunique()

        # Retention: fraction of the cohort with engagement above threshold on the LAST
        # day of this week (a snapshot, consistent week to week).
        last_day_of_week = group["day"].max()
        last_day_rows = group[group["day"] == last_day_of_week]
        retained = (last_day_rows.groupby("cohort_member")["engagement"].last() > ACTIVE_ENGAGEMENT_THRESHOLD).sum()
        retention = retained / cohort_size

        rows.append({
            "persona": persona,
            "archetype": archetype,
            "baseline_factor": factor,
            "week": week,
            "avg_engagement": group["engagement"].mean(),
            "retention": retention,
            "verification_power_issued": group["verification_power"].sum(),
            "improvement_power_issued": group["improvement_power"].sum(),
            "challenge_power_issued": group["challenge_power"].sum(),
            "total_power_issued": group["total_power"].sum(),
            "reward_cost": group["total_power"].sum(),  # Power issued == reward cost proxy (no $ conversion assumed)
            "total_sustainable_trips": int(group["took_trip"].sum()),
            "estimated_additional_trips": int(group["is_additional_trip"].sum()),
            "true_co2_avoided_kg": group["true_co2_avoided_kg"].sum(),
            "reward_co2_avoided_kg": group["reward_co2_avoided_kg"].sum(),
        })

    return pd.DataFrame(rows).sort_values(["persona", "archetype", "baseline_factor", "week"])


def summarize_overall(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Collapses the weekly table further into one row per (persona, archetype, baseline_factor)."""
    rows = []
    group_cols = ["persona", "archetype", "baseline_factor"]
    for keys, group in weekly_df.groupby(group_cols):
        persona, archetype, factor = keys
        last_4_weeks = group[group["week"] >= group["week"].max() - 3]
        rows.append({
            "persona": persona,
            "archetype": archetype,
            "baseline_factor": factor,
            "avg_engagement_last_4wk": last_4_weeks["avg_engagement"].mean(),
            "avg_retention_last_4wk": last_4_weeks["retention"].mean(),
            "total_power_issued": group["total_power_issued"].sum(),
            "total_reward_cost": group["reward_cost"].sum(),
            "total_sustainable_trips": group["total_sustainable_trips"].sum(),
            "total_estimated_additional_trips": group["estimated_additional_trips"].sum(),
            "total_true_co2_avoided_kg": group["true_co2_avoided_kg"].sum(),
            "total_reward_co2_avoided_kg": group["reward_co2_avoided_kg"].sum(),
        })
    return pd.DataFrame(rows).sort_values(["persona", "archetype", "baseline_factor"])


if __name__ == "__main__":
    print(f"Running macro experiment: {len(PERSONAS)} personas x {len(ARCHETYPES)} archetypes x "
          f"{len(BASELINE_FACTORS)} baseline factors x {COHORT_SIZE} cohort members x {SIMULATION_DAYS} days...")
    print("This runs a lot of individual simulations - may take a minute.")

    raw = run_macro_experiment()
    weekly = summarize_weekly(raw)
    overall = summarize_overall(weekly)

    os.makedirs("results", exist_ok=True)
    weekly.to_csv("results/macro_weekly.csv", index=False)
    overall.to_csv("results/macro_summary.csv", index=False)

    print(f"\nSaved {len(weekly)} weekly rows to results/macro_weekly.csv")
    print(f"Saved {len(overall)} summary rows to results/macro_summary.csv")
    print("\nOverall summary (averaged over last 4 weeks of engagement/retention):")
    print(overall.to_string(index=False))

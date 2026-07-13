"""
run_taper_experiment.py
MICRO-TO-MACRO SIMULATION (team's second request):

Tests the core question: "can gamification preserve engagement and sustainable behavior
after the strongest external incentive (redeemable Power) is reduced?"

Runs every persona x archetype combination TWICE at the soft-baseline candidate
(baseline_factor = 0.25): once with redemption value held at 100% throughout, and once
with redemption value tapering down to REDEMPTION_TAPER_FLOOR between
REDEMPTION_TAPER_START_DAY and REDEMPTION_TAPER_END_DAY (config.py). Challenge Power
(streaks/milestones) is unaffected by the taper in both runs.

Comparing the two conditions, per archetype, is what answers the team's question -
if an archetype's engagement holds up close to the no-taper condition, that's evidence
gamification alone can substitute for shrinking token value for that user type.

Run this file directly to produce results/taper_weekly.csv and results/taper_summary_by_archetype.csv.
"""

import os
import pandas as pd

from personas import PERSONAS
from archetypes import ARCHETYPES
from simulate_user import simulate_user
from run_macro_experiment import ACTIVE_ENGAGEMENT_THRESHOLD
from config import SIMULATION_DAYS, COHORT_SIZE, COHORT_BASE_SEED, SOFT_BASELINE_CANDIDATE


def run_taper_experiment(
    baseline_factor: float = SOFT_BASELINE_CANDIDATE,
    n_days: int = SIMULATION_DAYS,
    cohort_size: int = COHORT_SIZE,
) -> pd.DataFrame:
    """
    Runs every persona x archetype combination under both taper conditions
    (no_taper, tapered), as a cohort, at the given baseline_factor. Returns raw
    day-level data with a 'condition' column distinguishing the two runs.
    """
    all_runs = []

    for persona in PERSONAS:
        for archetype in ARCHETYPES:
            for condition, apply_taper in [("no_taper", False), ("tapered", True)]:
                for member in range(cohort_size):
                    seed = COHORT_BASE_SEED + member
                    df = simulate_user(
                        persona=persona,
                        archetype=archetype,
                        baseline_factor=baseline_factor,
                        n_days=n_days,
                        seed=seed,
                        apply_redemption_taper=apply_taper,
                    )
                    df["cohort_member"] = member
                    df["condition"] = condition
                    all_runs.append(df)

    return pd.concat(all_runs, ignore_index=True)


def summarize_taper_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Same weekly aggregation as the macro experiment, but grouped by condition instead of baseline_factor."""
    rows = []
    group_cols = ["persona", "archetype", "condition", "week"]
    for keys, group in df.groupby(group_cols):
        persona, archetype, condition, week = keys
        cohort_size = group["cohort_member"].nunique()
        last_day_of_week = group["day"].max()
        last_day_rows = group[group["day"] == last_day_of_week]
        retained = (last_day_rows.groupby("cohort_member")["engagement"].last() > ACTIVE_ENGAGEMENT_THRESHOLD).sum()
        retention = retained / cohort_size

        rows.append({
            "persona": persona,
            "archetype": archetype,
            "condition": condition,
            "week": week,
            "avg_engagement": group["engagement"].mean(),
            "retention": retention,
            "total_power_issued": group["total_power"].sum(),
            "total_sustainable_trips": int(group["took_trip"].sum()),
            "avg_redemption_multiplier": group["redemption_multiplier"].mean(),
        })

    return pd.DataFrame(rows).sort_values(["persona", "archetype", "condition", "week"])


def summarize_taper_by_archetype(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapses across personas to give one row per (archetype, condition) - the
    headline comparison for the team's core question, averaged over the final 4 weeks
    (after the taper has fully completed, since taper ends at REDEMPTION_TAPER_END_DAY).
    """
    rows = []
    for (archetype, condition), group in weekly_df.groupby(["archetype", "condition"]):
        last_4_weeks = group[group["week"] >= group["week"].max() - 3]
        rows.append({
            "archetype": archetype,
            "condition": condition,
            "avg_engagement_last_4wk": last_4_weeks["avg_engagement"].mean(),
            "avg_retention_last_4wk": last_4_weeks["retention"].mean(),
        })
    result = pd.DataFrame(rows)

    # Add an "engagement retained" column: tapered engagement as a % of no-taper engagement,
    # per archetype - this is the single number that most directly answers the team's question.
    pivot = result.pivot(index="archetype", columns="condition", values="avg_engagement_last_4wk")
    pivot["pct_engagement_retained_under_taper"] = (pivot["tapered"] / pivot["no_taper"] * 100).round(1)
    return pivot.reset_index().sort_values("pct_engagement_retained_under_taper", ascending=False)


if __name__ == "__main__":
    print(f"Running taper experiment at baseline_factor={SOFT_BASELINE_CANDIDATE}: "
          f"{len(PERSONAS)} personas x {len(ARCHETYPES)} archetypes x 2 conditions x "
          f"{COHORT_SIZE} cohort members x {SIMULATION_DAYS} days...")

    raw = run_taper_experiment()
    weekly = summarize_taper_weekly(raw)
    by_archetype = summarize_taper_by_archetype(weekly)

    os.makedirs("results", exist_ok=True)
    weekly.to_csv("results/taper_weekly.csv", index=False)
    by_archetype.to_csv("results/taper_summary_by_archetype.csv", index=False)

    print(f"\nSaved {len(weekly)} weekly rows to results/taper_weekly.csv")
    print("\nEngagement retained under redemption taper, by archetype (headline result):")
    print(by_archetype.to_string(index=False))

"""
config.py
Central place for constants used across the simulation.
Tune these to run sensitivity analyses without touching model logic.
"""

# --- Emissions assumptions (from Token Framework Proposal) ---
CAR_EMISSION_FACTOR_KG_PER_KM = 0.18  # midpoint of the 0.1-0.25 kg/km range in the proposal
MODE_EMISSION_FACTORS = {
    # kg CO2 per km, by transport mode
    "car": 0.18,
    "carpool": 0.09,       # roughly half of solo car, shared emissions
    "bus": 0.05,
    "train": 0.04,
    "bike": 0.0,
    "walk": 0.0,
}

# --- Token conversion (Table 2 in proposal): 1kg CO2 avoided = 5 tokens ---
CO2_TO_TOKEN_RATE = 5  # tokens per kg CO2 avoided

# --- Historical baseline model ---
HISTORICAL_WINDOW_DAYS = 14  # rolling window length (test 7 / 14 / 30 for sensitivity)
MIN_TRIPS_FOR_HISTORICAL_BASELINE = 3  # cold-start floor before this model activates

# --- Matched-trip baseline model ---
MIN_MODES_FOR_MATCH = 2  # need >=2 different modes on the same OD pair to compute a match

# --- Light-baseline model (macro simulation request) ---
# reference_per_km = (1 - factor) * car_factor + factor * user_historical_avg_per_km
# factor = 0.0   -> identical to counterfactual (no baseline deduction at all - "no baseline" model)
# factor = 1.0   -> reference fully anchored to the user's own historical average
# If the user has no trip history yet, the historical component falls back to the car
# factor automatically (see baseline_models.light_baseline), so this model never has a
# cold-start gap the way the pure historical model does.
BASELINE_FACTORS = [0.0, 0.25, 0.5, 1.0]
SOFT_BASELINE_CANDIDATE = 0.25  # the company's proposed initial soft-baseline setting

# --- Token split (Micro-to-macro request) ---
# Power is now split into three components instead of one combined value.
VERIFICATION_POWER_PER_TRIP = 5     # flat Power for any verified sustainable trip (Table 3: "validate own trip")
# Improvement Power uses the existing CO2_TO_TOKEN_RATE, applied to reduction ABOVE
# whichever reward baseline is active (light_baseline at the configured factor).
CHALLENGE_POWER_STREAK_MILESTONES = {3: 10, 7: 15, 30: 20}   # streak_days -> bonus Power (Table 3)
CHALLENGE_POWER_TRIP_MILESTONES = {10: 15, 20: 20, 50: 25}   # cumulative trip count -> bonus Power (Table 3)
# NOTE: leaderboard-position bonuses from the proposal are NOT modeled here - they require
# simulating a full population competing simultaneously, which this single-user-at-a-time
# simulation structure doesn't support. Flagged as a known gap, not silently omitted.

# --- Engagement model: base mechanics (unchanged from v1) ---
ENGAGEMENT_START = 0.5          # initial engagement score, 0-1 scale
ENGAGEMENT_DECAY_PER_DAY = 0.03 # decay applied each day with no rewarded trip
ENGAGEMENT_REWARD_GAIN = 0.02   # engagement gain per token earned (scaled, see engagement_model.py)
ENGAGEMENT_REWARD_GAIN_SATURATION = 40  # tokens at which marginal engagement gain starts flattening
STREAK_BONUS_MULTIPLIER = 1.3   # multiplier on engagement gain while on an active streak
MIN_TRIP_PROBABILITY = 0.05     # floor so simulated users never have exactly 0% trip chance
MAX_TRIP_PROBABILITY = 0.95     # ceiling so no user is guaranteed to trip every day

# --- Habit conversion (micro-to-macro request) ---
# Represents intrinsic motivation gradually replacing reward-driven motivation.
# 21 days is a commonly cited (though contested) rough heuristic for habit formation;
# used here as a defensible starting assumption, not a validated figure for this app.
HABIT_CONVERSION_STREAK_THRESHOLD = 21   # minimum consecutive rewarded days before conversion can occur
HABIT_DECAY_REDUCTION_FACTOR = 0.3       # once habitual, daily decay is multiplied by this (i.e. decays slower)

# --- Redemption value tapering (micro-to-macro request) ---
# Simulates the redeemable/token value shrinking over time while challenge Power
# (streaks, leaderboard, milestones) keeps functioning normally.
REDEMPTION_TAPER_START_DAY = 30
REDEMPTION_TAPER_END_DAY = 60
REDEMPTION_TAPER_FLOOR = 0.2   # redemption value shrinks linearly to 20% of original by day 60, then holds

# --- Cohort simulation settings (for population-style retention metrics) ---
COHORT_SIZE = 20   # number of independent synthetic individuals simulated per persona x archetype cell
COHORT_BASE_SEED = 1000

# --- Simulation run settings ---
SIMULATION_DAYS = 90
RANDOM_SEED = 42

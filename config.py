"""
Place for constants used across the simulation
"""
CAR_EMISSION_FACTOR_KG_PER_KM = 0.18

MODE_EMISSION_FACTORS = {
    "car": 0.18,
    "bus": 0.05,
    "train": 0.04,
    "bike": 0.0,
    "walk": 0.0,
}

# Token conversion
CO2_To_Token_RATE = 5

# Historical Baseline Model
HISTORICAL_WINDOW_DAYS = 14
MIN_TRIPS_FOR_HISTORICAL_BASELINE = 3

# Matched Trip Baseline Model
MIN_TRANSPORT_MODES = 2

# Engagement Model
ENGAGEMENT_START = 0.5
ENGAGEMENT_DECAY_PER_DAY = 0.03
ENGAGEMENT_REWARD_GAIN = 0.02
ENGAGEMENT_REWARD_GAIN_SATURATION = 40
STREAK_BONUS_MULTIPLIER = 1.3
MIN_TRIP_PROBABILITY = 0.05
MAX_TRIP_PROBABILITY = 0.95

# Simulation Run Settings
SIMULATION_DAYS = 90
RANDOM_SEED = 42
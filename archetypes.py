"""
archetypes.py
Defines WHY a synthetic user is motivated - separate from personas.py, which defines WHAT
mode they travel by. Layering these two lets the simulation ask questions like "does a
Gamer who mostly carpools behave differently from an Earner who mostly carpools?"

Each archetype specifies four parameters, all requested by the team:

- reward_sensitivity: multiplier on how much verification + improvement Power (the
  redeemable, token-value part of Power) contributes to engagement gain. 1.0 = baseline
  (matches the original v1 engagement model exactly). Above 1.0 = more responsive to
  token/redemption value; below 1.0 = less responsive.

- gamification_sensitivity: multiplier on how much challenge Power (streaks, milestones)
  contributes to engagement gain, evaluated separately from reward_sensitivity above.

- habit_conversion_probability: daily probability (while on a streak of
  HABIT_CONVERSION_STREAK_THRESHOLD days or longer) that this user "converts" to
  intrinsically-motivated/habitual behavior. Once converted, daily engagement decay is
  reduced (see engagement_model.py) - representing the idea that some users' sustainable
  behavior becomes self-sustaining and less dependent on the reward system over time.

- post_incentive_decay_multiplier: multiplier applied to the user's normal daily decay
  rate specifically while redemption value is tapered (see REDEMPTION_TAPER_* in
  config.py). Above 1.0 = decays faster than normal when rewards shrink (more
  reward-dependent); below 1.0 = decays slower (less affected by the taper).

These are assumptions, not measured values - see README for how to treat them.
"""

from dataclasses import dataclass


@dataclass
class Archetype:
    name: str
    reward_sensitivity: float
    gamification_sensitivity: float
    habit_conversion_probability: float
    post_incentive_decay_multiplier: float
    description: str


ARCHETYPES = [
    Archetype(
        name="Mover",
        # Motivated primarily by the activity/impact itself, not the token value.
        # Least reliant on reward, most likely to form a lasting habit.
        reward_sensitivity=0.6,
        gamification_sensitivity=0.5,
        habit_conversion_probability=0.05,
        post_incentive_decay_multiplier=0.7,
        description="Motivated by the activity and its impact more than the reward itself.",
    ),
    Archetype(
        name="Earner",
        # Motivated primarily by token/redemption value. Most reward-dependent archetype -
        # expected to be hit hardest by the redemption tapering scenario.
        reward_sensitivity=1.4,
        gamification_sensitivity=0.4,
        habit_conversion_probability=0.01,
        post_incentive_decay_multiplier=1.6,
        description="Motivated primarily by redeemable token value.",
    ),
    Archetype(
        name="Saver",
        # Motivated by accumulating Power toward larger, delayed rewards. Responsive to
        # reward but more patient than an Earner; moderate habit formation.
        reward_sensitivity=1.1,
        gamification_sensitivity=0.6,
        habit_conversion_probability=0.02,
        post_incentive_decay_multiplier=1.2,
        description="Motivated by accumulating Power toward larger, delayed rewards.",
    ),
    Archetype(
        name="Gamer",
        # Motivated by streaks, leaderboards, and challenge mechanics rather than token
        # value itself - expected to be relatively insulated from redemption tapering.
        reward_sensitivity=0.5,
        gamification_sensitivity=1.5,
        habit_conversion_probability=0.03,
        post_incentive_decay_multiplier=0.8,
        description="Motivated by streaks, leaderboards, milestones, and competition.",
    ),
    Archetype(
        name="Hybrid",
        # Neutral on every axis - this is the archetype that reproduces the original
        # v1 engagement model's behavior exactly, useful as a control/reference case.
        reward_sensitivity=1.0,
        gamification_sensitivity=1.0,
        habit_conversion_probability=0.02,
        post_incentive_decay_multiplier=1.0,
        description="Balanced across reward and gamification motivations (control case).",
    ),
]


def get_archetype(name: str) -> Archetype:
    for a in ARCHETYPES:
        if a.name == name:
            return a
    raise ValueError(f"Unknown archetype: {name}")

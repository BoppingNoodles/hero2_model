# Power Token Simulation v2: Baseline Sweep + Gamification Tapering

Extends the original 3-model simulation into two new experiments requested by the team:

1. **Macro simulation:** tests a "no baseline" reward model (every verified sustainable
   trip earns Power) against a **light-baseline** model where only a portion of the
   user's own historical baseline is deducted from reward eligibility (0%, 25%, 50%,
   100%), while environmental impact is always calculated against the full counterfactual
   regardless of the reward baseline used.
2. **Micro-to-macro simulation:** splits Power into verification / improvement / challenge
   components, adds 5 motivation archetypes (Mover, Earner, Saver, Gamer, Hybrid) layered
   on top of the 5 existing transport-mode personas, and tests whether gamification
   (streaks, milestones) can sustain engagement once redeemable token value tapers.

## Setup

```bash
pip install pandas matplotlib jupyter
```

## Run

```bash
python run_macro_experiment.py    # baseline factor sweep -> results/macro_weekly.csv, results/macro_summary.csv
python run_taper_experiment.py    # redemption tapering by archetype -> results/taper_weekly.csv, results/taper_summary_by_archetype.csv
```

Then open `analysis.ipynb` for the charts. Each experiment simulates a **cohort** of
independent synthetic individuals per persona x archetype cell (`COHORT_SIZE` in
`config.py`, default 20) rather than a single trajectory, so retention and engagement
numbers reflect a population, not one noisy run.

## File guide

| File | Purpose |
|---|---|
| `config.py` | All tunable constants: emission factors, baseline factors to sweep, token-split amounts, archetype/habit/taper parameters, cohort size. |
| `personas.py` | WHAT a user does - transport mode mix, trip frequency, route pool (unchanged from v1). |
| `archetypes.py` | **New.** WHY a user is motivated - Mover, Earner, Saver, Gamer, Hybrid, each with reward sensitivity, gamification sensitivity, habit-conversion probability, and post-incentive decay. |
| `trip_generator.py` | Generates a trip (route, mode, distance) for a persona on a given day (unchanged from v1). |
| `baseline_models.py` | The original counterfactual/historical/matched-trip models and hybrids, plus the **new `light_baseline()`** (parameterized macro model) and `true_environmental_impact()` (always the full counterfactual, tracked separately from the reward). |
| `token_model.py` | **New.** Splits Power into verification (flat, per trip), improvement (proportional to reduction above the reward baseline), and challenge (streak/milestone bonuses). Also flags "additional trips." |
| `engagement_model.py` | Extended to evaluate reward-driven and gamification-driven Power as two separate gain terms (each scaled by the archetype's sensitivities), plus habit conversion and redemption-value tapering. |
| `simulate_user.py` | **New.** The shared day-by-day loop for one synthetic individual, used by both experiments below. |
| `run_macro_experiment.py` | **New.** Runs the baseline factor sweep (0/25/50/100%) across all persona x archetype cohorts, aggregated weekly. |
| `run_taper_experiment.py` | **New.** Runs every persona x archetype twice (with/without redemption tapering) at the 25% soft-baseline candidate, to test the gamification question. |
| `analysis.ipynb` | All requested charts: weekly engagement/retention/Power issuance/reward cost/sustainable trips/additional trips by baseline factor, plus the tapering comparison by archetype. |

## Findings

### Part 1: Baseline factor sweep (0%, 25%, 50%, 100%)

**Result 1: Engagement and retention stay roughly flat across baseline factors, for most personas.**
Because Power is now split into three components, verification Power (a flat amount awarded for any verified trip) and challenge Power (streak/milestone bonuses) are **unaffected by the baseline factor** - only improvement Power shrinks as the factor increases. For personas with frequent trips (`transit_loyalist`, `walker_biker`, `carpooler`), verification and challenge Power alone are usually enough to keep engagement high regardless of which baseline factor is active. This is a structural change from the original simulation, where a single combined token value drove engagement directly.

**Result 2: The baseline factor's real effect shows up in reward cost, not engagement.**
Total Power issued (summed across every persona/archetype) drops from 370,907 at 0% baseline to 260,253 at 100% baseline - a 30% reduction in token liability - while engagement stayed close to flat per Result 1. This is the core tradeoff the team was asking about: a softer baseline factor reduces cost without much visible cost to engagement, for most user types.

**Result 3: True environmental impact stays constant across baseline factors; reward-credited impact does not.**
Total true CO2 avoided (calculated against the full counterfactual, regardless of reward baseline) stayed within about 1% across all four factors (~27,000-27,100 kg). Reward-credited CO2 avoided, by contrast, dropped sharply: 27,117 kg at 0% baseline down to 5,793 kg at 100% baseline. This confirms the environmental accounting and the reward accounting are properly decoupled, as the team requested - the app can report accurate impact numbers regardless of how generous or conservative the reward baseline is.

**Result 4: Estimated additional trips stayed at roughly 67% of all sustainable trips, regardless of baseline factor.**
This proxy (trips where the mode differs from the persona's true baseline mode) didn't meaningfully shift across baseline factors - suggesting the baseline factor mainly affects how much reward a trip earns, not whether the trip happens at all, at least under this simulation's assumptions about how engagement translates into trip probability.

**Result 5: Not every persona is insulated from the baseline factor.**
`reward_motivated` and `carpooler` personas (whose behavior is more tied to their improvement Power) show a real engagement decline as the factor increases - e.g. `reward_motivated` + `Mover` archetype drops from 0.177 average engagement at 0% baseline to 0.105 at 100%. These are the personas/archetypes worth watching most closely if a harder baseline factor is considered later.

### Part 2: Gamification tapering (at the 25% soft-baseline candidate)

**Result 6: Gamification-driven archetypes are the most resilient to redemption tapering; reward-driven archetypes are the least.**
Averaged over the last 4 weeks of the simulation (after the taper has fully completed):

| Archetype | Engagement retained under taper |
|---|---|
| Gamer | 99.5% |
| Mover | 99.1% |
| Hybrid | 97.9% |
| Saver | 94.3% |
| Earner | 91.8% |

This is a direct answer to the team's core question: gamification mechanics (streaks, milestones) do measurably help sustain engagement as redeemable token value shrinks, and the effect is strongest for Gamer and Mover archetypes (who are less dependent on token value to begin with, by construction). Earner archetypes - defined specifically as the most reward-dependent - show the largest, though still fairly small, drop (about 8 percentage points).

**Caveat on Result 6:** the gap between "most resilient" and "least resilient" archetypes (99.5% vs 91.8%) is smaller than might be expected. This is a direct consequence of how the archetypes were parameterized (see `archetypes.py`) - the sensitivity and decay multipliers are assumptions, not calibrated to real user data. A team member reviewing this should treat the *ranking* (Gamer/Mover most resilient, Earner least) as the more defensible takeaway than the exact percentages.


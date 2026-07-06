# Power Token Baseline Model Simulator

Simulates three carbon-reduction baseline models from the emissions research paper —
**counterfactual**, **historical**, and **matched-trip** — plus two hybrids
(**waterfall** and **weighted ensemble**), across five synthetic user personas, to
compare which model best sustains user engagement.

## Setup

```bash
pip install pandas matplotlib jupyter
```

## Run

```bash
python run_experiment.py
```

This generates:
- `results/experiment_results.csv` — day-by-day, single seed, per user
- `results/experiment_summary.csv` — single-seed totals per persona x model
- `results/experiment_summary_multiseed.csv` — **the defensible one** — mean and std of headline metrics across 10 random seeds per persona x model

Then open `analysis.ipynb` to explore plots (both single-seed and multi-seed versions are included).

## File guide

| File | Purpose | Logistics |
|---|---|---|
| `config.py` | Single source of truth for every tunable assumption (emission factors, token conversion rate, engagement decay/gain, window sizes). | No logic, just constants. Every other file imports from here — change a value once, it propagates everywhere. Start here for sensitivity analysis. |
| `personas.py` | Defines the 5 synthetic user archetypes (walker/biker, carpooler, transit loyalist, casual/inconsistent, reward-motivated) as pure data. | A `Persona` dataclass + 5 instances. No simulation logic — just probability profiles (mode choice, trip frequency, route pool size) that `run_experiment.py` loops over. |
| `trip_generator.py` | Turns a persona's probabilities into an actual simulated trip (route, mode, distance) on a given day. | Builds each user's fixed OD-pair pool (needed for matched-trip to ever activate) and handles the mode-preference drift used by `reward_motivated`. |
| `baseline_models.py` | Implements the 3 models from the research paper (counterfactual, historical, matched-trip) + 2 hybrids (waterfall, weighted), plus CO2→token conversion. | Each model function takes a trip + history, returns kg CO2 avoided or `None` if not yet computable (that `None` vs `0.0` distinction is what drives the waterfall finding below). |
| `engagement_model.py` | Converts tokens earned into an engagement score, which feeds back into next-day trip probability. | **Most assumption-heavy module in the project** — decay/gain/streak-bonus constants have no real data behind them. Read the docstring before trusting results. |
| `run_experiment.py` | Orchestrates the full persona × model matrix (5×5=25 runs), single-seed and multi-seed (10 seeds averaged). | Run directly (`python run_experiment.py`) to regenerate all three result CSVs. |
| `analysis.ipynb` | Visualizes and interprets the CSVs — engagement-over-time plots, single-seed and multi-seed persona×model heatmaps, streak comparisons, fairness checks. | Run after `run_experiment.py`. This is where the "which model is best" question actually gets answered — and complicated. |

## Findings (validated across 10 random seeds)

These results are averaged across 10 simulation runs per persona/model combination (not a single run), so they reflect a consistent pattern rather than one-time noise. Full numbers are in `results/experiment_summary_multiseed.csv`.

**What "engagement" means here:** a score from 0 to 1 representing how likely a simulated user is to keep using the app. Higher is better. It goes up when a user earns tokens and goes down on days they earn nothing.

**Result 1: The counterfactual model produces the highest engagement for users who are already very sustainable.**
For `transit_loyalist` (a persona that already exclusively uses bus and train), the counterfactual model produces an average engagement of 0.997 out of 1.0. For `walker_biker` (a persona that mostly walks and bikes), it produces an average of 0.610. Both are far higher than any other model produces for these two personas.

**Result 2: This model rewards users for emissions reductions they may not have actually made.**
The counterfactual model calculates tokens by comparing a trip against what a car would have emitted — regardless of what the user would have actually done instead. The research paper identifies this exact issue as a known limitation: a user who would not have driven anyway still receives credit as if they had. `transit_loyalist`'s real alternative is a bus, not a car, so the high engagement score in Result 1 is a byproduct of this over-crediting, not a sign that the model is measuring anything more accurate.

**Result 3: The historical and matched-trip models award close to zero tokens to already-sustainable users, once those users have enough trip history.**
Both models measure improvement relative to a user's own past behavior. A user who consistently walks or bikes has no further improvement to show relative to their own history, so these models correctly calculate zero additional credit for them. The result is that already-sustainable users earn almost no tokens under these two models, and their engagement scores drop close to zero (under 0.02 for both `transit_loyalist` and `walker_biker`, across all 10 seeds).

**Result 4: The hybrid_waterfall model behaves the same way as historical/matched-trip for already-sustainable users, not like counterfactual.**
Although hybrid_waterfall is designed to fall back to the counterfactual model when other models can't produce a value, it does not do so in this case. Historical and matched-trip both return a valid value of exactly 0 tokens for these users (not "no value"), so the waterfall model treats that as a usable result and never reaches the counterfactual fallback. Its engagement scores for `transit_loyalist` and `walker_biker` end up close to zero, similar to historical and matched-trip, rather than close to counterfactual.

**Result 5: The hybrid_weighted model produces a middle-ground result.**
It averages 0.578 engagement for `transit_loyalist` and 0.160 for `walker_biker` — lower than counterfactual, but clearly higher than historical, matched-trip, and hybrid_waterfall for these two personas. This model combines all available model outputs rather than picking one, so it continues to award some tokens from the counterfactual calculation even when historical/matched-trip contribute zero.

**Result 6: For personas that are not already highly sustainable (carpooler, casual_inconsistent, reward_motivated), no model produces strong engagement, and the differences between models are small.**
All five models stay under roughly 0.02 average engagement for these three personas. These users have lower baseline trip frequency and lower reward amounts to begin with, and the over-crediting issue described in Result 2 does not apply to them in the same way, since they were not already fully sustainable before using the app.

**Summary:** the counterfactual model produces the strongest engagement numbers in this simulation, but specifically for users who were already highly sustainable before using the app (gives those users credit for emissions reductions they likely didn't make). The historical and matched-trip models avoid that over-crediting but, as a side effect, give almost no ongoing reward to those same already-sustainable users. This is a real design tradeoff for the token system: reward accuracy and reward-driven engagement pull in opposite directions for this specific group of users. The two hybrid approaches sit at different points along that tradeoff rather than resolving it.


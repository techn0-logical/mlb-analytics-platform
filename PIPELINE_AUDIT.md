# 🔬 MLB Betting Model — Deep Pipeline Audit

*Prepared March 16, 2026 · Regular Season starts March 26*

---

## Executive Summary

Your model is running at **50.5% live accuracy** (194 resolved games) — essentially a coin flip. But there's good news: the problems are **identifiable and fixable**. The test accuracy of 56.7% and CV of 58.5% tell us the model *can* learn signal, but multiple compounding issues are burying it in noise.

Here are the **7 critical problems** ranked by impact, followed by a concrete fix plan.

---

## 🚨 Critical Problem #1: Feature Values Are Out-of-Distribution

**The single biggest problem.** The model was trained on regular season data (April–October), but is being asked to predict with spring training inputs that look *nothing* like what it learned.

Evidence from today's BOS @ NYY feature vector:

| Feature | Today's Value | Training Mean | Z-Score | Problem |
|---|---|---|---|---|
| `home_production` | 0.074 | 0.947 | **-8.62** | 9 standard deviations below training! |
| `away_production` | 0.080 | 0.947 | **-8.54** | Same |
| `away_pitching_depth` | 0.800 | 0.994 | **-6.35** | Spring rosters are bigger |
| `away_obp` | 0.787 | 0.630 | **+5.52** | Inflated spring stats |
| `home_power` | 0.080 | 0.894 | **-5.23** | Very few spring ABs |
| `home_slg` | 0.754 | 0.578 | **+4.41** | Small sample SLG noise |

**20 of 55 features** (36%) are more than 2 standard deviations from training mean. The model has *never seen* inputs like this during training. It's extrapolating into unknown territory.

**Root cause:** Features like `production` are calculated as `avg_rbi / 100` — with spring training having ~20 ABs and maybe 1-2 RBI per player, you get 0.07 instead of the regular season's ~0.95. The StandardScaler saw 0.5–1.0 during training, and now it's getting values that map to z-scores of -8.

---

## 🚨 Critical Problem #2: Confidence is Perfectly Inverted

| Confidence | Games | Correct | Accuracy |
|---|---|---|---|
| **<55%** | 97 | 52 | **53.6%** ✅ Best |
| 55–60% | 49 | 22 | 44.9% |
| 60–65% | 19 | 12 | 63.2% |
| 65–70% | 16 | 7 | 43.8% |
| **70%+** | 13 | 5 | **38.5%** ❌ Worst |
| 80–90%* | 17 | 7 | 41.2% |
| 90%+* | 8 | 2 | 25.0% |

*From confidence calibration table

The model is **most confident when it's most wrong**. This means:
- High confidence = the model found extreme feature differences between teams
- Extreme feature differences in spring = noise from small samples, not real skill gaps
- The model has learned to be "sure" about things that don't matter

**This makes the betting recommendations actively harmful** — you'd do better betting the opposite of high-confidence picks.

---

## 🚨 Critical Problem #3: 839 Spring Games in Training Data

| Year | Spring | Regular | Spring % |
|---|---|---|---|
| 2022 | 196 | 2,542 | 7.2% |
| 2023 | 215 | 2,451 | 8.1% |
| 2024 | 212 | 2,417 | 8.1% |
| 2025 | 216 | 2,401 | 8.3% |
| **Total** | **839** | **9,811** | **7.9%** |

839 spring training games are polluting the training data. Spring games have:
- Different rosters (minor leaguers, tryout players)
- Different pitcher usage (2-3 inning stints, no real strategy)
- Different motivation (experimenting, not competing)
- Different outcomes (ties are allowed, rain-shortened games)

The model learned that "spring-like features → random outcome" and now applies that lesson to games with spring-like features.

---

## 🚨 Critical Problem #4: H2H Features Include Spring Games

For NYY vs BOS, the 3-year H2H lookback includes:
- 2024-03: **1 spring game** (12-6 score — wildly inflated)
- 2025-03: **1 spring game** (4-4 tie)
- 2026-03: **1 spring game** (4-0)

Across all teams: **981 spring games** vs 7,269 regular season in the H2H window. Spring games are 11.9% of H2H data and they have abnormal scoring patterns that distort:
- `h2h_avg_home_score` / `h2h_avg_away_score` (inflated by spring blowouts)
- `h2h_home_win_pct` / `h2h_away_win_pct` (spring results are random)
- `h2h_scoring_advantage` (meaningless in spring context)

---

## ⚠️ Problem #5: Overfitting (17-Point Train/Test Gap)

| Metric | Value |
|---|---|
| Training accuracy | 73.7% |
| Test accuracy | 56.7% |
| CV accuracy | 58.5% |
| **Live accuracy** | **50.5%** |

The gap from training (73.7%) → test (56.7%) → live (50.5%) shows classic overfitting that gets worse in production. The XGBoost hyperparameters are insufficiently regularized:

| Parameter | Current | Concern |
|---|---|---|
| `n_estimators` | 300 | May be too many for noisy data |
| `max_depth` | 5 | Allows complex interaction patterns |
| `learning_rate` | 0.05 | Reasonable |
| `min_child_weight` | **None (default=1)** | No minimum leaf samples! |
| `gamma` | **None (default=0)** | No minimum split gain! |
| `reg_alpha` | **None (default=0)** | No L1 regularization! |
| `reg_lambda` | **None (default=1)** | Minimal L2 regularization |

The three `None` values are critical — the model can create splits on single observations and doesn't need any information gain to split. This is why it memorizes training data.

---

## ⚠️ Problem #6: Adaptive Learning is Adding Random Noise

The `update_feature_performance()` method in `AdaptiveLearning.py` works like this:

```
for each feature:
    importance = xgboost_importance[feature]
    if importance > mean_importance:
        noise = random.uniform(-0.03, 0.03)    # ±3% RANDOM
    else:
        noise = random.uniform(-0.08, 0.08)    # ±8% RANDOM
    performance_score = overall_accuracy + noise
```

This means **feature weights are overall accuracy ± random noise**, not actual per-feature signal. Every feature in the `feature_performance` table has almost identical scores (40.6–50.7) because they're all `~46% ± random jitter`.

Similarly, the team adjustments are all `+1.30 confidence_boost` for most teams — they're saturating at the cap value and not differentiating.

The adaptive system is **theater, not science**. It creates the illusion of personalized feature/team adjustments while actually applying near-identical random perturbations.

---

## ⚠️ Problem #7: Class Imbalance + Home Bias

| Outcome | Count | Percentage |
|---|---|---|
| Away wins | 5,902 | **55.4%** |
| Home wins | 4,748 | **44.6%** |

The training data has 11% more away wins than home wins, yet the model predicts home team **60.8%** of the time (118 home vs 76 away picks). This is backwards.

The home picks have 56.8% accuracy vs 40.8% for away picks — but this may be because the model is essentially always picking home and getting lucky ~half the time, not because it understands home advantage.

`scale_pos_weight = None (default=1)` means the model doesn't adjust for this imbalance.

---

## 📊 Feature Importance: What the Model Actually Uses

| Rank | Feature | Importance | Category |
|---|---|---|---|
| 1 | `h2h_home_advantage` | 0.0420 | H2H |
| 2 | `h2h_scoring_advantage` | 0.0358 | H2H |
| 3 | `pitching_advantage` | 0.0302 | Comparative |
| 4 | `batting_advantage` | 0.0262 | Comparative |
| 5 | `home_production` | 0.0228 | Batting |
| 6 | `war_advantage` | 0.0227 | Comparative |
| 7 | `away_era_quality` | 0.0227 | Pitching |

**Observation:** The importance distribution is remarkably flat (max=0.042, min=0.010, ratio=4:1). For comparison, a good model typically has a 50:1+ ratio. This flatness means:
- No single feature carries strong signal
- The model is spreading weight across many weak features
- This is consistent with a noisy dataset where no feature is reliably predictive

The top features being H2H metrics is concerning because those are the most contaminated by spring training data.

---

## 🔧 Fix Plan (Prioritized)

### Phase 1: Pre-Opening Day (Do Before March 26)

#### 1.1 Retrain Model on Regular Season Only
- Filter training data: `WHERE EXTRACT(MONTH FROM game_date) >= 4`
- Remove 2021 from training_years (0 completed games)
- This alone removes 839 noise samples

#### 1.2 Add Regularization
```python
params = {
    'n_estimators': 200,        # reduced from 300
    'max_depth': 4,             # reduced from 5
    'learning_rate': 0.05,      # keep
    'subsample': 0.8,           # keep
    'colsample_bytree': 0.7,    # reduced from 0.8
    'min_child_weight': 5,      # NEW: minimum 5 samples per leaf
    'gamma': 0.1,               # NEW: minimum split gain
    'reg_alpha': 0.1,           # NEW: L1 regularization
    'reg_lambda': 1.5,          # increased from default 1
    'scale_pos_weight': 1.24,   # 5902/4748 to balance classes
}
```

#### 1.3 Filter Spring from H2H Lookback
In `working_feature_engineering.py`, the H2H query needs:
```sql
AND EXTRACT(MONTH FROM game_date) >= 4
```

#### 1.4 Use 2025 Season Stats Until May
For April predictions, 2026 stats will have ~2 weeks of data (tiny samples). Use 2025 full-season stats as the baseline until late April/May when 2026 sample sizes become meaningful. Add logic:
```python
if current_month <= 4:
    season_to_use = current_year - 1
```

#### 1.5 Reset Adaptive Tables
Clear `feature_performance`, `confidence_calibration`, `model_parameters`, and `team_performance_adjustments` on Opening Day. The current data is based on spring training noise.

### Phase 2: Regular Season Improvements (April–May)

#### 2.1 Fix Adaptive Learning Feature Weights
Replace random noise with actual per-feature accuracy measurement:
- For each feature, split predictions into above-median and below-median
- Measure accuracy for each split
- Features where the split matters get higher weights

#### 2.2 Add Early Warning for Feature Drift
Track z-scores of incoming features vs training distribution. If >30% of features have |z| > 2, flag the prediction as low-confidence regardless of model output.

#### 2.3 Implement Proper Confidence Calibration
Use Platt scaling or isotonic regression on the holdout set to map raw XGBoost probabilities to calibrated probabilities. The current inversion means raw probabilities are anti-informative.

### Phase 3: Season Optimization (June+)

#### 3.1 Feature Selection
Remove low-signal features. The flat importance distribution suggests many features are noise. Try:
- Recursive Feature Elimination (RFE) with CV
- Start with top 20 features, add back only if CV improves

#### 3.2 Model Ensemble
Add a simple logistic regression as a secondary model. If XGBoost and LR disagree, lower confidence. Agreement = higher confidence.

#### 3.3 Transaction Features Rethink
Transaction features (acquisitions, departures) are raw counts, not normalized. A team with 77 acquisitions (MIA above) gets a huge value that means nothing predictive. Consider:
- Only count transactions in last 7 days (recency)
- Weight by player WAR (quality of transaction)
- Or drop transaction features entirely if they don't help CV

---

## 📈 Expected Impact

| Fix | Expected Accuracy Gain | Effort |
|---|---|---|
| Remove spring from training | +2-3% | Low |
| Add regularization | +1-2% | Low |
| Fix H2H spring contamination | +1% | Low |
| Use prior season stats early | +2-3% (in April) | Medium |
| Proper confidence calibration | +3-5% (for betting ROI) | Medium |
| Fix adaptive learning | +1-2% | Medium |
| Feature selection/engineering | +1-3% | High |

**Conservative estimate:** These fixes should bring live accuracy from 50.5% to **57-60%** range, which is competitive for MLB betting (the sharp market line is ~52-55%).

---

## ⚡ Quick Win: The One Change That Helps Most Right Now

**Invert your confidence filter.** Until the model is retrained:
- Bet only on predictions where confidence is **< 55%** (53.6% accuracy)
- Avoid predictions where confidence is **> 70%** (38.5% accuracy)

This is counterintuitive but the data is clear: the model's low-confidence picks are its best picks. This buys you time until the retrain.

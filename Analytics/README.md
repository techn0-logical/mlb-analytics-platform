
# Analytics Folder (2026)

This folder contains legacy and experimental analytics modules `working_feature_engineering.py` 


## Current Structure

- `working_feature_engineering.py`: The only feature engineering module used by `AdaptiveLearning.py` and `OptimizedMLTrainer.py`.
- `models/`: Stores legacy model artifacts (not used in current workflow).


## Purpose

This folder is now a holding area for analytics code `working_feature_engineering.py`which is required for model training and feature generation.


## Usage

**To use the current feature engineering system:**

```python
from Analytics.working_feature_engineering import WorkingFeatureEngineer

engineer = WorkingFeatureEngineer()
features = engineer.create_game_features("NYY", "BOS", date(2025, 4, 15))
print(features)
```

## Overview

`working_feature_engineering.py` is the **sole feature engineering module** used in this project. It is designed to generate robust, production-ready features for MLB game prediction models, focusing on simplicity, reliability, and accuracy. This module is actively used by `AdaptiveLearning.py` and `OptimizedMLTrainer.py`.

## What It Does

The module provides the `WorkingFeatureEngineer` class, which:

- Aggregates and normalizes team batting and pitching statistics from the database
- Computes recent transaction activity and roster stability
- Calculates head-to-head matchup features
- Produces comparative features (batting, pitching, WAR, roster stability advantages)
- Returns a single, comprehensive feature dictionary for any MLB matchup and date

All features are designed to be numerically stable, normalized, and ready for direct use in machine learning models.

## Key Methods

### `create_game_features(home_team: str, away_team: str, game_date: date) -> Dict[str, float]`
Generates a full set of features for a given game, including:
- Team batting features (OPS, OBP, SLG, WAR, depth, etc.)
- Team pitching features (ERA, WHIP, K/9, BB/9, WAR, depth, etc.)
- Transaction features (roster activity, acquisitions, trades, stability)
- Head-to-head matchup features (win rates, scoring, advantage)
- Comparative features (batting, pitching, WAR, roster stability advantages)

### `create_team_batting_features(team_id: str, as_of_date: date) -> Dict[str, float]`
Aggregates and normalizes batting stats for a team as of a given date.

### `create_team_pitching_features(team_id: str, as_of_date: date) -> Dict[str, float]`
Aggregates and normalizes pitching stats for a team as of a given date.

### `create_transaction_features(team_id: str, as_of_date: date, days: int = 30) -> Dict[str, float]`
Summarizes recent roster transactions and stability for a team.

### `create_head_to_head_features(home_team: str, away_team: str, as_of_date: date) -> Dict[str, float]`
Summarizes the last 3 years of head-to-head matchups between two teams.

## Example Usage

```python
from Analytics.working_feature_engineering import WorkingFeatureEngineer
from datetime import date

engineer = WorkingFeatureEngineer()
features = engineer.create_game_features("NYY", "BOS", date(2025, 4, 15))
print(features)
engineer.close_session()
```

## Feature Categories

- **Batting**: OPS, OBP, SLG, WAR, depth, power, production, speed
- **Pitching**: ERA quality, WHIP quality, K/9, BB/9, WAR, depth, wins, saves
- **Transactions**: Roster activity, acquisitions, departures, trades, stability
- **Head-to-Head**: Win rates, scoring, home advantage
- **Comparative**: Batting, pitching, WAR, and roster stability advantages

## Design Principles

- **Simplicity**: No complex SQL or fragile logic; all queries are robust and easy to debug
- **Normalization**: All features are scaled to [0, 1] or meaningful ranges for ML
- **Fail-Safe Defaults**: If no data is available, reasonable default values are returned
- **Production-Ready**: Used in all current model training and prediction workflows

## Dependencies

- **Database**: PostgreSQL with SQLAlchemy ORM
- **Python**: 3.8+
- **ML (downstream)**: scikit-learn, xgboost (not required for feature engineering itself)

## Testing

The module includes a test function for standalone validation:

```bash
python Analytics/working_feature_engineering.py
```
This will print a categorized summary of generated features for a sample game.

## Maintenance

If you need to extend or modify feature engineering, edit only `working_feature_engineering.py`. All other analytics files have been removed for clarity and maintainability.
# MLB Analytics Platform

A full-stack MLB game prediction system that collects real-time data from the MLB Stats API, engineers features from player and team performance metrics, trains an XGBoost classification model, and generates daily game winner predictions with confidence-tiered recommendations.

Built for the 2026 MLB season. Currently tracking **~10,000 lines** of Python across data collection, feature engineering, model training, adaptive learning, and production prediction modules — backed by a **30+ table PostgreSQL database** with comprehensive sabermetric coverage.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MLB Stats API                                │
│                   (schedules, boxscores, rosters,                    │
│                    transactions, player stats)                       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     DataCollection/                                  │
│  collector.py ── orchestrates daily pipeline                        │
│  ├── games.py ── scores, schedules, game status                     │
│  ├── player_stats.py ── batting & pitching (season + sabermetrics)  │
│  ├── pitcher_game_logs.py ── per-start pitching lines               │
│  ├── transactions.py ── trades, IL moves, roster changes            │
│  ├── roster_collection.py ── team roster validation                 │
│  └── weather.py ── game-day conditions (OpenWeatherMap)             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                              │
│  30+ tables: teams, games, players, player_batting_stats,           │
│  player_pitching_stats, pitcher_game_logs, mlb_transactions,        │
│  weather_conditions, game_predictions, trained_models,              │
│  daily_predictions, prediction_performance, ...                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────────────┐ ┌──────────┐ ┌──────────────────┐
│   Analytics/     │ │ Model    │ │ Production       │
│   Feature        │ │ Trainer/ │ │ Predictor/       │
│   Engineering    │ │          │ │                  │
│   (77 features)  │ │ XGBoost  │ │ Daily predictions│
│                  │ │ training │ │ + result updates │
│   Batting        │ │ + CV     │ │ + performance    │
│   Pitching       │ │ + store  │ │   tracking       │
│   Starter logs   │ │ to DB    │ │                  │
│   Bullpen stats  │ │          │ │ Adaptive         │
│   Transactions   │ │          │ │ Learning Engine  │
│   H2H matchups   │ │          │ │ (weight tuning)  │
└──────────────────┘ └──────────┘ └──────────────────┘
```

---

## Features

### Data Collection Pipeline
- **MLB Stats API integration** — game schedules, live scores, final results, boxscores
- **Player statistics** — season batting and pitching stats with sabermetrics (`season,sabermetrics` combined API call for WAR, wOBA, wRC+, FIP, xFIP)
- **Pitcher game logs** — per-start pitching lines extracted from boxscores (IP, ER, K, BB, pitches, quality starts)
- **Roster transactions** — trades, IL placements, call-ups, DFAs from the MLB transactions API
- **Weather conditions** — temperature, wind, humidity via OpenWeatherMap for each game's stadium
- **Spring training filtering** — automatic purge of spring training holdover data when regular season begins
- **Orchestrated daily runs** — single `collector.py` entry point with modes: `daily`, `lightweight`, `scores`, `trades`, `players`, `pitcher-logs`, `multi-season`

### Feature Engineering (77 Features)
All features are normalized to 0–1 scale for model consistency:

| Category | Count | Examples |
|---|---|---|
| Team Batting | 9 × 2 | avg, OPS, OBP, SLG, power, production, speed, WAR, depth |
| Team Pitching | 7 × 2 | ERA quality, WHIP quality, K rate, control, saves, WAR, depth |
| Starting Pitcher | 7 × 2 | Rolling 5-start ERA, WHIP, K/9, BB/9, QS%, avg IP, avg pitches |
| Bullpen | 3 × 2 | 14-day rolling ERA, WHIP, K rate |
| Roster Activity | 6 × 2 | Acquisitions, departures, net change, trade activity, stability |
| Head-to-Head | 7 | H2H games, home/away win%, advantage, scoring differential |
| Derived Advantages | 5 | Batting, pitching, WAR, roster stability, starter/bullpen ERA |

### Model Training
- **Algorithm**: XGBoost classifier with `binary:logistic` objective
- **Training data**: Regular season games only (months 4–10), 2022–2025 (~9,000 games)
- **Validation**: Stratified 5-fold cross-validation (CV accuracy ~58%)
- **Model storage**: Serialized to PostgreSQL `trained_models` table as binary (no `.pkl` files on disk)
- **Feature selection**: Automatic pruning of features below importance threshold

### Adaptive Learning
- **Feature weight adjustment** — measures per-feature correlation with correct predictions, adjusts weights via EMA smoothing
- **Confidence calibration** — tracks predicted vs actual accuracy per confidence band, applies calibration factors
- **Team-specific adjustments** — corrects systematic over/under-prediction of individual teams
- **Conservative updates** — all adjustments are bounded and smoothed to prevent overfitting to noise

### Production Prediction System
- **Daily game predictions** with win probability and confidence score
- **Confidence tiers**: STRONG (≥62%), MODERATE (56–62%), AVOID (<56%)
- **Automated result tracking** — `update_predictions.py` backfills actual winners from completed games
- **Performance monitoring** — `model_performance_today.py` for quick daily accuracy checks
- **Full performance analysis** — `PerformanceAnalysis/Performance.py` populates multi-table accuracy tracking across confidence levels and tiers

---

## Database Schema

PostgreSQL 14+ with 30+ tables organized into domains:

| Domain | Key Tables | Purpose |
|---|---|---|
| **Core** | `teams`, `games` | 30 MLB teams, game schedules/results |
| **Players** | `players`, `player_batting_stats`, `player_pitching_stats` | ~1,500 active players with season stats + sabermetrics |
| **Pitching Detail** | `pitcher_game_logs` | Per-game pitching lines for starter/bullpen feature engineering |
| **Transactions** | `mlb_transactions`, `player_team_history`, `player_injuries` | Roster moves, IL tracking, trade impact analysis |
| **Team Analytics** | `team_stats`, `advanced_team_*_metrics`, `composite_team_metrics` | Aggregated team performance and Statcast data |
| **Weather** | `weather_conditions` | Game-day weather from OpenWeatherMap |
| **Predictions** | `game_predictions`, `daily_predictions`, `trained_models` | Model predictions, results, and serialized model storage |
| **Performance** | `prediction_performance`, `confidence_level_performance`, `betting_performance` | Multi-dimensional accuracy tracking |
| **Adaptive** | `feature_performance`, `confidence_calibration`, `model_parameters`, `team_performance_adjustments` | Learning engine state |

Full schema definition: [`Database/schema/databaseTables.sql`](Database/schema/databaseTables.sql)

---

## Project Structure

```
├── Analytics/
│   └── working_feature_engineering.py    # 77-feature engineering pipeline
│
├── Application/
│   ├── Application.py                    # CLI interface
│   └── Functions.py                      # CLI helper functions
│
├── Database/
│   ├── config/database.py                # SQLAlchemy engine, session factory, connection pooling
│   ├── models/models.py                  # 30+ SQLAlchemy ORM models
│   └── schema/databaseTables.sql         # Full DDL with indexes and constraints
│
├── DataCollection/
│   ├── collector.py                      # Daily collection orchestrator
│   ├── config.py                         # API config, team name mappings
│   ├── games.py                          # Game schedule and score collection
│   ├── player_stats.py                   # Batting/pitching stats + sabermetrics
│   ├── pitcher_game_logs.py              # Per-start pitching lines from boxscores
│   ├── transactions.py                   # MLB transaction ingestion
│   ├── roster_collection.py              # Team roster validation
│   ├── weather.py                        # OpenWeatherMap integration
│   └── utils.py                          # Shared utilities (API calls, team normalization)
│
├── ModelTrainer/
│   ├── OptimizedMLTrainer.py             # XGBoost model training pipeline
│   └── AdaptiveLearning.py               # Post-training weight/calibration tuning
│
├── PerformanceAnalysis/
│   └── Performance.py                    # Multi-table prediction accuracy tracking
│
├── ProductionPredictor/
│   ├── live_betting_predictions.py       # Generate daily predictions
│   ├── update_predictions.py             # Backfill actual results
│   ├── model_performance_today.py        # Quick daily accuracy check
│   └── show_games_status.py              # Debug game status viewer
│
├── logs/                                 # Structured logging (system, errors, predictions, performance)
├── testing/data/                         # Training and validation CSVs
├── requirements.txt                      # Python dependencies
└── secrets.env                           # Database credentials and API keys (not committed)
```

---

## Getting Started

### Prerequisites

- **Python** 3.11+
- **PostgreSQL** 14+
- **API Keys** (optional): OpenWeatherMap for weather data

### Installation

```bash
# Clone the repository
git clone https://github.com/techn0-logical/mlb-analytics-platform.git
cd mlb-analytics-platform

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `secrets.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/mlb_betting_analytics

# API Keys (optional)
OPENWEATHER_API_KEY=your_openweathermap_key
ODDS_API_KEY=your_odds_api_key
```

### Database Setup

```bash
# Create the database
createdb mlb_betting_analytics

# Run the schema
psql -d mlb_betting_analytics -f Database/schema/databaseTables.sql
```

---

## Usage

### Daily Data Collection

```bash
# Full daily collection (games, pitcher logs, transactions, weather, player stats)
python -m DataCollection.collector daily

# Lightweight (scores and schedules only)
python -m DataCollection.collector lightweight

# Specific modules
python -m DataCollection.collector scores
python -m DataCollection.collector players
python -m DataCollection.collector pitcher-logs
python -m DataCollection.collector trades

# Historical backfill
python -m DataCollection.collector multi-season
```

### Model Training

```bash
# Train the XGBoost model (saves to database, not disk)
python ModelTrainer/OptimizedMLTrainer.py
```

The trainer:
1. Pulls regular season games from 2022–2025
2. Engineers 77 features per game via `WorkingFeatureEngineer`
3. Trains XGBoost with cross-validation
4. Stores the serialized model + feature names in the `trained_models` table
5. Marks the new model as active (deactivates previous)

### Adaptive Learning

```bash
# Run adaptive learning (after predictions have been scored)
python ModelTrainer/AdaptiveLearning.py
```

Analyzes recent prediction accuracy, adjusts feature weights, recalibrates confidence bands, and saves tuning parameters to the database.

### Generate Predictions

```bash
# Generate predictions for today's games
python ProductionPredictor/live_betting_predictions.py
```

### Score & Evaluate Predictions

```bash
# Update predictions with actual game results
python ProductionPredictor/update_predictions.py

# Check today's accuracy
python ProductionPredictor/model_performance_today.py

# Full performance analysis (populates tracking tables)
python PerformanceAnalysis/Performance.py
```

---

## Data Sources

| Source | Data | Method |
|---|---|---|
| [MLB Stats API](https://statsapi.mlb.com) | Schedules, scores, rosters, transactions, boxscores, player stats (season + sabermetrics) | REST API (`mlb-statsapi` package + direct HTTP) |
| [OpenWeatherMap](https://openweathermap.org/api) | Game-day weather conditions | REST API (requires key) |

All player and team data is sourced from the official MLB Stats API. No web scraping is used.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Database | PostgreSQL 14+ |
| ORM | SQLAlchemy 2.0 |
| ML Framework | XGBoost 3.1, scikit-learn 1.8 |
| Data Processing | pandas 3.0, NumPy 2.4 |
| API Client | requests, mlb-statsapi |
| Environment | python-dotenv |

---

## Key Design Decisions

- **Model stored in database, not on disk.** The trained XGBoost model is serialized as binary and stored in the `trained_models` table alongside its feature names and metadata. This eliminates `.pkl` file drift, enables atomic model swaps via the `is_active` flag, and keeps the model versioned with its training metrics.

- **Feature engineering queries the database, not flat files.** The `WorkingFeatureEngineer` runs SQL queries against live data to build features. This ensures predictions always reflect the latest available stats without manual CSV exports.

- **Spring training data is actively filtered.** The collector includes a `_purge_spring_training_holdovers()` method that removes stale spring training stats once the regular season begins, preventing contamination of player performance features.

- **Confidence tiers over raw probabilities.** Rather than exposing raw model probabilities, predictions are bucketed into STRONG / MODERATE / AVOID tiers. This provides actionable signal while acknowledging the inherent uncertainty in single-game outcomes.

- **Adaptive learning without retraining.** The `AdaptiveLearningEngine` adjusts feature weights and confidence calibration based on rolling prediction outcomes — enabling the model to adapt to mid-season trends without expensive full retraining cycles.

---

## License

This project is for educational and personal use. MLB data is sourced from the public MLB Stats API.

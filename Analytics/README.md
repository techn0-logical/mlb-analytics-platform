# Analytics Engine

A streamlined, production-ready MLB analytics system that combines statistical analysis with machine learning for comprehensive team evaluation and game predictions.

## Features

- **Team Analysis**: Advanced sabermetrics with trade and injury impact assessment
- **Game Predictions**: Statistical and hybrid ML-enhanced predictions
- **Trade Impact**: Automatic evaluation of recent trades on team performance
- **Injury Analysis**: Assessment of how injuries affect team strength
- **ML Integration**: Optional machine learning model training and predictions
- **Professional Caching**: Automatic result caching for improved performance

## Quick Start

```python
from Analytics.analytics_engine import analyze_team, predict_game

# Analyze a team
team_stats = analyze_team("LAD")
print(f"{team_stats.team_name}: {team_stats.wins}-{team_stats.losses}")
print(f"Strength Rating: {team_stats.strength_rating:.3f}")

# Predict a game
prediction = predict_game("LAD", "SF")
print(f"Prediction: {prediction.predicted_winner} ({prediction.win_probability:.1%})")
print(f"Confidence: {prediction.confidence_level}")
```

## Core Functions

### `analyze_team(team_id: str, as_of_date: date = None) -> TeamStats`

Comprehensive team analysis including:
- Win-loss record and win percentage
- Pythagorean expectation
- Recent form (last 10 games)
- Home field advantage
- Trade impact (last 30 days)
- Injury impact assessment
- Overall strength rating and confidence

### `predict_game(home_team: str, away_team: str, game_date: date = None) -> GamePrediction`

Game prediction using multiple factors:
- Team strength differential (40% weight)
- Recent form (25% weight)
- Injury impact (20% weight)
- Trade impact (15% weight)
- Home field advantage (baseline)

Returns prediction with confidence level and key factors.

### Machine Learning Integration

```python
from Analytics.analytics_engine import train_ml_model, predict_game_with_ml

# Train ML model with historical data
games_data = [...] # List of game dictionaries
result = train_ml_model(games_data)

# Use hybrid predictions (statistical + ML)
hybrid_prediction = predict_game_with_ml("LAD", "SF")
```

## Data Structures

### TeamStats
- `team_id`: Team identifier (e.g., "LAD")
- `team_name`: Full team name
- `wins/losses`: Season record
- `win_pct`: Win percentage
- `strength_rating`: Overall team strength (0.0-1.0)
- `recent_form`: Recent performance (0.0-1.0)
- `trade_impact`: Impact of recent trades (-0.5 to 0.5)
- `injury_impact`: Impact of current injuries (0.0-0.5)
- `confidence`: Analysis confidence (0.0-1.0)

### GamePrediction
- `predicted_winner`: Team ID of predicted winner
- `win_probability`: Probability of predicted winner (0.5-1.0)
- `confidence_level`: "high", "medium", or "low"
- `factors`: List of key factors influencing prediction
- `prediction_type`: "statistical", "ml", or "hybrid"

## Configuration

Global configuration can be modified via the `CONFIG` dictionary:

```python
from Analytics.analytics_engine import CONFIG

CONFIG['confidence_high'] = 0.70  # High confidence threshold
CONFIG['recent_games_window'] = 15  # Recent form window
CONFIG['cache_ttl'] = 7200  # Cache time-to-live (seconds)
```

## System Status

Check system capabilities and status:

```python
from Analytics.analytics_engine import get_system_status

status = get_system_status()
print(f"Database: {'✅' if status['database_available'] else '❌'}")
print(f"ML Available: {'✅' if status['ml_available'] else '❌'}")
print(f"ML Trained: {'✅' if status['ml_trained'] else '❌'}")
```

## Compatibility

The system includes a compatibility layer for existing code:

```python
from Analytics.analytics_engine import SabermetricCalculator

# Legacy interface support
calc = SabermetricCalculator()
prediction = calc.predict_game("LAD", "SF")
```

## Performance Features

- **Automatic Caching**: Results cached for 1 hour by default
- **Database Connection Pooling**: Efficient database access
- **Error Handling**: Graceful degradation on component failures
- **Memory Efficient**: Simplified data structures and algorithms

## Dependencies

- **Database**: PostgreSQL with SQLAlchemy ORM
- **Scientific**: pandas, numpy
- **ML (Optional)**: scikit-learn, xgboost
- **System**: Python 3.8+

## File Size Reduction

**Simplified Version**: 748 lines (56% reduction from original 1,687 lines)

- Maintained all core functionality
- Streamlined architecture
- Simplified but powerful ML integration
- Professional error handling and caching
- Clean, readable code structure

## Architecture Improvements

1. **Single File Design**: All components in one cohesive file
2. **Simple Functions**: Clear, focused functions with single responsibilities
3. **Global Configuration**: Easy-to-modify settings
4. **Minimal Dependencies**: Core functionality with optional advanced features
5. **Professional Standards**: Proper logging, error handling, and documentation

The simplified analytics engine maintains the power and accuracy of the original system while being significantly more maintainable and easier to understand.
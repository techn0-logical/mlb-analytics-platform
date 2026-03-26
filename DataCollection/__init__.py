"""
Simple MLB Data Collection System
==================================

A clean, modular approach to collecting MLB data with focused functions.

Structure:
- config.py: Configuration settings
- utils.py: Common utilities
- games.py: Game data collection  
- transactions.py: Transaction data collection
- weather.py: Weather data collection
- collector.py: Main orchestrator
"""

from .collector import (
    run_daily_collection,
    run_score_update, 
    run_trade_update,
    run_player_stats_update,
    run_custom_collection
)
from .roster_collection import (
    collect_oakland_historical_data,
    validate_all_teams_data
)
from .player_stats import (
    collect_player_batting_stats,
    collect_player_pitching_stats,
    collect_daily_player_status,
    collect_all_player_stats
)

__all__ = [
    'run_daily_collection',
    'run_score_update',
    'run_trade_update', 
    'run_player_stats_update',
    'run_custom_collection',
    'collect_oakland_historical_data',
    'validate_all_teams_data',
    'collect_player_batting_stats',
    'collect_player_pitching_stats', 
    'collect_daily_player_status',
    'collect_all_player_stats'
]
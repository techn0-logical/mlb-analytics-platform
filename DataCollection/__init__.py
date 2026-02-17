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
    run_custom_collection
)

__all__ = [
    'run_daily_collection',
    'run_score_update',
    'run_trade_update', 
    'run_custom_collection'
]
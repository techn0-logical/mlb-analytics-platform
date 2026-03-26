#!/usr/bin/env python3
"""
Update today's predictions with actual results from the games table.
"""
import sys
import os
from pathlib import Path
from datetime import date

# Handle space in folder name and ensure absolute path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import timedelta

from Database.config.database import db_config
from Database.models.models import GamePrediction, Game

SessionLocal = db_config.create_session_factory()
session = SessionLocal()

today = date.today()

predictions = session.query(GamePrediction).filter(GamePrediction.prediction_date == today).all()
updated = 0
for pred in predictions:
    game = session.query(Game).filter(Game.game_pk == pred.game_pk).first()
    if not game:
        continue
    # Only update if the game is completed (including 'completed early') and has a winner
    if game.game_status and game.game_status.startswith('completed') and game.winner_team_id:
        pred.actual_winner = game.winner_team_id
        if game.home_score is not None and game.away_score is not None:
            pred.actual_total_runs = game.home_score + game.away_score
        else:
            pred.actual_total_runs = None
        pred.prediction_correct = 1 if pred.predicted_winner == game.winner_team_id else 0
        updated += 1
    else:
        pred.actual_winner = None
        pred.actual_total_runs = None
        pred.prediction_correct = None

session.commit()
print(f"Updated {updated} predictions for {today} with actual results.")
session.close()

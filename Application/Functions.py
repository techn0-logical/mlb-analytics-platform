#!/usr/bin/env python3
"""This line allows this application file to be ran as a shell script"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Database.config.database import db_config
from Database.models.models import GamePrediction, Game
from sqlalchemy.orm import Session
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from ModelTrainer.OptimizedMLTrainer import OptimizedMLTrainer, get_session
from ModelTrainer.AdaptiveLearning import AdaptiveLearningEngine
from Database.config.database import DatabaseConfig


def show_predictions():
    SessionLocal = db_config.create_session_factory()
    session = SessionLocal()

    results = session.query(GamePrediction, Game).join(Game, GamePrediction.game_pk == Game.game_pk).filter(GamePrediction.prediction_date == date.today()).all()

    print("\nMLB Betting Predictions for today\n")
    print("Home Team | Away Team | Predicted Winner | Win Probability")
    print("-"*90)

    for pred, game in results:
        print(f"{game.home_team_id} | {game.away_team_id} | {pred.predicted_winner} | {pred.win_probability}")

        if not results:
            print("No predictions found for today.")
                    
    session.close()

def get_accuracy():
    """Pull actual model accuracy from the trained_models table — no more hardcoded claims."""
    try:
        db_config = DatabaseConfig()
        engine = db_config.create_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT model_version, test_accuracy, cv_accuracy
                FROM trained_models WHERE is_active = TRUE
                ORDER BY created_at DESC LIMIT 1
            """)).fetchone()
        if result:
            return {
                'version': result[0],
                'test_accuracy': round(float(result[1] or 0) * 100, 1),
                'cv_accuracy': round(float(result[2] or 0) * 100, 1),
            }
    except Exception:
        pass
    return {'version': 'unknown', 'test_accuracy': 0.0, 'cv_accuracy': 0.0}

def get_games(target_date):
    """Get REAL games scheduled for a specific date"""
    
    print(f"🔍 Checking for LIVE games on {target_date}...")
    
    try:
        session = get_session()
        
        query = text("""
            SELECT 
                game_pk,
                home_team_id, 
                away_team_id, 
                game_date,
                game_status
            FROM games
            WHERE game_date = :target_date
            AND game_status IN ('scheduled', 'in_progress', 'postponed', 'pre-game')
            ORDER BY game_pk
        """)
        
        games = session.execute(query, {'target_date': target_date}).fetchall()
        
        print(f"📊 Found {len(games)} LIVE games scheduled for {target_date}")
        print(games)
        return games
        
    except Exception as e:
        print(f"❌ Error getting live games: {e}")
        return []
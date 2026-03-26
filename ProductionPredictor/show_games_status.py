#!/usr/bin/env python3
"""
Show all games for today with their status and winner for debugging prediction updates.
"""
import sys
import os
from pathlib import Path
from datetime import date

# Handle space in folder name and ensure absolute path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Database.config.database import db_config
from Database.models.models import Game

SessionLocal = db_config.create_session_factory()
session = SessionLocal()

today = date.today()
games = session.query(Game).filter(Game.game_date == today).all()

print(f"\nGames for {today} (status and winner):\n")
for g in games:
    print(f"Game PK: {g.game_pk} | Home: {g.home_team_id} | Away: {g.away_team_id} | Status: {g.game_status} | Winner: {g.winner_team_id}")

session.close()

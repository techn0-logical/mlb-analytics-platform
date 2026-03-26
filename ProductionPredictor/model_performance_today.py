#!/usr/bin/env python3
"""
Evaluate model performance for today's predictions.
"""
import sys
import os
from pathlib import Path
from datetime import date, timedelta


# Handle space in folder name and ensure absolute path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Database.config.database import db_config
from Database.models.models import GamePrediction

SessionLocal = db_config.create_session_factory()
session = SessionLocal()

today = date.today()
preds = session.query(GamePrediction).filter(GamePrediction.prediction_date == today).all()

total = 0
correct = 0
ties = 0
for pred in preds:
    if pred.prediction_correct is None:
        ties += 1
    else:
        total += 1
        if pred.prediction_correct == 1:
            correct += 1

if total > 0:
    accuracy = correct / total * 100
    print(f"Model accuracy for {today}: {correct}/{total} correct ({accuracy:.1f}%)")
else:
    print(f"No completed games with a winner for {today}.")

if ties > 0:
    print(f"Tied games (no winner): {ties}")

session.close()

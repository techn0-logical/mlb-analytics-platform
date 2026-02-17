#!/usr/bin/env python3
"""
MLB Prediction Monitoring System
================================

Command-line monitoring system for tracking your 73.2% accurate model's
performance during the 2026 MLB season.

Features:
- Real-time accuracy tracking
- Confidence level performance monitoring
- Daily prediction summaries
- Performance trends and analytics
- Live game predictions display
- Model health monitoring

Author: MLB Analytics Team
Date: February 16, 2026
Version: 2.0.0 - Personal Use (No Web Interface)
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from Database.config.database import DatabaseConfig
from Database.models.models import Game, GamePrediction as DBPrediction, Team
from ProductionPredictor.logging_config import get_logger


class PredictionMonitor:
    """Real-time monitoring system for MLB predictions"""
    
    def __init__(self):
        self.db_config = DatabaseConfig()
        self.logger = get_logger()
        
    def get_daily_summary(self, target_date: date = None) -> Dict[str, Any]:
        """Get summary of predictions for a specific date"""
        
        if target_date is None:
            target_date = date.today()
        
        try:
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            
            # Get games and predictions for the date
            results = session.query(Game, DBPrediction).outerjoin(
                DBPrediction, Game.game_pk == DBPrediction.game_pk
            ).filter(Game.game_date == target_date).all()
            
            if not results:
                session.close()
                return {'date': str(target_date), 'games': 0, 'predictions': 0}
            
            total_games = len(results)
            predictions_made = sum(1 for _, pred in results if pred is not None)
            completed_games = sum(1 for game, _ in results if game.game_status == 'final')
            
            # Calculate accuracy for completed games with predictions
            validated_predictions = [
                (game, pred) for game, pred in results 
                if pred is not None and game.game_status == 'final' and pred.prediction_correct is not None
            ]
            
            accuracy = 0
            confidence_performance = {'high': [0, 0], 'medium': [0, 0], 'low': [0, 0]}
            
            if validated_predictions:
                correct = sum(1 for _, pred in validated_predictions if pred.prediction_correct == 1)
                accuracy = correct / len(validated_predictions)
                
                # Confidence breakdown
                for _, pred in validated_predictions:
                    confidence = self._get_confidence_from_probability(pred.win_probability)
                    confidence_performance[confidence][1] += 1  # total
                    if pred.prediction_correct == 1:
                        confidence_performance[confidence][0] += 1  # correct
            
            session.close()
            return {
                'date': str(target_date),
                'games_scheduled': total_games,
                'predictions_made': predictions_made,
                'games_completed': completed_games,
                'games_validated': len(validated_predictions),
                'accuracy': accuracy,
                'confidence_performance': {
                    level: {
                        'accuracy': stats[0] / stats[1] if stats[1] > 0 else 0,
                        'correct': stats[0],
                        'total': stats[1]
                    }
                    for level, stats in confidence_performance.items()
                }
            }
                
        except Exception as e:
            self.logger.log_error("get_daily_summary", e, {'date': str(target_date)})
            return {'error': str(e)}
    
    def get_weekly_performance(self, weeks: int = 4) -> List[Dict[str, Any]]:
        """Get performance data for the last N weeks"""
        
        end_date = date.today()
        start_date = end_date - timedelta(weeks=weeks)
        
        try:
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            
            # Get all validated predictions in the range
            predictions = session.query(DBPrediction, Game).join(
                Game, DBPrediction.game_pk == Game.game_pk
            ).filter(
                Game.game_date.between(start_date, end_date),
                DBPrediction.prediction_correct.isnot(None)
            ).order_by(Game.game_date).all()
            
            session.close()
            
            # Group by week
            weekly_data = []
            current_week_start = start_date
            
            while current_week_start <= end_date:
                week_end = current_week_start + timedelta(days=6)
                
                week_predictions = [
                    (pred, game) for pred, game in predictions
                    if current_week_start <= game.game_date <= week_end
                ]
                
                if week_predictions:
                    total = len(week_predictions)
                    correct = sum(1 for pred, _ in week_predictions if pred.prediction_correct == 1)
                    accuracy = correct / total
                    
                    # Confidence breakdown
                    conf_stats = {'high': [0, 0], 'medium': [0, 0], 'low': [0, 0]}
                    for pred, _ in week_predictions:
                        confidence = self._get_confidence_from_probability(pred.win_probability)
                        conf_stats[confidence][1] += 1
                        if pred.prediction_correct == 1:
                            conf_stats[confidence][0] += 1
                    
                    weekly_data.append({
                        'week_start': str(current_week_start),
                        'week_end': str(week_end),
                        'total_predictions': total,
                        'correct_predictions': correct,
                        'accuracy': accuracy,
                        'confidence_breakdown': {
                            level: {
                                'accuracy': stats[0] / stats[1] if stats[1] > 0 else 0,
                                'count': stats[1]
                            }
                            for level, stats in conf_stats.items()
                        }
                    })
                
                current_week_start = week_end + timedelta(days=1)
            
            return weekly_data
                
        except Exception as e:
            self.logger.log_error("get_weekly_performance", e)
            return []
    
    def get_live_predictions(self, target_date: date = None) -> List[Dict[str, Any]]:
        """Get today's predictions for live monitoring"""
        
        if target_date is None:
            target_date = date.today()
        
        try:
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            
            # Get games and predictions for the date
            results = session.query(Game, DBPrediction).join(
                DBPrediction, Game.game_pk == DBPrediction.game_pk
            ).filter(Game.game_date == target_date).all()
            
            predictions = []
            for game, pred in results:
                
                # Get team info separately
                home_team = session.query(Team).filter(Team.team_id == game.home_team_id).first()
                away_team = session.query(Team).filter(Team.team_id == game.away_team_id).first()
                
                if not home_team or not away_team:
                    continue
                
                # Parse key factors if available
                factors = []
                if pred.primary_factors:
                    try:
                        factors = json.loads(pred.primary_factors)
                    except:
                        pass
                
                prediction_data = {
                    'game_pk': game.game_pk,
                    'game_time': str(game.game_time) if game.game_time else 'TBD',
                    'home_team': {
                        'id': game.home_team_id,
                        'name': home_team.team_name,
                        'city': home_team.city
                    },
                    'away_team': {
                        'id': game.away_team_id,
                        'name': away_team.team_name,
                        'city': away_team.city
                    },
                    'prediction': {
                        'winner': pred.predicted_winner,
                        'probability': float(pred.win_probability),
                        'confidence': self._get_confidence_from_probability(pred.win_probability),
                        'factors': factors[:3]  # Top 3 factors
                    },
                    'game_status': game.game_status,
                    'actual_result': {
                        'winner': pred.actual_winner,
                        'correct': pred.prediction_correct == 1 if pred.prediction_correct is not None else None
                    } if game.game_status == 'final' else None
                }
                
                predictions.append(prediction_data)
            
            session.close()
            return predictions
                
        except Exception as e:
            self.logger.log_error("get_live_predictions", e, {'date': str(target_date)})
            return []
    
    def get_model_health(self) -> Dict[str, Any]:
        """Get model health and system status"""
        
        try:
            # Check recent prediction activity
            recent_date = date.today() - timedelta(days=1)
            daily_summary = self.get_daily_summary(recent_date)
            
            # Check database connectivity
            db_status = True
            try:
                SessionLocal = self.db_config.create_session_factory()
                session = SessionLocal()
                try:
                    session.execute("SELECT 1").fetchone()
                finally:
                    session.close()
            except:
                db_status = False
            
            # Calculate rolling accuracy (last 50 predictions)
            rolling_accuracy = self._get_rolling_accuracy()
            
            # System health indicators
            health_status = "healthy"
            warnings = []
            
            if not db_status:
                health_status = "error"
                warnings.append("Database connectivity issues")
            
            if rolling_accuracy < 0.5:
                health_status = "warning" if health_status != "error" else "error"
                warnings.append(f"Model accuracy below 50% ({rolling_accuracy:.1%})")
            
            if daily_summary.get('predictions_made', 0) == 0 and daily_summary.get('games_scheduled', 0) > 0:
                health_status = "warning" if health_status != "error" else "error"
                warnings.append("No predictions made for scheduled games")
            
            return {
                'status': health_status,
                'warnings': warnings,
                'database_connected': db_status,
                'rolling_accuracy': rolling_accuracy,
                'last_prediction_date': str(recent_date),
                'recent_activity': daily_summary,
                'model_version': "2026_season_v1.0",
                'validation_accuracy': 0.732,  # From your validation results
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.log_error("get_model_health", e)
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_rolling_accuracy(self, n: int = 50) -> float:
        """Calculate rolling accuracy for the last N predictions"""
        
        try:
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            
            recent_predictions = session.query(DBPrediction).filter(
                DBPrediction.prediction_correct.isnot(None)
            ).order_by(DBPrediction.prediction_date.desc()).limit(n).all()
            
            session.close()
            
            if not recent_predictions:
                return 0.0
            
            correct = sum(1 for pred in recent_predictions if pred.prediction_correct == 1)
            return correct / len(recent_predictions)
            
        except Exception as e:
            self.logger.log_error("_get_rolling_accuracy", e)
            return 0.0
    
    def _get_confidence_from_probability(self, probability: float) -> str:
        """Convert probability to confidence level"""
        if probability >= 0.7:
            return 'high'
        elif probability >= 0.6:
            return 'medium'
        else:
            return 'low'


def display_performance_chart(weekly_data: List[Dict]) -> None:
    """Display performance chart in text format"""
    if not weekly_data:
        print("📊 No performance data available")
        return
    
    print("\n📈 Performance Trend (Last 4 weeks):")
    print("-" * 50)
    
    for data in weekly_data:
        week_start = data['week_start']
        accuracy = data['accuracy'] * 100
        total = data['total_predictions']
        
        # Create simple text chart
        bar_length = int(accuracy / 2)  # Scale to 50 characters max
        bar = "█" * bar_length + "░" * (50 - bar_length)
        
        print(f"{week_start}: {bar} {accuracy:.1f}% ({total} games)")


def main():
    """Command line interface for the monitoring system"""
    
    print("🎯 MLB Prediction Monitoring System - 2026 Season")
    print("=" * 60)
    
    monitor = PredictionMonitor()
    
    while True:
        print("\n📊 Select Monitoring Option:")
        print("1. View daily summary")
        print("2. Check model health")
        print("3. View live predictions")
        print("4. Generate performance report")
        print("5. Show performance chart")
        print("6. Exit")
        
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == '1':
            date_str = input("Enter date (YYYY-MM-DD) or press Enter for today: ").strip()
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
            
            summary = monitor.get_daily_summary(target_date)
            print("\n📊 Daily Summary:")
            print(json.dumps(summary, indent=2, default=str))
            
        elif choice == '2':
            health = monitor.get_model_health()
            print("\n🏥 Model Health:")
            print(json.dumps(health, indent=2, default=str))
            
        elif choice == '3':
            predictions = monitor.get_live_predictions()
            print(f"\n🔮 Live Predictions ({len(predictions)} games):")
            for pred in predictions:
                winner = pred['prediction']['winner']
                prob = pred['prediction']['probability']
                confidence = pred['prediction']['confidence']
                print(f"  {pred['away_team']['city']} @ {pred['home_team']['city']}: "
                      f"{winner} ({prob:.1%}) - {confidence.upper()}")
            
        elif choice == '4':
            weeks = input("Enter number of weeks for report (default 4): ").strip()
            weeks = int(weeks) if weeks.isdigit() else 4
            
            performance = monitor.get_weekly_performance(weeks)
            print(f"\n📈 Performance Report ({weeks} weeks):")
            print(json.dumps(performance, indent=2, default=str))
            
        elif choice == '5':
            weeks = input("Enter number of weeks for chart (default 4): ").strip()
            weeks = int(weeks) if weeks.isdigit() else 4
            
            performance = monitor.get_weekly_performance(weeks)
            display_performance_chart(performance)
            
        elif choice == '6':
            print("\n👋 Goodbye! Your monitoring system is ready for the 2026 season!")
            break
            
        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    main()
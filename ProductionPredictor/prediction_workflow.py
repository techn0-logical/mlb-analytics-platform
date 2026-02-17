#!/usr/bin/env python3
"""
Production MLB Prediction Workflow System
========================================

Comprehensive prediction workflow for the 2026 MLB season with full logging,
performance tracking, and prediction persistence for your 73.2% accurate model.

Features:
- Daily game predictions with confidence levels
- Comprehensive logging and audit trails  
- Performance tracking and validation
- Database persistence for predictions
- Real-time model performance monitoring
- Automated prediction scheduling
- Prediction result validation and accuracy tracking

Author: MLB Analytics Team
Date: February 5, 2026
Version: 1.0.0 - Production Ready
"""

import sys
import os
from pathlib import Path
import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import schedule
import time

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import your trained model system
from ModelTrainer.MLTrainer import train_and_validate_model, quick_train_model
from Analytics.analytics_engine import MLBAnalyticsEngine, AnalyticsConfig
from Database.config.database import DatabaseConfig
from Database.models.models import Game, GamePrediction as DBPrediction, Team

class ProductionPredictionLogger:
    """Professional logging system for production predictions"""
    
    def __init__(self, log_dir: str = "logs/predictions"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup daily prediction log
        today = datetime.now().strftime("%Y%m%d")
        self.prediction_log_file = self.log_dir / f"predictions_{today}.log"
        self.performance_log_file = self.log_dir / f"performance_{today}.log"
        self.error_log_file = self.log_dir / f"errors_{today}.log"
        
        # Configure loggers
        self._setup_loggers()
        
    def _setup_loggers(self):
        """Setup specialized loggers for different aspects of prediction workflow"""
        
        # Prediction Logger - All predictions made
        self.prediction_logger = logging.getLogger('predictions')
        self.prediction_logger.setLevel(logging.INFO)
        pred_handler = logging.FileHandler(self.prediction_log_file)
        pred_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        pred_handler.setFormatter(pred_formatter)
        self.prediction_logger.addHandler(pred_handler)
        
        # Performance Logger - Model accuracy tracking
        self.performance_logger = logging.getLogger('performance')
        self.performance_logger.setLevel(logging.INFO)
        perf_handler = logging.FileHandler(self.performance_log_file)
        perf_formatter = logging.Formatter('%(asctime)s | PERFORMANCE | %(message)s')
        perf_handler.setFormatter(perf_formatter)
        self.performance_logger.addHandler(perf_handler)
        
        # Error Logger - Issues and failures
        self.error_logger = logging.getLogger('prediction_errors')
        self.error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(self.error_log_file)
        error_formatter = logging.Formatter('%(asctime)s | ERROR | %(funcName)s | %(message)s')
        error_handler.setFormatter(error_formatter)
        self.error_logger.addHandler(error_handler)
        
        # Console output for real-time monitoring
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
        console_handler.setFormatter(console_formatter)
        
        self.prediction_logger.addHandler(console_handler)
        self.performance_logger.addHandler(console_handler)


@dataclass
class PredictionResult:
    """Complete prediction result with metadata"""
    game_pk: int
    game_date: date
    home_team: str
    away_team: str
    predicted_winner: str
    win_probability: float
    confidence_level: str
    key_factors: List[str]
    model_version: str
    prediction_timestamp: datetime
    
    # Additional metadata
    home_team_rating: float
    away_team_rating: float
    trade_impact: str
    injury_impact: str
    ml_probability: Optional[float] = None
    statistical_probability: Optional[float] = None


class ProductionPredictor:
    """Production-ready prediction system for 2026 MLB season"""
    
    def __init__(self, model_path: str = None):
        """Initialize production prediction system"""
        
        # Setup logging
        self.logger = ProductionPredictionLogger()
        
        # Load your trained model
        self.model_path = model_path or "Analytics/models/season_based_model_2026_20260204_071301.pkl"
        # Use direct function calls instead of trainer instance
        
        # Initialize database connection
        self.db_config = DatabaseConfig()
        
        # Performance tracking
        self.daily_predictions = []
        self.performance_metrics = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'high_confidence_correct': 0,
            'high_confidence_total': 0,
            'medium_confidence_correct': 0,
            'medium_confidence_total': 0,
            'low_confidence_correct': 0,
            'low_confidence_total': 0
        }
        
        self.logger.prediction_logger.info("🚀 Production Predictor initialized for 2026 season")
        
    def load_model(self) -> bool:
        """Load the trained model safely"""
        try:
            self.trainer.load_model(self.model_path)
            self.logger.prediction_logger.info(f"✅ Model loaded successfully: {self.model_path}")
            return True
        except Exception as e:
            self.logger.error_logger.error(f"Failed to load model {self.model_path}: {e}")
            return False
    
    def get_todays_games(self, target_date: date = None) -> List[Dict]:
        """Get today's scheduled games from database"""
        if target_date is None:
            target_date = date.today()
            
        try:
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            
            games = session.query(Game).filter(
                Game.game_date == target_date,
                Game.game_status.in_(['scheduled', 'pre-game'])
            ).all()
            
            game_data = []
            for game in games:
                game_data.append({
                    'game_pk': game.game_pk,
                    'game_date': game.game_date,
                    'home_team_id': game.home_team_id,
                    'away_team_id': game.away_team_id,
                    'game_status': game.game_status,
                    'venue_name': game.venue_name
                })
            
            session.close()
            self.logger.prediction_logger.info(f"📊 Found {len(game_data)} scheduled games for {target_date}")
            return game_data
                
        except Exception as e:
            self.logger.error_logger.error(f"Failed to get games for {target_date}: {e}")
            return []
    
    def make_prediction(self, game_data: Dict) -> Optional[PredictionResult]:
        """Make a single game prediction with full logging"""
        try:
            game_pk = game_data['game_pk']
            game_date = game_data['game_date']
            home_team = game_data['home_team_id']
            away_team = game_data['away_team_id']
            
            # Make prediction using your trained model
            prediction = self.trainer.calculator.predict_game(
                home_team_id=home_team,
                away_team_id=away_team,
                game_date=game_date,
                save_prediction=False,
                allow_historical=False
            )
            
            if not prediction:
                self.logger.error_logger.error(f"No prediction returned for game {game_pk}")
                return None
            
            # Create comprehensive prediction result
            result = PredictionResult(
                game_pk=game_pk,
                game_date=game_date,
                home_team=home_team,
                away_team=away_team,
                predicted_winner=prediction.predicted_winner,
                win_probability=prediction.win_probability,
                confidence_level=prediction.confidence_level,
                key_factors=prediction.key_factors[:5],  # Top 5 factors
                model_version="2026_season_v1.0",
                prediction_timestamp=datetime.now(),
                home_team_rating=prediction.home_team_rating,
                away_team_rating=prediction.away_team_rating,
                trade_impact=prediction.trade_impact,
                injury_impact=prediction.injury_impact
            )
            
            # Log the prediction
            self._log_prediction(result, game_data)
            
            return result
            
        except Exception as e:
            self.logger.error_logger.error(f"Prediction failed for game {game_data.get('game_pk', 'unknown')}: {e}")
            return None
    
    def _log_prediction(self, result: PredictionResult, game_data: Dict):
        """Log prediction with comprehensive details"""
        
        # Main prediction log
        log_message = (
            f"PREDICTION | Game {result.game_pk} | "
            f"{result.away_team} @ {result.home_team} | "
            f"Winner: {result.predicted_winner} | "
            f"Probability: {result.win_probability:.1%} | "
            f"Confidence: {result.confidence_level.upper()} | "
            f"Venue: {game_data.get('venue_name', 'N/A')}"
        )
        
        self.logger.prediction_logger.info(log_message)
        
        # Detailed factors log
        factors_str = " | ".join(result.key_factors)
        self.logger.prediction_logger.info(f"FACTORS | Game {result.game_pk} | {factors_str}")
        
        # Performance tracking log
        self.logger.performance_logger.info(
            f"METRICS | Game {result.game_pk} | "
            f"Home Rating: {result.home_team_rating:.3f} | "
            f"Away Rating: {result.away_team_rating:.3f} | "
            f"Trade Impact: {result.trade_impact} | "
            f"Injury Impact: {result.injury_impact}"
        )
    
    def save_prediction_to_database(self, result: PredictionResult) -> bool:
        """Save prediction to database for tracking"""
        try:
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            
            # Check if prediction already exists
            existing = session.query(DBPrediction).filter_by(
                game_pk=result.game_pk,
                model_version=result.model_version
            ).first()
            
            if existing:
                session.close()
                self.logger.prediction_logger.warning(f"Prediction already exists for game {result.game_pk}")
                return False
            
            # Create new prediction record
            db_prediction = DBPrediction(
                game_pk=result.game_pk,
                prediction_date=result.game_date,
                model_version=result.model_version,
                predicted_winner=result.predicted_winner,
                win_probability=result.win_probability,
                confidence_score=result.win_probability,
                primary_factors=json.dumps(result.key_factors)
            )
            
            session.add(db_prediction)
            session.commit()
            session.close()
            
            self.logger.prediction_logger.info(f"💾 Prediction saved to database: Game {result.game_pk}")
            return True
                
        except Exception as e:
            self.logger.error_logger.error(f"Failed to save prediction for game {result.game_pk}: {e}")
            return False
    
    def run_daily_predictions(self, target_date: date = None) -> Dict[str, Any]:
        """Run predictions for all games on a given day"""
        
        if target_date is None:
            target_date = date.today()
        
        self.logger.prediction_logger.info(f"🎯 Starting daily prediction run for {target_date}")
        
        # Get today's games
        games = self.get_todays_games(target_date)
        
        if not games:
            self.logger.prediction_logger.info(f"📅 No games scheduled for {target_date}")
            return {'success': True, 'games': 0, 'predictions': 0}
        
        # Load model if not already loaded
        if not hasattr(self.trainer, 'calculator') or not self.trainer.calculator:
            if not self.load_model():
                self.logger.error_logger.error("Model loading failed - aborting prediction run")
                return {'success': False, 'error': 'Model loading failed'}
        
        # Make predictions for each game
        results = []
        successful_predictions = 0
        
        for game in games:
            result = self.make_prediction(game)
            if result:
                results.append(result)
                successful_predictions += 1
                
                # Save to database
                self.save_prediction_to_database(result)
        
        # Update daily tracking
        self.daily_predictions.extend(results)
        
        # Summary logging
        summary = {
            'date': target_date,
            'games_scheduled': len(games),
            'predictions_made': successful_predictions,
            'success_rate': successful_predictions / len(games) if games else 0,
            'confidence_breakdown': self._get_confidence_breakdown(results)
        }
        
        self.logger.prediction_logger.info(
            f"📊 Daily prediction summary: {successful_predictions}/{len(games)} games predicted "
            f"({summary['success_rate']:.1%} success rate)"
        )
        
        return {'success': True, **summary, 'results': results}
    
    def _get_confidence_breakdown(self, results: List[PredictionResult]) -> Dict[str, int]:
        """Get breakdown of predictions by confidence level"""
        breakdown = {'high': 0, 'medium': 0, 'low': 0}
        for result in results:
            breakdown[result.confidence_level] += 1
        return breakdown
    
    def validate_predictions(self, check_date: date) -> Dict[str, Any]:
        """Validate predictions against actual results for completed games"""
        
        self.logger.performance_logger.info(f"🔍 Validating predictions for {check_date}")
        
        try:
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            
            # Get completed games with predictions
            completed_games = session.query(Game, DBPrediction).join(
                DBPrediction, Game.game_pk == DBPrediction.game_pk
            ).filter(
                Game.game_date == check_date,
                Game.game_status == 'final',
                DBPrediction.prediction_correct.is_(None)  # Not yet validated
            ).all()
            
            if not completed_games:
                session.close()
                self.logger.performance_logger.info(f"📅 No completed games to validate for {check_date}")
                return {'validated': 0}
            
            correct_predictions = 0
            total_validated = 0
            confidence_performance = {'high': [0, 0], 'medium': [0, 0], 'low': [0, 0]}  # [correct, total]
            
            for game, prediction in completed_games:
                
                # Check if prediction was correct
                is_correct = (prediction.predicted_winner == game.winner_team_id)
                
                # Update prediction record with result
                prediction.actual_winner = game.winner_team_id
                prediction.prediction_correct = 1 if is_correct else 0
                
                # Update counters
                if is_correct:
                    correct_predictions += 1
                total_validated += 1
                
                # Track confidence level performance
                confidence = self._get_confidence_from_probability(prediction.win_probability)
                confidence_performance[confidence][1] += 1  # total
                if is_correct:
                    confidence_performance[confidence][0] += 1  # correct
                
                # Log validation
                result_str = "✅ CORRECT" if is_correct else "❌ INCORRECT"
                self.logger.performance_logger.info(
                    f"VALIDATION | Game {game.game_pk} | {prediction.predicted_winner} vs {game.winner_team_id} | {result_str}"
                )
            
            session.commit()
            session.close()
            
            # Calculate performance metrics
            overall_accuracy = correct_predictions / total_validated if total_validated > 0 else 0
            
            performance_summary = {
                'date': check_date,
                'validated': total_validated,
                'correct': correct_predictions,
                'accuracy': overall_accuracy,
                'confidence_performance': {}
            }
            
            # Calculate confidence level accuracies
            for level, (correct, total) in confidence_performance.items():
                if total > 0:
                    performance_summary['confidence_performance'][level] = {
                        'accuracy': correct / total,
                        'count': total
                    }
            
            # Log performance summary
            self.logger.performance_logger.info(
                f"📈 DAILY PERFORMANCE | {check_date} | "
                f"Accuracy: {overall_accuracy:.1%} ({correct_predictions}/{total_validated}) | "
                f"High: {confidence_performance['high'][0]}/{confidence_performance['high'][1]} | "
                f"Medium: {confidence_performance['medium'][0]}/{confidence_performance['medium'][1]} | "
                f"Low: {confidence_performance['low'][0]}/{confidence_performance['low'][1]}"
            )
            
            return performance_summary
                
        except Exception as e:
            self.logger.error_logger.error(f"Prediction validation failed for {check_date}: {e}")
            return {'error': str(e)}
    
    def _get_confidence_from_probability(self, probability: float) -> str:
        """Convert probability to confidence level"""
        if probability >= 0.7:
            return 'high'
        elif probability >= 0.6:
            return 'medium'
        else:
            return 'low'
    
    def get_performance_report(self, days: int = 7) -> Dict[str, Any]:
        """Generate performance report for the last N days"""
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        self.logger.performance_logger.info(f"📊 Generating {days}-day performance report ({start_date} to {end_date})")
        
        try:
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            
            # Get all validated predictions in date range
            predictions = session.query(DBPrediction, Game).join(
                Game, DBPrediction.game_pk == Game.game_pk
            ).filter(
                Game.game_date.between(start_date, end_date),
                DBPrediction.prediction_correct.isnot(None)
            ).all()
            
            session.close()
            
            if not predictions:
                return {'error': 'No validated predictions found in date range'}
            
            # Calculate overall metrics
            total_predictions = len(predictions)
            correct_predictions = sum(1 for pred, _ in predictions if pred.prediction_correct == 1)
            overall_accuracy = correct_predictions / total_predictions
            
            # Confidence breakdown
            confidence_stats = {'high': [0, 0], 'medium': [0, 0], 'low': [0, 0]}
            
            for prediction, game in predictions:
                confidence = self._get_confidence_from_probability(prediction.win_probability)
                confidence_stats[confidence][1] += 1  # total
                if prediction.prediction_correct == 1:
                    confidence_stats[confidence][0] += 1  # correct
            
            # Daily breakdown
            daily_performance = {}
            for prediction, game in predictions:
                date_str = str(game.game_date)
                if date_str not in daily_performance:
                    daily_performance[date_str] = {'correct': 0, 'total': 0}
                
                daily_performance[date_str]['total'] += 1
                if prediction.prediction_correct == 1:
                    daily_performance[date_str]['correct'] += 1
            
            # Format report
            report = {
                'period': f"{start_date} to {end_date}",
                'overall_accuracy': overall_accuracy,
                'total_predictions': total_predictions,
                'correct_predictions': correct_predictions,
                'confidence_performance': {
                    level: {
                        'accuracy': stats[0] / stats[1] if stats[1] > 0 else 0,
                        'count': stats[1]
                    }
                    for level, stats in confidence_stats.items()
                },
                'daily_performance': {
                    date_str: {
                        'accuracy': stats['correct'] / stats['total'],
                        'count': stats['total']
                    }
                    for date_str, stats in daily_performance.items()
                }
            }
            
            # Log report summary
            self.logger.performance_logger.info(
                f"📈 PERFORMANCE REPORT | {days} days | "
                f"Overall: {overall_accuracy:.1%} ({correct_predictions}/{total_predictions}) | "
                f"Avg daily: {np.mean([stats['accuracy'] for stats in report['daily_performance'].values()]):.1%}"
            )
            
            return report
                
        except Exception as e:
            self.logger.error_logger.error(f"Performance report generation failed: {e}")
            return {'error': str(e)}
    
    def schedule_daily_predictions(self):
        """Schedule automatic daily predictions"""
        
        self.logger.prediction_logger.info("⏰ Setting up automatic daily prediction schedule")
        
        # Schedule predictions for 9 AM every day
        schedule.every().day.at("09:00").do(self.run_daily_predictions)
        
        # Schedule validation for previous day at 1 AM
        def validate_yesterday():
            yesterday = date.today() - timedelta(days=1)
            self.validate_predictions(yesterday)
        
        schedule.every().day.at("01:00").do(validate_yesterday)
        
        self.logger.prediction_logger.info("✅ Automatic scheduling configured:")
        self.logger.prediction_logger.info("   📅 Daily predictions: 9:00 AM")
        self.logger.prediction_logger.info("   🔍 Previous day validation: 1:00 AM")
    
    def run_scheduler(self):
        """Run the scheduled prediction system"""
        self.logger.prediction_logger.info("🚀 Starting automated prediction scheduler...")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute


def main():
    """Main entry point for production prediction system"""
    
    print("🎯 MLB Production Prediction System - 2026 Season")
    print("=" * 60)
    print("🏆 Model Performance: 73.2% accuracy on validation data")
    print("📊 Ready for live 2026 season predictions")
    print("=" * 60)
    
    # Initialize predictor
    predictor = ProductionPredictor()
    
    # Load the trained model
    if not predictor.load_model():
        print("❌ Failed to load model. Exiting.")
        return
    
    # Menu for different operations
    while True:
        print("\n🎯 Select Operation:")
        print("1. Run predictions for today")
        print("2. Run predictions for specific date")
        print("3. Validate predictions for completed games")
        print("4. Generate performance report")
        print("5. Start automatic scheduler")
        print("6. Exit")
        
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == '1':
            results = predictor.run_daily_predictions()
            print(f"\n✅ Completed: {results}")
            
        elif choice == '2':
            date_str = input("Enter date (YYYY-MM-DD): ").strip()
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                results = predictor.run_daily_predictions(target_date)
                print(f"\n✅ Completed: {results}")
            except ValueError:
                print("❌ Invalid date format")
                
        elif choice == '3':
            date_str = input("Enter date to validate (YYYY-MM-DD): ").strip()
            try:
                check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                results = predictor.validate_predictions(check_date)
                print(f"\n🔍 Validation results: {results}")
            except ValueError:
                print("❌ Invalid date format")
                
        elif choice == '4':
            days = input("Enter number of days for report (default 7): ").strip()
            days = int(days) if days.isdigit() else 7
            report = predictor.get_performance_report(days)
            
            print(f"\n📊 Performance Report ({days} days):")
            if 'error' not in report:
                print(f"Overall Accuracy: {report['overall_accuracy']:.1%}")
                print(f"Total Predictions: {report['total_predictions']}")
                print("\nConfidence Level Performance:")
                for level, stats in report['confidence_performance'].items():
                    print(f"  {level.title()}: {stats['accuracy']:.1%} ({stats['count']} games)")
            else:
                print(f"Error: {report['error']}")
                
        elif choice == '5':
            print("\n⏰ Starting automatic scheduler...")
            print("Press Ctrl+C to stop")
            try:
                predictor.schedule_daily_predictions()
                predictor.run_scheduler()
            except KeyboardInterrupt:
                print("\n🛑 Scheduler stopped")
                
        elif choice == '6':
            print("\n👋 Goodbye! Your 73.2% accurate model is ready for the 2026 season!")
            break
            
        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    main()
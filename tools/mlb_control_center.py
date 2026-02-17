#!/usr/bin/env python3
"""
MLB Analytics Control Center
============================

Comprehensive command-line interface for all MLB analytics operations.
Your one-stop control center for data collection, predictions, model training, and monitoring.

Features:
- Data Collection Management
- Live Prediction Generation
- Model Training & Updates
- Performance Monitoring
- System Health Checks
- Database Operations

Author: MLB Analytics Team
Date: February 16, 2026
Version: 1.0.0 - Unified Control Center
"""

import os
import sys
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import all system components
try:
    # Data Collection
    from DataCollection import run_daily_collection, run_score_update, run_trade_update
    
    # Analytics & Predictions
    from Analytics.analytics_engine import predict_game, analyze_team
    
    # Model Training
    from ModelTrainer.MLTrainer import (
        train_and_validate_model, quick_train_model, list_saved_models
    )
    
    # Production Monitoring
    from ProductionPredictor.monitoring_dashboard import PredictionMonitor
    # from ProductionPredictor.prediction_workflow import ProductionPredictionWorkflow
    # from ProductionPredictor.quick_start import QuickStartPredictor
    
    # Database
    from Database.config.database import test_connection, get_db
    from Database.models.models import Game, GamePrediction, Team
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Make sure you're in the project root and all dependencies are installed")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLBControlCenter:
    """Unified control center for MLB analytics operations"""
    
    def __init__(self):
        self.monitor = PredictionMonitor()
        # Note: Some components disabled due to import issues
        
    def show_main_menu(self):
        """Display the main menu"""
        print("\n" + "="*60)
        print("⚾ MLB ANALYTICS CONTROL CENTER ⚾")
        print("="*60)
        print("📊 DATA OPERATIONS")
        print("  1. Run Daily Data Collection")
        print("  2. Update Game Scores") 
        print("  3. Update Transactions/Trades")
        print("  4. Check Data Status")
        
        print("\n🎯 PREDICTION OPERATIONS")
        print("  5. Make Today's Predictions")
        print("  6. Quick Single Game Prediction")
        print("  7. View Live Predictions")
        print("  8. Run Prediction Workflow")
        
        print("\n🤖 MODEL OPERATIONS")
        print("  9. Train New Model")
        print(" 10. Update Model with Latest Data")
        print(" 11. Validate Model Performance")
        print(" 12. Model Health Check")
        
        print("\n📈 MONITORING & ANALYSIS")
        print(" 13. Daily Performance Summary")
        print(" 14. Weekly Performance Report")
        print(" 15. Team Analysis")
        print(" 16. System Health Check")
        
        print("\n🔧 SYSTEM OPERATIONS")
        print(" 17. Database Status")
        print(" 18. View Recent Logs")
        print(" 19. Cleanup Operations")
        print(" 20. Full System Test")
        
        print("\n 0. Exit")
        print("="*60)
        
    def run_data_collection(self, mode: str = 'daily'):
        """Run data collection operations"""
        try:
            print(f"\n🔄 Running {mode} data collection...")
            
            if mode == 'daily':
                result = run_daily_collection()
            elif mode == 'scores':
                result = run_score_update()
            elif mode == 'trades':
                result = run_trade_update()
            else:
                print("❌ Invalid collection mode")
                return
            
            print(f"✅ Collection complete: {result.get('total_changes', 0)} changes")
            return result
            
        except Exception as e:
            print(f"❌ Data collection failed: {e}")
            logger.error(f"Data collection error: {e}")
    
    def make_todays_predictions(self):
        """Generate predictions for today's games"""
        try:
            print("\n🎯 Generating today's predictions...")
            
            session = next(get_db())
            try:
                today = date.today()
                games = session.query(Game).filter(Game.game_date == today).all()
                
                if not games:
                    print("📅 No games scheduled for today")
                    return
                
                predictions = []
                for game in games:
                    try:
                        prediction = predict_game(game.home_team_id, game.away_team_id, today)
                        predictions.append({
                            'game': f"{game.away_team_id} @ {game.home_team_id}",
                            'prediction': prediction
                        })
                        print(f"  ⚾ {game.away_team_id} @ {game.home_team_id}: "
                              f"{prediction.predicted_winner} ({prediction.win_probability:.1%})")
                              
                    except Exception as e:
                        print(f"  ❌ Failed to predict {game.away_team_id} @ {game.home_team_id}: {e}")
                
                print(f"\n📊 Generated {len(predictions)} predictions")
                return predictions
                
            finally:
                session.close()
                
        except Exception as e:
            print(f"❌ Prediction generation failed: {e}")
            logger.error(f"Prediction error: {e}")
    
    def quick_game_prediction(self):
        """Make a quick prediction for user-specified teams"""
        try:
            print("\n🎯 Quick Game Prediction")
            print("Available teams: LAD, NYY, HOU, ATL, TB, SF, BOS, TOR, etc.")
            
            home_team = input("Enter home team (3-letter code): ").upper().strip()
            away_team = input("Enter away team (3-letter code): ").upper().strip()
            
            if not home_team or not away_team:
                print("❌ Invalid team codes")
                return
            
            print(f"\n🔮 Predicting {away_team} @ {home_team}...")
            prediction = predict_game(home_team, away_team)
            
            print(f"\n📊 PREDICTION RESULT:")
            print(f"  Winner: {prediction.predicted_winner}")
            print(f"  Probability: {prediction.win_probability:.1%}")
            print(f"  Confidence: {prediction.confidence_level}")
            if hasattr(prediction, 'factors') and prediction.factors:
                print(f"  Key Factors: {', '.join(prediction.factors[:3])}")
            else:
                print("  Key Factors: N/A")
            
            return prediction
            
        except Exception as e:
            print(f"❌ Quick prediction failed: {e}")
            logger.error(f"Quick prediction error: {e}")
    
    def train_new_model(self):
        """Train a new ML model"""
        try:
            print("\n🤖 Training new ML model...")
            print("This may take 2-5 minutes depending on data size...")
            
            result = train_and_validate_model('xgboost')
            
            if result.get('success'):
                print(f"✅ Model trained successfully!")
                print(f"  Accuracy: {result.get('test_accuracy', 0):.1%}")
                print(f"  Features: {result.get('feature_count', 0)}")
                print(f"  Model saved: {result.get('model_path', 'N/A')}")
                return result
            else:
                print(f"❌ Model training failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Model training failed: {e}")
            logger.error(f"Model training error: {e}")
    
    def update_model(self):
        """Update existing model with latest data"""
        try:
            print("\n🔄 Updating model with latest data...")
            
            # Check for recent predictions to validate against
            validation_result = self.validate_recent_predictions()
            
            if validation_result:
                print(f"📊 Recent predictions accuracy: {validation_result['accuracy']:.1%}")
                
                if validation_result['accuracy'] < 0.65:  # Below 65% accuracy
                    print("⚠️  Model performance declining, retraining recommended...")
                    self.train_new_model()
                else:
                    print("✅ Model performance stable, running quick update...")
                    # Run quick training with latest year
                    result = quick_train_model([2026], 'xgboost')
                    if result.get('success'):
                        print(f"✅ Model updated: {result.get('test_accuracy', 0):.1%} accuracy")
                    else:
                        print(f"❌ Update failed: {result.get('error', 'Unknown error')}")
            else:
                print("🔄 No recent predictions to validate, running full retrain...")
                self.train_new_model()
                
        except Exception as e:
            print(f"❌ Model update failed: {e}")
            logger.error(f"Model update error: {e}")
    
    def validate_recent_predictions(self):
        """Validate recent predictions against actual results"""
        try:
            print("\n📊 Validating recent predictions...")
            
            session = next(get_db())
            try:
                # Get predictions from last 7 days with actual results
                cutoff_date = date.today() - timedelta(days=7)
                
                predictions = session.query(GamePrediction).join(Game).filter(
                    Game.game_date >= cutoff_date,
                    Game.game_status == 'completed',
                    GamePrediction.actual_winner.isnot(None)
                ).all()
                
                if not predictions:
                    print("📅 No recent completed predictions found")
                    return None
                
                correct = sum(1 for p in predictions if p.is_correct)
                total = len(predictions)
                accuracy = correct / total
                
                print(f"📈 Recent Performance ({total} games):")
                print(f"  Correct: {correct}")
                print(f"  Total: {total}")
                print(f"  Accuracy: {accuracy:.1%}")
                
                return {'accuracy': accuracy, 'correct': correct, 'total': total}
                
            finally:
                session.close()
                
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            logger.error(f"Validation error: {e}")
            return None
    
    def show_daily_summary(self):
        """Show daily performance summary"""
        try:
            print("\n📊 Daily Performance Summary")
            summary = self.monitor.get_daily_summary()
            
            print(f"Games Scheduled: {summary.get('games_scheduled', 0)}")
            print(f"Predictions Made: {summary.get('predictions_made', 0)}")
            print(f"Games Completed: {summary.get('games_completed', 0)}")
            
            if summary.get('accuracy'):
                print(f"Today's Accuracy: {summary['accuracy']:.1%}")
            
            # Show confidence breakdown
            if summary.get('confidence_performance'):
                print("\nBy Confidence Level:")
                for level, perf in summary['confidence_performance'].items():
                    if perf['total'] > 0:
                        acc = perf['accuracy']
                        print(f"  {level.upper()}: {acc:.1%} ({perf['correct']}/{perf['total']})")
            
            return summary
            
        except Exception as e:
            print(f"❌ Summary failed: {e}")
            logger.error(f"Summary error: {e}")
    
    def show_weekly_report(self):
        """Show weekly performance report"""
        try:
            print("\n📈 Weekly Performance Report")
            weeks = input("Number of weeks to analyze (default 4): ").strip()
            weeks = int(weeks) if weeks.isdigit() else 4
            
            performance = self.monitor.get_weekly_performance(weeks)
            
            print(f"\n📊 Performance Trends ({weeks} weeks):")
            for week_data in performance:
                week_start = week_data['week_start']
                accuracy = week_data['accuracy'] * 100
                total = week_data['total_predictions']
                print(f"  {week_start}: {accuracy:.1f}% ({total} games)")
            
            return performance
            
        except Exception as e:
            print(f"❌ Weekly report failed: {e}")
            logger.error(f"Weekly report error: {e}")
    
    def analyze_specific_team(self):
        """Analyze a specific team"""
        try:
            print("\n🔍 Team Analysis")
            team_id = input("Enter team code (e.g., LAD, NYY, HOU): ").upper().strip()
            
            if not team_id:
                print("❌ Invalid team code")
                return
            
            print(f"\n📊 Analyzing {team_id}...")
            analysis = analyze_team(team_id)
            
            print(f"\n{team_id} Analysis:")
            print(f"  Record: {analysis.wins}-{analysis.losses} ({analysis.win_pct:.3f})")
            print(f"  Runs Scored: {analysis.runs_scored}")
            print(f"  Runs Allowed: {analysis.runs_allowed}")
            print(f"  Strength Rating: {analysis.strength_rating:.3f}")
            print(f"  Recent Form: {analysis.recent_form:.1%}")
            print(f"  Home Advantage: {analysis.home_advantage:.1%}")
            print(f"  Trade Impact: {analysis.trade_impact:.3f}")
            print(f"  Injury Impact: {analysis.injury_impact:.3f}")
            
            return analysis
            
        except Exception as e:
            print(f"❌ Team analysis failed: {e}")
            logger.error(f"Team analysis error: {e}")
    
    def check_system_health(self):
        """Comprehensive system health check"""
        try:
            print("\n🏥 System Health Check")
            health_status = {}
            
            # Database connectivity
            print("🔹 Testing database connection...")
            db_ok = test_connection()
            health_status['database'] = db_ok
            print(f"  Database: {'✅ OK' if db_ok else '❌ FAILED'}")
            
            # Model health
            print("🔹 Checking model health...")
            model_health = self.monitor.get_model_health()
            health_status['model'] = model_health.get('status') == 'healthy'
            print(f"  Model Status: {model_health.get('status', 'unknown').upper()}")
            print(f"  Rolling Accuracy: {model_health.get('rolling_accuracy', 0):.1%}")
            
            # Data freshness
            print("🔹 Checking data freshness...")
            session = next(get_db())
            try:
                latest_game = session.query(Game).order_by(Game.game_date.desc()).first()
                if latest_game:
                    days_old = (date.today() - latest_game.game_date).days
                    data_fresh = days_old <= 3
                    health_status['data_freshness'] = data_fresh
                    print(f"  Latest Game Data: {latest_game.game_date} ({days_old} days old)")
                    print(f"  Data Freshness: {'✅ OK' if data_fresh else '⚠️ STALE'}")
                else:
                    health_status['data_freshness'] = False
                    print(f"  Latest Game Data: ❌ No games found")
            finally:
                session.close()
            
            # Overall health
            all_ok = all(health_status.values())
            print(f"\n🎯 Overall System Health: {'✅ EXCELLENT' if all_ok else '⚠️ NEEDS ATTENTION'}")
            
            return health_status
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            logger.error(f"Health check error: {e}")
    
    def show_data_status(self):
        """Show current data status"""
        try:
            print("\n📊 Data Status Summary")
            
            session = next(get_db())
            try:
                # Game counts
                total_games = session.query(Game).count()
                completed_games = session.query(Game).filter(Game.game_status == 'completed').count()
                today_games = session.query(Game).filter(Game.game_date == date.today()).count()
                
                # Team count
                teams = session.query(Team).count()
                
                print(f"📈 Database Statistics:")
                print(f"  Total Games: {total_games:,}")
                print(f"  Completed Games: {completed_games:,}")
                print(f"  Today's Games: {today_games}")
                print(f"  Teams: {teams}")
                
                # Recent data
                latest_game = session.query(Game).order_by(Game.game_date.desc()).first()
                if latest_game:
                    print(f"  Latest Game Date: {latest_game.game_date}")
                
                return {
                    'total_games': total_games,
                    'completed_games': completed_games,
                    'today_games': today_games,
                    'teams': teams
                }
                
            finally:
                session.close()
                
        except Exception as e:
            print(f"❌ Data status check failed: {e}")
            logger.error(f"Data status error: {e}")
    
    def run(self):
        """Main control loop"""
        while True:
            try:
                self.show_main_menu()
                choice = input("\n🎯 Select option (0-20): ").strip()
                
                if choice == '0':
                    print("\n👋 Goodbye! Your MLB Analytics system is ready.")
                    break
                    
                elif choice == '1':
                    self.run_data_collection('daily')
                elif choice == '2':
                    self.run_data_collection('scores')
                elif choice == '3':
                    self.run_data_collection('trades')
                elif choice == '4':
                    self.show_data_status()
                    
                elif choice == '5':
                    self.make_todays_predictions()
                elif choice == '6':
                    self.quick_game_prediction()
                elif choice == '7':
                    predictions = self.monitor.get_live_predictions()
                    print(f"\n🔮 Found {len(predictions)} live predictions")
                    for pred in predictions[:5]:  # Show first 5
                        print(f"  {pred['away_team']['city']} @ {pred['home_team']['city']}")
                elif choice == '8':
                    print("\n🚀 Running full prediction workflow...")
                    print("⚠️  Workflow component currently disabled - use individual functions")
                    # self.workflow.run_daily_predictions()
                    
                elif choice == '9':
                    self.train_new_model()
                elif choice == '10':
                    self.update_model()
                elif choice == '11':
                    self.validate_recent_predictions()
                elif choice == '12':
                    model_health = self.monitor.get_model_health()
                    print(f"\n🤖 Model Health: {json.dumps(model_health, indent=2, default=str)}")
                    
                    # Also show available models
                    print(f"\n📁 Available Models:")
                    models = list_saved_models()
                    if models:
                        for i, model in enumerate(models[:5]):
                            print(f"  {i+1}. {model['name']} ({model['model_type']}, {model.get('accuracy', 0):.3f} acc)")
                    else:
                        print("  No saved models found")
                    
                elif choice == '13':
                    self.show_daily_summary()
                elif choice == '14':
                    self.show_weekly_report()
                elif choice == '15':
                    self.analyze_specific_team()
                elif choice == '16':
                    self.check_system_health()
                    
                elif choice == '17':
                    db_ok = test_connection()
                    print(f"\n💾 Database Status: {'✅ Connected' if db_ok else '❌ Disconnected'}")
                elif choice == '18':
                    log_dir = project_root / 'logs'
                    if log_dir.exists():
                        print(f"\n📋 Log files in {log_dir}:")
                        for log_file in log_dir.rglob('*.log'):
                            size = log_file.stat().st_size / 1024  # KB
                            print(f"  {log_file.name}: {size:.1f} KB")
                    else:
                        print("\n📋 No log directory found")
                elif choice == '19':
                    print("\n🧹 Cleanup operations:")
                    print("  1. Clear old log files")
                    print("  2. Clean temporary files")
                    print("  (Not implemented - manual cleanup recommended)")
                elif choice == '20':
                    print("\n🔬 Running full system test...")
                    self.check_system_health()
                    self.show_data_status()
                    print("✅ System test complete")
                    
                else:
                    print("❌ Invalid option. Please select 0-20.")
                
                input("\n⏎ Press Enter to continue...")
                
            except KeyboardInterrupt:
                print("\n\n🛑 Interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                logger.error(f"Control center error: {e}")
                input("\n⏎ Press Enter to continue...")

def main():
    """Entry point"""
    try:
        print("🚀 Initializing MLB Analytics Control Center...")
        control_center = MLBControlCenter()
        control_center.run()
    except Exception as e:
        print(f"❌ Failed to start control center: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
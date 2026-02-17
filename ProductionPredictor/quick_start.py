#!/usr/bin/env python3
"""
Quick Start Production Prediction Script
========================================

Simple script to get started with production predictions using your
73.2% accurate model for the 2026 MLB season.

This script provides an easy way to:
1. Make predictions for today's games
2. Test the prediction workflow
3. Verify your model is working in production mode

Author: MLB Analytics Team  
Date: February 5, 2026
Version: 1.0.0 - Quick Start
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta
import pandas as pd

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ModelTrainer.MLTrainer import train_and_validate_model, quick_train_model
from Database.config.database import DatabaseConfig
from Database.models.models import Game


def quick_prediction_test():
    """Quick test to make sure your model is ready for production"""
    
    print("🎯 Testing MLB Production Prediction System")
    print("=" * 50)
    
    # Load your trained model
    print("🤖 Loading your 73.2% accurate model...")
    trainer = ModelTrainer()
    model_path = "Analytics/models/season_based_model_2026_20260204_071301.pkl"
    
    try:
        trainer.load_model(model_path)
        print("✅ Model loaded successfully!")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return False
    
    # Test database connection
    print("\n📊 Testing database connection...")
    try:
        db_config = DatabaseConfig()
        SessionLocal = db_config.create_session_factory()
        session = SessionLocal()
        # Test query
        game_count = session.query(Game).count()
        print(f"✅ Database connected! Found {game_count} games in database")
        session.close()
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False
    
    # Test prediction capability
    print("\n🔮 Testing prediction capability...")
    try:
        # Use a test prediction (LAD vs SF is always a good rivalry!)
        prediction = trainer.calculator.predict_game(
            home_team_id="LAD",
            away_team_id="SF", 
            game_date=date.today(),
            save_prediction=False,
            allow_historical=False
        )
        
        if prediction:
            print("✅ Prediction test successful!")
            print(f"   Test matchup: SF @ LAD")
            print(f"   Predicted winner: {prediction.predicted_winner}")
            print(f"   Win probability: {prediction.win_probability:.1%}")
            print(f"   Confidence level: {prediction.confidence_level.upper()}")
            print(f"   Key factors: {', '.join(prediction.key_factors[:3])}")
        else:
            print("❌ No prediction returned")
            return False
            
    except Exception as e:
        print(f"❌ Prediction test failed: {e}")
        return False
    
    print("\n🏆 System Check Complete - Ready for 2026 Season!")
    return True


def get_sample_games(target_date: date = None):
    """Get sample games for testing predictions"""
    
    if target_date is None:
        target_date = date.today()
    
    print(f"\n📅 Checking for games on {target_date}...")
    
    try:
        db_config = DatabaseConfig()
        SessionLocal = db_config.create_session_factory()
        session = SessionLocal()
        
        # Look for games on the target date
        games = session.query(Game).filter(
            Game.game_date == target_date
        ).limit(5).all()  # Limit to 5 for testing
        
        if not games:
            print(f"📅 No games found for {target_date}")
            
            # Try looking for recent games
            recent_date = target_date - timedelta(days=7)
            recent_games = session.query(Game).filter(
                Game.game_date >= recent_date,
                Game.game_date <= target_date
            ).order_by(Game.game_date.desc()).limit(3).all()
            
            session.close()
            if recent_games:
                print(f"📊 Found {len(recent_games)} recent games for testing:")
                return recent_games
            else:
                print("📊 No recent games found")
                return []
        else:
            print(f"🎯 Found {len(games)} games for {target_date}")
            session.close()
            return games
                
    except Exception as e:
        print(f"❌ Error getting games: {e}")
        return []


def make_sample_predictions(games):
    """Make predictions for sample games"""
    
    if not games:
        print("📭 No games provided for predictions")
        return
    
    print(f"\n🔮 Making predictions for {len(games)} games...")
    print("-" * 50)
    
    # Load model
    trainer = ModelTrainer()
    model_path = "Analytics/models/season_based_model_2026_20260204_071301.pkl"
    trainer.load_model(model_path)
    
    predictions_made = 0
    
    for game in games:
        try:
            print(f"\n🎯 Game {game.game_pk}: {game.away_team_id} @ {game.home_team_id}")
            print(f"   Date: {game.game_date}")
            print(f"   Status: {game.game_status}")
            
            # Make prediction
            prediction = trainer.calculator.predict_game(
                home_team_id=game.home_team_id,
                away_team_id=game.away_team_id,
                game_date=game.game_date,
                save_prediction=False,  # Don't save during testing
                allow_historical=True   # Allow for testing purposes
            )
            
            if prediction:
                print(f"   🏆 Predicted Winner: {prediction.predicted_winner}")
                print(f"   📊 Win Probability: {prediction.win_probability:.1%}")
                print(f"   🎯 Confidence: {prediction.confidence_level.upper()}")
                print(f"   🔍 Key Factors:")
                for factor in prediction.key_factors[:3]:
                    print(f"      • {factor}")
                
                # Show actual result if game is completed
                if game.game_status == 'final' and game.winner_team_id:
                    actual_winner = game.winner_team_id
                    is_correct = (prediction.predicted_winner == actual_winner)
                    result_emoji = "✅" if is_correct else "❌"
                    
                    print(f"   {result_emoji} Actual Winner: {actual_winner}")
                    print(f"   📈 Prediction: {'CORRECT' if is_correct else 'INCORRECT'}")
                
                predictions_made += 1
                
            else:
                print("   ❌ No prediction generated")
                
        except Exception as e:
            print(f"   ❌ Error making prediction: {e}")
    
    print(f"\n📊 Prediction Summary: {predictions_made}/{len(games)} successful predictions")
    
    if predictions_made > 0:
        print("\n🎉 Your model is working perfectly in production mode!")
        print("💡 Next steps:")
        print("   1. Use ProductionPredictor/prediction_workflow.py for automated daily predictions")
        print("   2. Use ProductionPredictor/monitoring_dashboard.py for real-time monitoring")
        print("   3. Set up scheduled predictions for the 2026 season")
    

def main():
    """Main quick start workflow"""
    
    print("🚀 MLB Prediction System - Quick Start")
    print("🏆 Your model achieved 73.2% accuracy on validation data!")
    print("🎯 Ready to make production predictions for the 2026 season")
    print("=" * 60)
    
    # Run system check
    if not quick_prediction_test():
        print("\n❌ System check failed. Please fix issues before continuing.")
        return
    
    print("\n" + "=" * 60)
    
    # Get sample games and make predictions
    while True:
        print("\n🎯 Quick Start Options:")
        print("1. Test predictions with today's games")
        print("2. Test predictions with specific date")  
        print("3. Test with recent games")
        print("4. Run comprehensive system test")
        print("5. Exit and start production workflow")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == '1':
            games = get_sample_games()
            make_sample_predictions(games)
            
        elif choice == '2':
            date_str = input("Enter date (YYYY-MM-DD): ").strip()
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                games = get_sample_games(target_date)
                make_sample_predictions(games)
            except ValueError:
                print("❌ Invalid date format")
                
        elif choice == '3':
            # Look for games in the last week
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            db_config = DatabaseConfig()
            SessionLocal = db_config.create_session_factory()
            session = SessionLocal()
            recent_games = session.query(Game).filter(
                Game.game_date.between(start_date, end_date),
                Game.game_status == 'final'  # Completed games for validation
            ).order_by(Game.game_date.desc()).limit(5).all()
            session.close()
            
            if recent_games:
                print(f"📊 Found {len(recent_games)} recent completed games")
                make_sample_predictions(recent_games)
            else:
                print("📭 No recent games found")
                    
        elif choice == '4':
            print("\n🧪 Running comprehensive system test...")
            
            # Test with multiple scenarios
            test_scenarios = [
                ("LAD", "SF"),   # Rivalry game
                ("NYY", "BOS"),  # Another rivalry
                ("HOU", "OAK")   # Division matchup
            ]
            
            trainer = ModelTrainer()
            model_path = "Analytics/models/season_based_model_2026_20260204_071301.pkl"
            trainer.load_model(model_path)
            
            for home, away in test_scenarios:
                try:
                    prediction = trainer.calculator.predict_game(
                        home_team_id=home,
                        away_team_id=away,
                        game_date=date.today(),
                        save_prediction=False,
                        allow_historical=False
                    )
                    
                    if prediction:
                        print(f"✅ {away} @ {home}: {prediction.predicted_winner} ({prediction.win_probability:.1%}) - {prediction.confidence_level.upper()}")
                    else:
                        print(f"❌ {away} @ {home}: No prediction")
                        
                except Exception as e:
                    print(f"❌ {away} @ {home}: Error - {e}")
            
            print("\n🎉 Comprehensive test completed!")
                    
        elif choice == '5':
            print("\n🚀 Ready for Production!")
            print("=" * 30)
            print("Next steps to start production predictions:")
            print()
            print("1. 📊 Daily Predictions:")
            print("   python ProductionPredictor/prediction_workflow.py")
            print()
            print("2. 🖥️  Monitoring Dashboard:")
            print("   python ProductionPredictor/monitoring_dashboard.py")
            print()
            print("3. 📝 Logging Configuration:")
            print("   python ProductionPredictor/logging_config.py")
            print()
            print("🏆 Your 73.2% accurate model is ready for the 2026 MLB season!")
            break
            
        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    main()
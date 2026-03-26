#!/usr/bin/env python3
"""
MLB GAME PREDICTIONS — PRODUCTION SYSTEM
=========================================

Daily game winner predictions for MLB with adaptive accuracy calibration.

The system optimizes for PREDICTION ACCURACY. Betting is a downstream use case —
the model doesn't know or care about betting. It just tries to be correct.

Flow:
1. Gets today's scheduled games from the database
2. Runs each matchup through the trained XGBoost model  
3. Applies adaptive confidence calibration (learned from recent accuracy)
4. Saves predictions and confidence levels to the database
5. Reports which predictions are high-confidence vs uncertain

Author: MLB Analytics
Version: v3.0 (Accuracy-focused)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ModelTrainer.OptimizedMLTrainer import OptimizedMLTrainer, get_session
from ModelTrainer.AdaptiveLearning import AdaptiveLearningEngine
from Database.config.database import DatabaseConfig

def get_model_accuracy_from_db():
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

def get_live_games_today():
    """Get REAL games scheduled for TODAY ONLY"""
    
    today = date.today()
    print(f"🔍 Checking for LIVE games on {today}...")
    
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
            WHERE game_date = :today
            AND game_status IN ('scheduled', 'in_progress', 'postponed', 'pre-game')
            ORDER BY game_pk
        """)
        
        games = session.execute(query, {'today': today}).fetchall()
        
        print(f"📊 Found {len(games)} LIVE games scheduled for today")
        return games
        
    except Exception as e:
        print(f"❌ Error getting live games: {e}")
        return []

def get_live_games_for_date(target_date):
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
        return games
        
    except Exception as e:
        print(f"❌ Error getting live games: {e}")
        return []

def get_adaptive_parameters():
    """Load current adaptive learning parameters to calibrate confidence for accuracy.
    
    Returns neutral/default parameters if adaptive tables are empty (e.g. after model retraining).
    This prevents stale calibration data from a previous model from poisoning the new one.
    """
    try:
        # Initialize adaptive learning engine
        adaptive_engine = AdaptiveLearningEngine()
        adaptive_engine.load_model()
        
        # Get current adaptive parameters
        adaptive_params = adaptive_engine.get_adaptive_parameters()
        
        # Extract key parameters with defaults
        parameters = adaptive_params.get('parameters', {})
        calibration = adaptive_params.get('calibration', {})
        feature_weights = adaptive_params.get('feature_weights', {})
        
        # Check if adaptive data actually exists
        has_adaptive_data = bool(parameters) or bool(calibration) or bool(feature_weights)
        
        if not has_adaptive_data:
            print("🧠 ADAPTIVE LEARNING: No calibration data yet (new model)")
            print("   Using raw model output — adaptive adjustments activate after 30+ predictions")
            return {
                'confidence_calibration': {},
                'feature_weights': {},
                'adaptive_active': False
            }
        
        print("🧠 LOADING ADAPTIVE ACCURACY CALIBRATION")
        print("=" * 50)
        
        accuracy_trend = float(parameters.get('overall_accuracy_trend', 55.0))
        confidence_reliable = float(parameters.get('confidence_reliability', 1.0))
        
        adaptive_config = {
            'confidence_calibration': {k: float(v) for k, v in calibration.items()},
            'feature_weights': {k: float(v) for k, v in feature_weights.items()},
            'accuracy_trend': accuracy_trend,
            'confidence_reliability': confidence_reliable,
            'adaptive_active': True
        }
        
        print(f"✅ Accuracy trend: {accuracy_trend:.1f}%")
        print(f"🎯 Confidence reliability: {confidence_reliable:.3f}")
        print(f"🧠 Feature weight adjustments: {len(feature_weights)} features")
        print(f"📊 Confidence calibration bins: {len(calibration)}")
        
        return adaptive_config
        
    except Exception as e:
        print(f"⚠️ Could not load adaptive parameters: {e}")
        print("📝 Using raw model output...")
        return {
            'confidence_calibration': {},
            'feature_weights': {},
            'adaptive_active': False
        }

def apply_adaptive_adjustments(prediction, adaptive_config):
    """Apply adaptive accuracy calibration to a prediction.
    
    Adjusts confidence so it reflects actual real-world accuracy.
    If the model says 70% but historically it's 60% accurate in that range,
    calibrate the confidence down to be honest.
    
    No betting thresholds — just calibrated confidence.
    """
    try:
        if not adaptive_config.get('adaptive_active', False):
            prediction['adaptive_applied'] = False
            return prediction
        
        confidence = prediction['confidence']
        confidence_pct = confidence * 100
        
        # Apply bin-specific confidence calibration
        calibration = adaptive_config.get('confidence_calibration', {})
        calibration_factor = 1.0
        
        if 50 <= confidence_pct < 60:
            calibration_factor = calibration.get('50-60%', 1.0)
        elif 60 <= confidence_pct < 70:
            calibration_factor = calibration.get('60-70%', 1.0)
        elif 70 <= confidence_pct < 80:
            calibration_factor = calibration.get('70-80%', 1.0)
        elif 80 <= confidence_pct < 90:
            calibration_factor = calibration.get('80-90%', 1.0)
        elif confidence_pct >= 90:
            calibration_factor = calibration.get('90%+', 1.0)
        
        calibrated_confidence = min(0.99, max(0.50, confidence * calibration_factor))
        
        # Classify confidence level (for display, NOT for betting decisions)
        if calibrated_confidence >= 0.70:
            confidence_tier = 'HIGH'
        elif calibrated_confidence >= 0.60:
            confidence_tier = 'MEDIUM'
        else:
            confidence_tier = 'LOW'
        
        prediction['original_confidence'] = confidence
        prediction['confidence'] = calibrated_confidence
        prediction['confidence_tier'] = confidence_tier
        prediction['adaptive_applied'] = True
        prediction['calibration_factor'] = calibration_factor
        
        return prediction
        
    except Exception as e:
        print(f"⚠️ Error applying adaptive adjustments: {e}")
        prediction['adaptive_applied'] = False
        return prediction

def make_live_betting_predictions(games):
    """Make predictions for live games with adaptive accuracy calibration."""
    
    if not games:
        print("📭 NO GAMES TODAY - NO PREDICTIONS TO MAKE")
        return
    
    print(f"\n🎯 MAKING PREDICTIONS FOR {len(games)} GAMES")
    print("=" * 60)
    print("🧠 Adaptive accuracy calibration from recent performance")
    print("=" * 60)
    
    # Load adaptive learning parameters
    adaptive_config = get_adaptive_parameters()
    
    # Load model from database
    trainer = OptimizedMLTrainer()
    
    print(f"🤖 Loading model from database...")
    
    if not trainer.load_optimized_model('betting_winner_predictor'):
        print("❌ CRITICAL ERROR: Cannot load model from database!")
        return
        
    print(f"✅ Model loaded ({len(trainer.feature_names)} features)")
    
    predictions = []
    high_confidence_count = 0
    
    for i, game in enumerate(games, 1):
        game_pk = game.game_pk
        away = game.away_team_id
        home = game.home_team_id
        status = game.game_status
        
        print(f"\n🏟️  GAME {i}/{len(games)} - PK: {game_pk}")
        print(f"   {away} @ {home}")
        print(f"   Status: {status}")
        print(f"   Date: {game.game_date}")
        
        try:
            # Make prediction
            prediction = trainer.predict_winner(away, home, game.game_date)
            
            if 'error' in prediction:
                print(f"   ❌ PREDICTION FAILED: {prediction['error']}")
                continue
            
            # Apply adaptive accuracy calibration
            original_confidence = prediction['confidence']
            prediction = apply_adaptive_adjustments(prediction, adaptive_config)
            
            # Extract prediction data
            winner = prediction['predicted_winner']
            confidence = prediction['confidence']
            confidence_tier = prediction.get('confidence_tier', 'MEDIUM')
            h2h_games = prediction['h2h_sample_size']
            features_used = prediction.get('features_used', 0)
            data_quality = min(1.0, (h2h_games + features_used) / 100)
            
            # Show calibration info
            if prediction.get('adaptive_applied', False):
                cal_factor = prediction.get('calibration_factor', 1.0)
                print(f"   🧠 CALIBRATED: {original_confidence:.1%} → {confidence:.1%} (factor: {cal_factor:.3f})")
            
            is_high_confidence = confidence_tier == 'HIGH'
            if is_high_confidence:
                high_confidence_count += 1
            
            # Display prediction
            tier_emoji = {
                'HIGH': '�',
                'MEDIUM': '�',
                'LOW': '�'
            }.get(confidence_tier, '⚪')
            
            print(f"   🏆 PREDICTED WINNER: {winner}")
            print(f"   📊 CONFIDENCE: {confidence:.1%}" + (" (calibrated)" if prediction.get('adaptive_applied') else ""))
            print(f"   {tier_emoji} CONFIDENCE TIER: {confidence_tier}")
            print(f"   📈 DATA QUALITY: {data_quality:.3f}")
            print(f"   📚 H2H SAMPLE: {h2h_games} games")
            
            # Map confidence tier to the legacy betting_recommendation field for DB compatibility
            betting_rec_map = {'HIGH': 'STRONG', 'MEDIUM': 'MODERATE', 'LOW': 'AVOID'}
            betting_rec = betting_rec_map.get(confidence_tier, 'AVOID')
            
            # Save prediction to database (individual record via trainer)
            saved = trainer.save_prediction_to_db(away, home, prediction, str(game.game_date))
            if saved:
                print(f"   💾 Prediction saved to database")
            else:
                print(f"   ⚠️  Database logging failed")
            
            # Store for batch database save
            prediction_data = {
                'game_pk': game_pk,
                'game_date': str(game.game_date),
                'away_team': away,
                'home_team': home,
                'predicted_winner': winner,
                'confidence': float(confidence),
                'confidence_tier': confidence_tier,
                'betting_recommendation': betting_rec,  # Legacy field for DB schema
                'data_quality': float(data_quality),
                'h2h_sample_size': int(h2h_games),
                'is_high_confidence': is_high_confidence,
                'timestamp': datetime.now().isoformat()
            }
            predictions.append(prediction_data)
            
        except Exception as e:
            print(f"   ❌ ERROR MAKING PREDICTION: {e}")
    
    # Save all predictions to database
    if predictions:
        print(f"\n💾 SAVING PREDICTIONS...")
        print("-" * 30)
        
        db_saved = save_predictions_to_database(predictions, high_confidence_count)
        
        if db_saved:
            print(f"✅ Predictions saved to database")
        else:
            print(f"❌ Failed to save predictions to database")
    
    # Summary
    model_acc = get_model_accuracy_from_db()
    print(f"\n" + "=" * 60)
    print(f"🎯 PREDICTION SUMMARY FOR {date.today()}")
    print(f"=" * 60)
    print(f"📊 Total Games: {len(games)}")
    print(f"✅ Predictions Made: {len(predictions)}")
    print(f"� High Confidence: {high_confidence_count}")
    print(f"🎲 Model: {model_acc['version']} — CV Accuracy: {model_acc['cv_accuracy']}%")
    print(f"📈 Test Accuracy: {model_acc['test_accuracy']}%")
    
    if high_confidence_count > 0:
        print(f"\n� HIGH CONFIDENCE PREDICTIONS:")
        print("-" * 40)
        
        for pred in predictions:
            if pred['is_high_confidence']:
                winner = pred['predicted_winner']
                conf = pred['confidence']
                away = pred['away_team']
                home = pred['home_team']
                print(f"   🟢 {away} @ {home} → {winner} ({conf:.1%})")
    
    # Show all predictions sorted by confidence
    print(f"\n📋 ALL PREDICTIONS (by confidence):")
    print("-" * 40)
    sorted_preds = sorted(predictions, key=lambda x: x['confidence'], reverse=True)
    for pred in sorted_preds:
        tier = pred['confidence_tier']
        emoji = {'HIGH': '🟢', 'MEDIUM': '🟡', 'LOW': '🔴'}.get(tier, '⚪')
        print(f"   {emoji} {pred['away_team']} @ {pred['home_team']} → {pred['predicted_winner']} ({pred['confidence']:.1%}) [{tier}]")
    
    print(f"\n✅ PREDICTIONS COMPLETE!")

def save_predictions_to_database(predictions, high_confidence_count):
    """Save predictions to daily_predictions table."""
    
    if not predictions:
        print("   ❌ No predictions to save")
        return False
    
    try:
        load_dotenv('secrets.env')
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            print("   ❌ DATABASE_URL not found in environment")
            return False
        
        engine = create_engine(database_url)
        
        print(f"   💾 Saving {len(predictions)} predictions to database...")
        
        with engine.connect() as conn:
            insert_sql = '''
            INSERT INTO daily_predictions 
            (prediction_date, game_pk, away_team, home_team, predicted_winner, confidence,
             betting_recommendation, is_betting_opportunity, data_quality, h2h_sample_size,
             model_version, prediction_timestamp, session_total_games, session_betting_opportunities,
             session_model_accuracy, session_high_confidence_accuracy)
            VALUES 
            (:prediction_date, :game_pk, :away_team, :home_team, :predicted_winner, :confidence,
             :betting_recommendation, :is_betting_opportunity, :data_quality, :h2h_sample_size,
             :model_version, :prediction_timestamp, :session_total_games, :session_betting_opportunities,
             :session_model_accuracy, :session_high_confidence_accuracy)
            ON CONFLICT (prediction_date, game_pk, model_version) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                betting_recommendation = EXCLUDED.betting_recommendation,
                is_betting_opportunity = EXCLUDED.is_betting_opportunity,
                data_quality = EXCLUDED.data_quality,
                h2h_sample_size = EXCLUDED.h2h_sample_size,
                prediction_timestamp = EXCLUDED.prediction_timestamp;
            '''
            
            model_version = 'accuracy_focused_v4.0'
            model_acc = get_model_accuracy_from_db()
            
            for pred in predictions:
                game_date = pred.get('game_date', str(date.today()))
                
                # Map confidence tiers to legacy betting_recommendation column
                betting_rec = pred.get('betting_recommendation', 'AVOID')
                is_high_conf = pred.get('is_high_confidence', False)
                
                record = {
                    'prediction_date': game_date,
                    'game_pk': pred['game_pk'],
                    'away_team': pred['away_team'],
                    'home_team': pred['home_team'],
                    'predicted_winner': pred['predicted_winner'],
                    'confidence': round(pred['confidence'] * 100, 2),
                    'betting_recommendation': betting_rec,
                    'is_betting_opportunity': is_high_conf,
                    'data_quality': pred['data_quality'],
                    'h2h_sample_size': pred['h2h_sample_size'],
                    'model_version': model_version,
                    'prediction_timestamp': pred['timestamp'],
                    'session_total_games': len(predictions),
                    'session_betting_opportunities': high_confidence_count,
                    'session_model_accuracy': model_acc['cv_accuracy'],
                    'session_high_confidence_accuracy': model_acc['test_accuracy']
                }
                
                conn.execute(text(insert_sql), record)
            
            conn.commit()
            print(f"   ✅ Saved {len(predictions)} predictions to database")
            return True
            
    except Exception as e:
        print(f"   ❌ Database save failed: {e}")
        return False

def main(target_date=None):
    """Main prediction workflow"""
    
    if target_date:
        if isinstance(target_date, str):
            from datetime import datetime
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        
        print("🎯 MLB GAME PREDICTIONS")
        print("=" * 50)
        print(f"📅 {target_date.strftime('%A, %B %d, %Y')} (CUSTOM DATE)")
        model_acc = get_model_accuracy_from_db()
        print(f"🎲 Model: {model_acc['version']} (CV {model_acc['cv_accuracy']}%)")
        print("=" * 50)
        
        live_games = get_live_games_for_date(target_date)
    else:
        print("🎯 MLB GAME PREDICTIONS")
        print("=" * 50)
        print(f"📅 {date.today().strftime('%A, %B %d, %Y')}")
        model_acc = get_model_accuracy_from_db()
        print(f"🎲 Model: {model_acc['version']} (CV {model_acc['cv_accuracy']}%)")
        print("=" * 50)
        
        live_games = get_live_games_today()
    
    try:
        if not live_games:
            target_date_str = target_date.strftime('%Y-%m-%d') if target_date else 'TODAY'
            print(f"\n📭 NO GAMES SCHEDULED FOR {target_date_str}")
            print(f"🎯 Model is ready for predictions")
            return
        
        make_live_betting_predictions(live_games)
        
    except KeyboardInterrupt:
        print(f"\n👋 Prediction session cancelled")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
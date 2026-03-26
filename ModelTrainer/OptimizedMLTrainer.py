#!/usr/bin/env python3
"""
Optimized MLB Betting Prediction Model
=====================================

Enhanced model using the new comprehensive feature engineering system.
Uses 57 advanced features from player stats aggregation and transaction intelligence.

Key Features:
- Uses the new WorkingFeatureEngineer with 57 proven features
- Leverages player stats aggregation and transaction data
- Team batting, pitching, transaction, and head-to-head features
- Optimized for betting accuracy with proper confidence calibration
- Maximum signal from comprehensive data utilization

Author: MLB Betting Analytics
Version: 4.0.0 (Enhanced with WorkingFeatureEngineer)
"""

import sys
import os
import logging
import pickle
import json
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the new feature engineering system
try:
    from Analytics.working_feature_engineering import WorkingFeatureEngineer
    FEATURE_ENGINEERING_AVAILABLE = True
except ImportError:
    FEATURE_ENGINEERING_AVAILABLE = False
    print("❌ WorkingFeatureEngineer not available")

# Database imports
try:
    from Database.config.database import DatabaseConfig
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

# Machine learning
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import accuracy_score, classification_report, log_loss
    import xgboost as xgb
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# OPTIMIZED CONFIGURATION FOR BETTING
# =============================================================================

CONFIG = {
    'training_years': [2022, 2023, 2024, 2025],  # 4 years, skip 2020/2021 (COVID + empty)
    'min_games_per_matchup': 3,  # Minimum H2H history for reliability
    'recent_form_games': 10,  # Recent form window
    'model_save_dir': 'Analytics/models',
    'feature_importance_threshold': 0.001,  # Only keep meaningful features
    'confidence_threshold': 0.6,  # Minimum confidence for betting recommendations
    'regular_season_only': True,  # Filter out spring training games from training data
}

# THE 21 PROVEN FEATURES (from analysis of the failed enhanced model)
PROVEN_FEATURES = [
    # Head-to-Head Features (Most Important - 49.6% of total importance)
    'h2h_team_a_win_pct',
    'h2h_team_b_win_pct', 
    'h2h_competitiveness',
    'h2h_avg_total_runs',
    'h2h_run_differential',
    'h2h_games_played',
    
    # Recent Form Features (35.2% of total importance)
    'team_a_recent_win_pct_10',
    'team_b_recent_win_pct_10',
    'team_a_recent_runs_per_game_10',
    'team_b_recent_runs_per_game_10',
    'team_a_recent_run_differential_10',
    'team_b_recent_run_differential_10',
    'recent_form_momentum_a',
    'recent_form_momentum_b',
    
    # Comparative Features (15.2% of total importance)
    'recent_runs_per_game_difference',
    'recent_run_differential_difference',
    'recent_win_pct_difference',
    'head_to_head_advantage_a',
    'form_vs_history_consistency',
    
    # Data Quality & Context (Remaining importance)
    'data_completeness_score',
    'matchup_sample_size'
]

# Global session
_session = None

# =============================================================================
# DATABASE UTILITIES
# =============================================================================

def get_session():
    """Get database session"""
    global _session
    if not DATABASE_AVAILABLE:
        raise RuntimeError("Database not available")
    
    if _session is None:
        db_config = DatabaseConfig()
        engine = db_config.create_engine()
        Session = sessionmaker(bind=engine)
        _session = Session()
    
    return _session

def safe_divide(a, b, default=0.5):
    """Safely divide with sensible defaults for betting"""
    try:
        if a is None or b is None or pd.isna(a) or pd.isna(b) or b == 0:
            return default
        result = float(a) / float(b)
        return result if not pd.isna(result) else default
    except:
        return default

# =============================================================================
# OPTIMIZED FEATURE ENGINEERING
# =============================================================================

class OptimizedFeatureEngineer:
    """Create the 21 proven features for betting accuracy"""
    
    def __init__(self):
        self.session = get_session()
    
    def get_head_to_head_features(self, team_a: str, team_b: str, as_of_date: date) -> Dict[str, float]:
        """Get head-to-head features (most important for betting)"""
        try:
            # Look back 3 years for H2H history
            cutoff_date = as_of_date - timedelta(days=365 * 3)
            
            h2h_query = text("""
                SELECT 
                    home_team_id,
                    away_team_id,
                    home_score,
                    away_score,
                    winner_team_id
                FROM games
                WHERE ((home_team_id = :team_a AND away_team_id = :team_b) 
                    OR (home_team_id = :team_b AND away_team_id = :team_a))
                AND game_date >= :cutoff_date
                AND game_date < :as_of_date
                AND home_score IS NOT NULL 
                AND away_score IS NOT NULL
                ORDER BY game_date DESC
            """)
            
            results = self.session.execute(h2h_query, {
                'team_a': team_a,
                'team_b': team_b,
                'cutoff_date': cutoff_date,
                'as_of_date': as_of_date
            }).fetchall()
            
            if len(results) < CONFIG['min_games_per_matchup']:
                # Not enough H2H history - use league averages
                return {
                    'h2h_team_a_win_pct': 0.5,
                    'h2h_team_b_win_pct': 0.5,
                    'h2h_competitiveness': 0.5,
                    'h2h_avg_total_runs': 9.0,
                    'h2h_run_differential': 0.0,
                    'h2h_games_played': 0
                }
            
            # Analyze H2H results
            team_a_wins = 0
            team_b_wins = 0
            total_runs = 0
            team_a_runs = 0
            team_b_runs = 0
            close_games = 0
            
            for game in results:
                total_runs += game.home_score + game.away_score
                
                # Determine runs scored by each team
                if game.home_team_id == team_a:
                    team_a_runs += game.home_score
                    team_b_runs += game.away_score
                else:
                    team_b_runs += game.home_score
                    team_a_runs += game.away_score
                
                # Count wins
                if game.winner_team_id == team_a:
                    team_a_wins += 1
                elif game.winner_team_id == team_b:
                    team_b_wins += 1
                
                # Count close games (1-2 run difference)
                if abs(game.home_score - game.away_score) <= 2:
                    close_games += 1
            
            total_games = len(results)
            
            return {
                'h2h_team_a_win_pct': safe_divide(team_a_wins, total_games, 0.5),
                'h2h_team_b_win_pct': safe_divide(team_b_wins, total_games, 0.5),
                'h2h_competitiveness': safe_divide(close_games, total_games, 0.5),
                'h2h_avg_total_runs': safe_divide(total_runs, total_games, 9.0),
                'h2h_run_differential': safe_divide(team_a_runs - team_b_runs, total_games, 0.0),
                'h2h_games_played': total_games
            }
            
        except Exception as e:
            logger.error(f"Error getting H2H features for {team_a} vs {team_b}: {e}")
            # Return neutral values on error
            return {
                'h2h_team_a_win_pct': 0.5,
                'h2h_team_b_win_pct': 0.5,
                'h2h_competitiveness': 0.5,
                'h2h_avg_total_runs': 9.0,
                'h2h_run_differential': 0.0,
                'h2h_games_played': 0
            }
    
    def get_recent_form_features(self, team_id: str, as_of_date: date, games_back: int = 10) -> Dict[str, float]:
        """Get recent form features (second most important)"""
        try:
            form_query = text("""
                SELECT 
                    home_team_id,
                    away_team_id,
                    home_score,
                    away_score,
                    winner_team_id
                FROM games
                WHERE (home_team_id = :team_id OR away_team_id = :team_id)
                AND game_date < :as_of_date
                AND home_score IS NOT NULL 
                AND away_score IS NOT NULL
                ORDER BY game_date DESC
                LIMIT :games_back
            """)
            
            results = self.session.execute(form_query, {
                'team_id': team_id,
                'as_of_date': as_of_date,
                'games_back': games_back
            }).fetchall()
            
            if not results:
                # No recent games - return league averages
                return {
                    f'recent_win_pct_{games_back}': 0.5,
                    f'recent_runs_per_game_{games_back}': 4.5,
                    f'recent_run_differential_{games_back}': 0.0,
                    f'recent_form_momentum': 0.5
                }
            
            wins = 0
            runs_scored = 0
            runs_allowed = 0
            recent_results = []  # For momentum calculation
            
            for game in results:
                # Determine if team won and runs scored/allowed
                if game.home_team_id == team_id:
                    runs_scored += game.home_score
                    runs_allowed += game.away_score
                    won = (game.winner_team_id == team_id)
                else:
                    runs_scored += game.away_score
                    runs_allowed += game.home_score
                    won = (game.winner_team_id == team_id)
                
                if won:
                    wins += 1
                    recent_results.append(1)
                else:
                    recent_results.append(0)
            
            total_games = len(results)
            
            # Calculate momentum (weighted recent results, with latest games weighted more)
            momentum = 0.0
            if recent_results:
                weights = [1.0 + (i * 0.1) for i in range(len(recent_results))]  # Latest games get higher weight
                momentum = np.average(recent_results, weights=weights)
            
            return {
                f'recent_win_pct_{games_back}': safe_divide(wins, total_games, 0.5),
                f'recent_runs_per_game_{games_back}': safe_divide(runs_scored, total_games, 4.5),
                f'recent_run_differential_{games_back}': safe_divide(runs_scored - runs_allowed, total_games, 0.0),
                f'recent_form_momentum': momentum
            }
            
        except Exception as e:
            logger.error(f"Error getting recent form for {team_id}: {e}")
            return {
                f'recent_win_pct_{games_back}': 0.5,
                f'recent_runs_per_game_{games_back}': 4.5,
                f'recent_run_differential_{games_back}': 0.0,
                f'recent_form_momentum': 0.5
            }
    
    def create_betting_features(self, team_a: str, team_b: str, as_of_date: date = None) -> Dict[str, float]:
        """Create the optimized 21-feature set for betting predictions"""
        
        if as_of_date is None:
            as_of_date = date.today()
        
        logger.info(f"Creating optimized features for {team_a} vs {team_b}")
        
        # Get core feature sets
        h2h_features = self.get_head_to_head_features(team_a, team_b, as_of_date)
        team_a_form = self.get_recent_form_features(team_a, as_of_date, CONFIG['recent_form_games'])
        team_b_form = self.get_recent_form_features(team_b, as_of_date, CONFIG['recent_form_games'])
        
        # Build feature dictionary
        features = {}
        
        # 1. Head-to-Head Features (6 features - most important)
        features.update(h2h_features)
        
        # 2. Recent Form Features (8 features - second most important)
        features['team_a_recent_win_pct_10'] = team_a_form[f'recent_win_pct_{CONFIG["recent_form_games"]}']
        features['team_b_recent_win_pct_10'] = team_b_form[f'recent_win_pct_{CONFIG["recent_form_games"]}']
        features['team_a_recent_runs_per_game_10'] = team_a_form[f'recent_runs_per_game_{CONFIG["recent_form_games"]}']
        features['team_b_recent_runs_per_game_10'] = team_b_form[f'recent_runs_per_game_{CONFIG["recent_form_games"]}']
        features['team_a_recent_run_differential_10'] = team_a_form[f'recent_run_differential_{CONFIG["recent_form_games"]}']
        features['team_b_recent_run_differential_10'] = team_b_form[f'recent_run_differential_{CONFIG["recent_form_games"]}']
        features['recent_form_momentum_a'] = team_a_form['recent_form_momentum']
        features['recent_form_momentum_b'] = team_b_form['recent_form_momentum']
        
        # 3. Comparative Features (5 features - derived from the above)
        features['recent_runs_per_game_difference'] = features['team_a_recent_runs_per_game_10'] - features['team_b_recent_runs_per_game_10']
        features['recent_run_differential_difference'] = features['team_a_recent_run_differential_10'] - features['team_b_recent_run_differential_10'] 
        features['recent_win_pct_difference'] = features['team_a_recent_win_pct_10'] - features['team_b_recent_win_pct_10']
        features['head_to_head_advantage_a'] = features['h2h_team_a_win_pct'] - features['h2h_team_b_win_pct']
        
        # Form vs History consistency - does recent form match H2H history?
        features['form_vs_history_consistency'] = 1.0 - abs(features['recent_win_pct_difference'] - features['head_to_head_advantage_a'])
        
        # 4. Data Quality Features (2 features)
        features['data_completeness_score'] = min(1.0, (h2h_features['h2h_games_played'] + len([f for f in features.values() if f != 0])) / 25)
        features['matchup_sample_size'] = min(1.0, h2h_features['h2h_games_played'] / 10)  # Normalized sample size
        
        logger.info(f"Created {len(features)} optimized features for {team_a} vs {team_b}")
        return features

# =============================================================================
# OPTIMIZED MODEL TRAINER
# =============================================================================

class OptimizedMLTrainer:
    """Enhanced trainer using the new comprehensive feature engineering"""
    
    def __init__(self):
        if not FEATURE_ENGINEERING_AVAILABLE:
            raise RuntimeError("WorkingFeatureEngineer not available. Cannot initialize trainer.")
            
        self.feature_engineer = WorkingFeatureEngineer()
        self.session = get_session() if DATABASE_AVAILABLE else None
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []  # Will be set dynamically from actual features
        self.model_metadata = {}
        
        logger.info("🚀 OptimizedMLTrainer initialized with WorkingFeatureEngineer (57 features)")
        
    def collect_training_data(self, years: List[int]) -> pd.DataFrame:
        """Collect training data with quality filters. Uses cached feature engineering for speed."""
        import time
        logger.info(f"Collecting optimized training data for years: {years}")
        
        all_data = []
        overall_start = time.time()
        
        for year in years:
            year_start = time.time()
            logger.info(f"Processing {year} season data...")
            
            # Clear feature caches between years so stats come from correct season
            self.feature_engineer.clear_cache()
            
            # Get all completed games for the year — REGULAR SEASON ONLY (Apr-Oct)
            # Spring training (Feb-Mar) has different rosters, no strategy, and random outcomes
            games_query = text("""
                SELECT 
                    home_team_id, 
                    away_team_id, 
                    winner_team_id, 
                    game_date,
                    home_score,
                    away_score
                FROM games 
                WHERE EXTRACT(YEAR FROM game_date) = :year
                AND EXTRACT(MONTH FROM game_date) BETWEEN 4 AND 10
                AND home_score IS NOT NULL 
                AND away_score IS NOT NULL
                AND winner_team_id IS NOT NULL
                AND game_status = 'completed'
                ORDER BY game_date
            """)
            
            games = self.session.execute(games_query, {'year': year}).fetchall()
            
            logger.info(f"Found {len(games)} completed games in {year}")
            
            for i, game in enumerate(games):
                if i % 500 == 0 and i > 0:
                    elapsed = time.time() - year_start
                    rate = i / elapsed if elapsed > 0 else 0
                    remaining = (len(games) - i) / rate if rate > 0 else 0
                    logger.info(f"Processing game {i+1}/{len(games)} ({rate:.0f} games/sec, ~{remaining:.0f}s remaining for {year})")
                
                home_team = game.home_team_id
                away_team = game.away_team_id
                winner = game.winner_team_id
                game_date = game.game_date
                
                try:
                    # Create features using the new comprehensive feature engineering
                    features = self.feature_engineer.create_game_features(home_team, away_team, game_date)
                    
                    if not features or len(features) < 10:  # Basic data quality check
                        continue  # Skip games with insufficient data
                    
                    # Create training sample for this game
                    sample = features.copy()
                    sample['home_wins'] = 1 if winner == home_team else 0
                    sample['away_wins'] = 1 if winner == away_team else 0
                    sample['season'] = year
                    sample['game_date'] = game_date
                    sample['home_team'] = home_team
                    sample['away_team'] = away_team
                    all_data.append(sample)
                        
                except Exception as e:
                    logger.warning(f"Error processing game {away_team} @ {home_team}: {e}")
                    continue
            
            year_elapsed = time.time() - year_start
            logger.info(f"✅ {year} complete: {len(games)} games in {year_elapsed:.1f}s ({len(games)/year_elapsed:.0f} games/sec)")
        
        if not all_data:
            raise ValueError("No training data collected")
        
        total_elapsed = time.time() - overall_start
        df = pd.DataFrame(all_data)
        logger.info(f"Collected {len(df)} training samples with {len(df.columns)} features in {total_elapsed:.1f}s")
        
        return df
    
    def train_optimized_model(self, years: List[int], model_type: str = 'xgboost') -> Dict[str, Any]:
        """Train the optimized betting model"""
        logger.info(f"Training optimized betting model with {model_type}")
        
        try:
            # Collect training data
            df = self.collect_training_data(years)
            
            # Prepare features using the comprehensive feature set
            # Exclude metadata columns that aren't features
            exclude_cols = ['home_wins', 'away_wins', 'season', 'game_date', 'home_team', 'away_team']
            feature_cols = [col for col in df.columns if col not in exclude_cols]
            
            logger.info(f"🎯 Found {len(feature_cols)} features from WorkingFeatureEngineer")
            
            # Validate we have features
            if len(feature_cols) < 10:
                raise ValueError(f"Too few features ({len(feature_cols)}). Expected ~57 from WorkingFeatureEngineer")
            
            X = df[feature_cols].fillna(0.0)  # Fill missing with neutral values
            y = df['home_wins']  # Predict home team wins
            
            # Store actual feature names used
            self.feature_names = feature_cols
            
            logger.info(f"Training with {len(feature_cols)} comprehensive features on {len(X)} samples")
            
            # Split data temporally (important for betting models)
            # Use 80% for training, 20% for testing
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model with betting-optimized parameters + regularization
            # Key fixes: min_child_weight, gamma, reg_alpha prevent overfitting
            # scale_pos_weight corrects for away-team-wins class imbalance
            if model_type == 'xgboost':
                self.model = xgb.XGBClassifier(
                    n_estimators=200,       # Reduced from 300 for stability
                    max_depth=4,            # Reduced from 5 to prevent overfitting
                    learning_rate=0.05,
                    random_state=42,
                    eval_metric='logloss',
                    subsample=0.8,
                    colsample_bytree=0.7,   # Reduced from 0.8 for more feature diversity
                    min_child_weight=5,     # NEW: minimum 5 samples per leaf
                    gamma=0.1,              # NEW: minimum split gain required
                    reg_alpha=0.1,          # NEW: L1 regularization
                    reg_lambda=1.5,         # Increased L2 regularization
                    scale_pos_weight=1.24,  # NEW: correct for away-win class imbalance
                )
            else:
                self.model = RandomForestClassifier(
                    n_estimators=500,   # More trees for stability
                    max_depth=8,        # Controlled depth
                    random_state=42,
                    min_samples_split=10,  # Prevent overfitting
                    min_samples_leaf=5
                )
            
            logger.info("Training optimized model...")
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            train_pred = self.model.predict(X_train_scaled)
            test_pred = self.model.predict(X_test_scaled)
            train_proba = self.model.predict_proba(X_train_scaled)
            test_proba = self.model.predict_proba(X_test_scaled)
            
            train_accuracy = accuracy_score(y_train, train_pred)
            test_accuracy = accuracy_score(y_test, test_pred)
            train_logloss = log_loss(y_train, train_proba)
            test_logloss = log_loss(y_test, test_proba)
            
            # Cross validation for robust evaluation
            cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5, scoring='accuracy')
            
            # Calculate betting metrics
            # Confidence calibration - how well do probabilities match actual outcomes?
            test_proba_max = np.max(test_proba, axis=1)
            high_conf_mask = test_proba_max > CONFIG['confidence_threshold']
            high_conf_accuracy = accuracy_score(y_test[high_conf_mask], test_pred[high_conf_mask]) if np.any(high_conf_mask) else 0
            
            # Feature importance
            if hasattr(self.model, 'feature_importances_'):
                importance_df = pd.DataFrame({
                    'feature': feature_cols,
                    'importance': self.model.feature_importances_
                }).sort_values('importance', ascending=False)
                
                logger.info("Top 10 most important features:")
                for _, row in importance_df.head(10).iterrows():
                    logger.info(f"  {row['feature']}: {row['importance']:.4f}")
            
            # Store metadata (used by save_optimized_model for DB storage)
            self.model_metadata = {
                'model_type': model_type,
                'training_years': years,
                'feature_count': len(feature_cols),
                'sample_count': len(X),
                'feature_names': feature_cols,
                'training_date': datetime.now().isoformat(),
                'training_accuracy': float(train_accuracy),
                'test_accuracy': float(test_accuracy),
                'cv_accuracy': float(cv_scores.mean()),
            }
            
            result = {
                'success': True,
                'model_type': model_type,
                'training_accuracy': train_accuracy,
                'test_accuracy': test_accuracy,
                'train_logloss': train_logloss,
                'test_logloss': test_logloss,
                'cv_mean': cv_scores.mean(),
                'cv_std': cv_scores.std(),
                'high_confidence_accuracy': high_conf_accuracy,
                'high_confidence_sample_pct': np.mean(high_conf_mask) if len(test_proba_max) > 0 else 0,
                'feature_count': len(feature_cols),
                'sample_count': len(X),
                'training_years': years,
                'feature_names': feature_cols
            }
            
            logger.info(f"✅ Optimized model training completed!")
            logger.info(f"   Training accuracy: {train_accuracy:.3f}")
            logger.info(f"   Test accuracy: {test_accuracy:.3f}")
            logger.info(f"   CV accuracy: {cv_scores.mean():.3f} (±{cv_scores.std():.3f})")
            logger.info(f"   High confidence accuracy: {high_conf_accuracy:.3f}")
            logger.info(f"   Features: {len(feature_cols)} (optimized)")
            
            return result
            
        except Exception as e:
            logger.error(f"Optimized model training failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict_winner(self, home_team: str, away_team: str, game_date: date = None) -> Dict[str, Any]:
        """Predict winner between home and away teams using comprehensive features"""
        if self.model is None:
            return {'error': 'Model not trained'}
        
        try:
            if game_date is None:
                game_date = date.today()
            
            # Create comprehensive features using WorkingFeatureEngineer
            features = self.feature_engineer.create_game_features(home_team, away_team, game_date)
            
            if not features:
                return {'error': 'Could not create features'}
            
            # Check we have sufficient features
            if len(features) < 10:
                return {'error': 'Insufficient features for reliable prediction'}
            
            # Prepare feature vector in the same order as training
            feature_vector = []
            for feature_name in self.feature_names:
                feature_vector.append(features.get(feature_name, 0.0))
            
            # Scale and predict
            X = np.array([feature_vector])
            X_scaled = self.scaler.transform(X)
            
            prediction = self.model.predict(X_scaled)[0]
            probability = self.model.predict_proba(X_scaled)[0]
            
            team_a_prob = probability[1]  # Probability team A wins
            team_b_prob = probability[0]  # Probability team B wins
            confidence = max(team_a_prob, team_b_prob)
            
            # Confidence tier (for display — NOT betting optimization)
            if confidence > 0.70:
                confidence_tier = 'HIGH'
            elif confidence > 0.60:
                confidence_tier = 'MEDIUM'
            else:
                confidence_tier = 'LOW'
            
            # Keep betting_recommendation for backward compatibility with DB/downstream code
            betting_edge = 'STRONG' if confidence > 0.75 else 'MODERATE' if confidence > 0.65 else 'WEAK' if confidence > 0.55 else 'AVOID'
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'predicted_winner': home_team if prediction == 1 else away_team,
                'home_win_probability': team_a_prob,
                'away_win_probability': team_b_prob,
                'confidence': confidence,
                'confidence_tier': confidence_tier,
                'betting_recommendation': betting_edge,
                'h2h_sample_size': features.get('h2h_total_games', 0),
                'features_used': len([f for f in feature_vector if f != 0]),
                'model_version': 'enhanced_working_v4.0'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def save_optimized_model(self, model_name: str) -> bool:
        """Save the optimized model to the database (trained_models table)"""
        try:
            if not DATABASE_AVAILABLE:
                logger.error("Database not available — cannot save model")
                return False
            
            # Serialize model + scaler together
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
            }
            model_binary = pickle.dumps(model_data)
            
            db_config = DatabaseConfig()
            engine = db_config.create_engine()
            
            with engine.connect() as conn:
                # Deactivate any previously active model with this name
                conn.execute(text("""
                    UPDATE trained_models SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE model_name = :model_name AND is_active = TRUE
                """), {'model_name': model_name})
                
                # Insert the new active model
                conn.execute(text("""
                    INSERT INTO trained_models 
                    (model_name, model_version, model_type, model_binary, feature_names,
                     metadata, training_accuracy, test_accuracy, cv_accuracy,
                     feature_count, sample_count, training_years, is_active)
                    VALUES 
                    (:model_name, :model_version, :model_type, :model_binary, :feature_names,
                     :metadata, :training_accuracy, :test_accuracy, :cv_accuracy,
                     :feature_count, :sample_count, :training_years, TRUE)
                """), {
                    'model_name': model_name,
                    'model_version': self.model_metadata.get('model_type', 'xgboost') + '_v4.0',
                    'model_type': self.model_metadata.get('model_type', 'xgboost'),
                    'model_binary': model_binary,
                    'feature_names': json.dumps(self.feature_names),
                    'metadata': json.dumps(self.model_metadata),
                    'training_accuracy': self.model_metadata.get('training_accuracy'),
                    'test_accuracy': self.model_metadata.get('test_accuracy'),
                    'cv_accuracy': self.model_metadata.get('cv_accuracy'),
                    'feature_count': len(self.feature_names),
                    'sample_count': self.model_metadata.get('sample_count'),
                    'training_years': json.dumps(self.model_metadata.get('training_years', [])),
                })
                conn.commit()
            
            logger.info(f"✅ Model saved to database: {model_name} ({len(self.feature_names)} features)")
            return True
            
        except Exception as e:
            logger.error(f"Error saving model to database: {e}")
            return False
    
    def load_optimized_model(self, model_name: str = 'betting_winner_predictor') -> bool:
        """Load the active model from the database (trained_models table)"""
        try:
            if not DATABASE_AVAILABLE:
                logger.error("Database not available — cannot load model")
                return False
            
            db_config = DatabaseConfig()
            engine = db_config.create_engine()
            
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT model_binary, feature_names, metadata, model_version
                    FROM trained_models
                    WHERE model_name = :model_name AND is_active = TRUE
                    ORDER BY created_at DESC LIMIT 1
                """), {'model_name': model_name}).fetchone()
            
            if not result:
                logger.error(f"No active model found in database for: {model_name}")
                return False
            
            model_binary, feature_names_json, metadata_json, model_version = result
            
            # Deserialize
            model_data = pickle.loads(model_binary)
            self.model = model_data.get('model')
            self.scaler = model_data.get('scaler')
            self.feature_names = json.loads(feature_names_json) if isinstance(feature_names_json, str) else feature_names_json
            self.model_metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else (metadata_json or {})
            
            if self.model is None:
                logger.error("Model binary was empty/corrupt")
                return False
            
            logger.info(f"✅ Model loaded from database: {model_name} (version: {model_version}, {len(self.feature_names)} features)")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model from database: {e}")
            return False
    
    def save_prediction_to_db(self, team_a: str, team_b: str, prediction: dict, game_date: str = None) -> bool:
        """Save prediction to database with optimized format"""
        try:
            if not DATABASE_AVAILABLE:
                logger.error("Database not available")
                return False
            
            from datetime import datetime, date
            
            # Get database connection
            db_config = DatabaseConfig()
            engine = db_config.create_engine()
            
            prediction_date = game_date if game_date else date.today()
            
            # Dynamically determine model version based on actual feature count
            feature_count = len(self.feature_names) if hasattr(self, 'feature_names') and self.feature_names else 701
            model_version = f"optimized_betting_v3.0_{feature_count}_features"
            
            predicted_winner = prediction.get('predicted_winner', '')
            confidence_score = float(prediction.get('confidence', 0.0))
            confidence_tier = prediction.get('confidence_tier', 'MEDIUM')
            
            with engine.connect() as conn:
                # Try to find game_pk
                game_pk_query = text("""
                    SELECT game_pk FROM games 
                    WHERE game_date = :game_date 
                    AND ((home_team_id = :team_a AND away_team_id = :team_b)
                         OR (home_team_id = :team_b AND away_team_id = :team_a))
                    LIMIT 1
                """)
                
                result = conn.execute(game_pk_query, {
                    'game_date': prediction_date,
                    'team_a': team_a,
                    'team_b': team_b
                })
                
                game_pk_row = result.fetchone()
                game_pk = game_pk_row[0] if game_pk_row else None
                
                if game_pk is None:
                    # Generate unique game_pk for tracking
                    game_pk = int(f"8888{ord(team_a[0])}{ord(team_b[0])}{prediction_date.day}")
                
                # Insert optimized prediction
                insert_query = text("""
                    INSERT INTO game_predictions (
                        game_pk,
                        prediction_date,
                        model_version,
                        predicted_winner,
                        win_probability,
                        confidence_score,
                        primary_factors,
                        created_at,
                        updated_at
                    ) VALUES (
                        :game_pk,
                        :prediction_date,
                        :model_version,
                        :predicted_winner,
                        :win_probability,
                        :confidence_score,
                        :primary_factors,
                        :created_at,
                        :updated_at
                    )
                """)
                
                factors = f"{len(self.feature_names)} features: H2H history ({prediction.get('h2h_sample_size', 0)} games), recent form, confidence: {confidence_tier}"
                
                conn.execute(insert_query, {
                    'game_pk': game_pk,
                    'prediction_date': prediction_date,
                    'model_version': model_version,
                    'predicted_winner': predicted_winner,
                    'win_probability': confidence_score,
                    'confidence_score': confidence_score,
                    'primary_factors': factors,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                })
                
                conn.commit()
                
            logger.info(f"✅ Prediction saved: {team_a} vs {team_b} → {predicted_winner} ({confidence_score:.1%}, {confidence_tier})")
            return True
            
        except Exception as e:
            logger.error(f"Error saving optimized prediction: {e}")
            return False

# =============================================================================
# MAIN EXECUTION AND TESTING
# =============================================================================

def main():
    """Test the optimized prediction model"""
    print("🎯 Optimized MLB Prediction Model Trainer")
    print("=" * 60)
    
    if not all([DATABASE_AVAILABLE, ML_AVAILABLE]):
        print("❌ Missing required dependencies")
        return
    
    trainer = OptimizedMLTrainer()
    
    # Train optimized model
    print("🚀 Training optimized prediction model...")
    result = trainer.train_optimized_model(CONFIG['training_years'], 'xgboost')
    
    if result.get('success'):
        print(f"✅ Training successful!")
        print(f"   Test accuracy: {result.get('test_accuracy', 0):.3f}")
        print(f"   High confidence accuracy: {result.get('high_confidence_accuracy', 0):.3f}")
        print(f"   Features: {result.get('feature_count', 0)}")
        print(f"   CV accuracy: {result.get('cv_mean', 0):.3f} ± {result.get('cv_std', 0):.3f}")
        
        # Save model to database
        saved = trainer.save_optimized_model('betting_winner_predictor')
        print(f"   Model saved to database: {saved}")
        
        # Test prediction
        print(f"\n🎯 Testing prediction...")
        pred = trainer.predict_winner('LAD', 'NYY')
        if 'error' not in pred:
            print(f"   LAD vs NYY: {pred['predicted_winner']} ({pred['confidence']:.1%})")
            print(f"   Confidence tier: {pred['confidence_tier']}")
            print(f"   Features used: {pred.get('features_used', 'N/A')}")
            print(f"   H2H sample size: {pred.get('h2h_sample_size', 'N/A')}")
        
        # Test loading from database
        print(f"\n🔄 Testing model load from database...")
        trainer2 = OptimizedMLTrainer()
        if trainer2.load_optimized_model('betting_winner_predictor'):
            pred2 = trainer2.predict_winner('LAD', 'NYY')
            if 'error' not in pred2:
                print(f"   Loaded model prediction: {pred2['predicted_winner']} ({pred2['confidence']:.1%})")
                print(f"   ✅ DB save/load round-trip verified!")
            else:
                print(f"   ❌ Loaded model prediction failed: {pred2['error']}")
        else:
            print(f"   ❌ Could not load model from database")
        
    else:
        print(f"❌ Training failed: {result.get('error')}")
    
    print(f"\n✅ Model testing completed!")

if __name__ == "__main__":
    main()
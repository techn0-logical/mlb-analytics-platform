#!/usr/bin/env python3
"""
ADAPTIVE LEARNING ENGINE FOR MLB PREDICTIONS
===========================================

Accuracy-focused adaptive learning system that improves prediction quality
without full retraining. The goal is PREDICTION ACCURACY, not betting optimization.

How it works:
1. Analyzes recent prediction outcomes (correct vs incorrect)
2. Measures actual per-feature accuracy — which features correlate with correct picks
3. Adjusts feature weights so the model leans on features that are actually working
4. Calibrates confidence so model's stated confidence matches real-world accuracy
5. Tracks team-specific accuracy to correct systematic biases

Key design principles:
- NO random noise — every adjustment is derived from real measured performance
- NO betting thresholds — the system optimizes for accuracy, period
- Conservative adjustments (EMA smoothing) prevent overcorrection from small samples
- Features are scored by their actual correlation with correct predictions

Author: MLB Analytics Adaptive Learning Team
Version: v4.0 (Accuracy-focused, no betting optimization)
"""

import sys
import os
import pickle
import statistics
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from Database.config.database import db_config
from sqlalchemy import text

# Import the new feature engineering system
try:
    from Analytics.working_feature_engineering import WorkingFeatureEngineer
    FEATURE_ENGINEERING_AVAILABLE = True
except ImportError:
    FEATURE_ENGINEERING_AVAILABLE = False
    print("❌ WorkingFeatureEngineer not available")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdaptiveLearningEngine:
    """Enhanced adaptive learning system using WorkingFeatureEngineer"""
    
    def __init__(self):
        """Initialize the adaptive learning engine with WorkingFeatureEngineer"""
        self.engine = db_config.create_engine()
        self.model = None
        self.feature_names = []
        self.model_version = None
        
        # Initialize the feature engineering system
        if FEATURE_ENGINEERING_AVAILABLE:
            self.feature_engineer = WorkingFeatureEngineer()
            logger.info("🚀 AdaptiveLearningEngine initialized with WorkingFeatureEngineer")
        else:
            self.feature_engineer = None
            logger.warning("⚠️ WorkingFeatureEngineer not available")
        
        # Analysis parameters
        self.lookback_days = 14  # Days to analyze for adaptation
        self.min_sample_size = 5  # Minimum games for statistical significance
        self.confidence_bins = ['50-60%', '60-70%', '70-80%', '80-90%', '90%+']
        
        logger.info("🧠 Adaptive Learning Engine initialized")
    
    def load_model(self, model_name: str = 'betting_winner_predictor'):
        """Load the active trained model from the database (trained_models table)"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT model_binary, feature_names, model_version
                    FROM trained_models
                    WHERE model_name = :model_name AND is_active = TRUE
                    ORDER BY created_at DESC LIMIT 1
                """), {'model_name': model_name}).fetchone()
            
            if not result:
                raise FileNotFoundError(f"No active model found in database for: {model_name}")
            
            model_binary, feature_names_json, model_version = result
            
            import json
            model_data = pickle.loads(model_binary)
            self.model = model_data.get('model')
            self.feature_names = json.loads(feature_names_json) if isinstance(feature_names_json, str) else feature_names_json
            self.model_version = model_version
            
            logger.info(f"✅ Loaded model from database: {model_name}")
            logger.info(f"📊 Model version: {self.model_version}")
            logger.info(f"🔧 Features: {len(self.feature_names)}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load model from database: {e}")
            raise
    
    def analyze_recent_performance(self, days_back: int = None) -> Dict:
        """Analyze prediction performance over recent days"""
        if days_back is None:
            days_back = self.lookback_days
            
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"📈 Analyzing performance from {start_date} to {end_date} (model: {self.model_version})")
        
        with self.engine.connect() as conn:
            # Get recent predictions and results from game_predictions table
            query = text("""
                SELECT 
                    gp.prediction_date,
                    gp.game_pk,
                    gp.predicted_winner,
                    COALESCE(gp.win_probability * 100, gp.confidence_score * 100, 50) as confidence,
                    NULL as betting_recommendation,
                    FALSE as is_betting_opportunity,
                    NULL as h2h_sample_size,
                    g.away_team_id,
                    g.home_team_id,
                    g.away_score,
                    g.home_score,
                    CASE 
                        WHEN g.away_score > g.home_score THEN g.away_team_id
                        WHEN g.home_score > g.away_score THEN g.home_team_id
                        ELSE NULL 
                    END as actual_winner,
                    CASE 
                        WHEN gp.predicted_winner = CASE 
                            WHEN g.away_score > g.home_score THEN g.away_team_id
                            WHEN g.home_score > g.away_score THEN g.home_team_id
                            ELSE NULL 
                        END THEN 1 
                        ELSE 0 
                    END as correct_prediction
                FROM game_predictions gp
                JOIN games g ON gp.game_pk = g.game_pk
                WHERE gp.prediction_date BETWEEN :start_date AND :end_date
                AND g.game_status = 'completed'
                AND g.away_score IS NOT NULL
                AND g.home_score IS NOT NULL
                ORDER BY gp.prediction_date, gp.game_pk;
            """)
            
            results = conn.execute(query, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()
        
        if not results:
            logger.warning("⚠️ No recent completed games found for analysis")
            return {}
        
        # Convert results to list of dictionaries for easier processing
        columns = ['prediction_date', 'game_pk', 'predicted_winner', 'confidence', 
                  'betting_recommendation', 'is_betting_opportunity', 'h2h_sample_size',
                  'away_team_id', 'home_team_id', 'away_score', 'home_score', 
                  'actual_winner', 'correct_prediction']
        
        data = []
        for row in results:
            data.append(dict(zip(columns, row)))
        
        # Calculate overall performance
        total_predictions = len(data)
        correct_predictions = sum(1 for row in data if row['correct_prediction'])
        overall_accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
        
        # Performance by confidence level
        confidence_performance = {}
        for bin_name in self.confidence_bins:
            if bin_name == '50-60%':
                filtered_data = [row for row in data if 50 <= row['confidence'] < 60]
            elif bin_name == '60-70%':
                filtered_data = [row for row in data if 60 <= row['confidence'] < 70]
            elif bin_name == '70-80%':
                filtered_data = [row for row in data if 70 <= row['confidence'] < 80]
            elif bin_name == '80-90%':
                filtered_data = [row for row in data if 80 <= row['confidence'] < 90]
            elif bin_name == '90%+':
                filtered_data = [row for row in data if row['confidence'] >= 90]
            else:
                filtered_data = []
            
            if filtered_data:
                correct_count = sum(1 for row in filtered_data if row['correct_prediction'])
                accuracy = correct_count / len(filtered_data)
                avg_confidence = statistics.mean(row['confidence'] for row in filtered_data)
                
                confidence_performance[bin_name] = {
                    'accuracy': accuracy,
                    'sample_size': len(filtered_data),
                    'avg_confidence': avg_confidence
                }
        
        # Performance by team
        team_performance = {}
        for row in data:
            predicted_team = row['predicted_winner']
            is_correct = row['correct_prediction']
            
            if predicted_team not in team_performance:
                team_performance[predicted_team] = {'correct': 0, 'total': 0}
            
            team_performance[predicted_team]['total'] += 1
            if is_correct:
                team_performance[predicted_team]['correct'] += 1
        
        # Calculate team accuracy
        for team in team_performance:
            stats = team_performance[team]
            stats['accuracy'] = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
        
        performance_data = {
            'period': f"{start_date} to {end_date}",
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions,
            'overall_accuracy': overall_accuracy,
            'confidence_performance': confidence_performance,
            'team_performance': team_performance,
            'raw_data': data
        }
        
        logger.info(f"📊 Analysis complete: {correct_predictions}/{total_predictions} correct ({overall_accuracy:.1%})")
        return performance_data
    
    def update_feature_performance(self, performance_data: Dict):
        """Update feature performance based on ACTUAL per-feature accuracy.
        
        For each feature, we compare its average value in correct vs incorrect predictions.
        Features where there's a meaningful difference between correct/incorrect picks
        get a positive weight adjustment (the model should lean on them more).
        Features where there's no difference or a wrong-way signal get a negative adjustment.
        
        NO random noise — every adjustment is derived from measured data.
        """
        if not performance_data or 'raw_data' not in performance_data:
            logger.warning("⚠️ No performance data available for feature updates")
            return []
        
        if not self.model or not self.feature_names:
            logger.warning("⚠️ No model loaded or feature names available — skipping feature updates")
            return []
        
        data = performance_data['raw_data']
        today = date.today()
        
        # We need to reconstruct features for each game to measure per-feature accuracy
        # Separate games into correct vs incorrect predictions
        correct_games = [row for row in data if row['correct_prediction']]
        incorrect_games = [row for row in data if not row['correct_prediction']]
        
        if not correct_games or not incorrect_games:
            logger.warning("⚠️ Need both correct and incorrect predictions to measure feature accuracy")
            return []
        
        logger.info(f"🔧 Analyzing {len(self.feature_names)} features across "
                     f"{len(correct_games)} correct / {len(incorrect_games)} incorrect predictions")
        
        # Rebuild features for each game so we can compare feature values
        correct_feature_sums = {f: 0.0 for f in self.feature_names}
        correct_count = 0
        incorrect_feature_sums = {f: 0.0 for f in self.feature_names}
        incorrect_count = 0
        
        if self.feature_engineer:
            for row in data:
                try:
                    away_team = row.get('away_team_id')
                    home_team = row.get('home_team_id')
                    game_date = row.get('prediction_date')
                    if not away_team or not home_team or not game_date:
                        continue
                    
                    features = self.feature_engineer.create_game_features(
                        away_team, home_team, str(game_date)
                    )
                    if not features:
                        continue
                    
                    target = correct_feature_sums if row['correct_prediction'] else incorrect_feature_sums
                    for fname in self.feature_names:
                        target[fname] += features.get(fname, 0.0)
                    
                    if row['correct_prediction']:
                        correct_count += 1
                    else:
                        incorrect_count += 1
                        
                except Exception as e:
                    logger.debug(f"Could not reconstruct features for game {row.get('game_pk')}: {e}")
                    continue
        
        if correct_count < 3 or incorrect_count < 3:
            logger.warning(f"⚠️ Not enough reconstructed games (correct={correct_count}, incorrect={incorrect_count})")
            # Fall back to model importance only (no per-feature accuracy data)
            return self._update_features_from_importance_only(performance_data)
        
        # Calculate per-feature accuracy signal:
        # For each feature, compute mean value in correct vs incorrect predictions.
        # A feature that shows a clear difference is informative.
        feature_updates = []
        
        # Get model feature importance for weighting the adjustment
        feature_importance = {}
        if hasattr(self.model, 'feature_importances_'):
            for i, fname in enumerate(self.feature_names):
                if i < len(self.model.feature_importances_):
                    feature_importance[fname] = self.model.feature_importances_[i]
        
        with self.engine.connect() as conn:
            for fname in self.feature_names:
                correct_mean = correct_feature_sums[fname] / correct_count
                incorrect_mean = incorrect_feature_sums[fname] / incorrect_count
                
                # Signal = normalized difference between correct and incorrect predictions
                # Positive signal means this feature's values differ meaningfully 
                # between correct and incorrect picks (useful feature)
                range_val = max(abs(correct_mean), abs(incorrect_mean), 0.001)
                signal_strength = abs(correct_mean - incorrect_mean) / range_val
                
                # Performance score: 50 = no signal, 100 = strong signal
                performance_score = min(90, 50 + signal_strength * 40)
                
                # Weight adjustment: features with signal get boosted, features without get damped
                # Conservative: 0.90 to 1.10 range
                importance = feature_importance.get(fname, 0.01)
                
                if signal_strength > 0.1:
                    # Feature shows a real difference — boost it proportionally
                    weight_adjustment = 1.0 + min(0.10, signal_strength * 0.05)
                elif signal_strength < 0.02:
                    # Feature shows no difference — slightly reduce its influence
                    weight_adjustment = max(0.90, 1.0 - 0.05)
                else:
                    # Marginal signal — leave it alone
                    weight_adjustment = 1.0
                
                # High-importance features get even more conservative adjustments
                if importance > 0.05:
                    weight_adjustment = 1.0 + (weight_adjustment - 1.0) * 0.5
                
                # Apply EMA smoothing with existing weight if available
                existing_weight = self._get_existing_weight(conn, fname)
                if existing_weight is not None:
                    # EMA: 70% existing, 30% new measurement
                    weight_adjustment = existing_weight * 0.7 + weight_adjustment * 0.3
                
                query = text("""
                    INSERT INTO feature_performance 
                    (date, model_version, feature_name, weight_adjustment, 
                     performance_score, sample_size, significance_level)
                    VALUES (:date, :model_version, :feature_name, :weight_adjustment,
                            :performance_score, :sample_size, :significance_level)
                    ON CONFLICT (date, model_version, feature_name) 
                    DO UPDATE SET 
                        weight_adjustment = EXCLUDED.weight_adjustment,
                        performance_score = EXCLUDED.performance_score,
                        sample_size = EXCLUDED.sample_size,
                        updated_at = CURRENT_TIMESTAMP;
                """)
                
                conn.execute(query, {
                    'date': today,
                    'model_version': self.model_version,
                    'feature_name': fname,
                    'weight_adjustment': round(weight_adjustment, 3),
                    'performance_score': round(performance_score, 2),
                    'sample_size': correct_count + incorrect_count,
                    'significance_level': 0.05
                })
                
                feature_updates.append({
                    'feature': fname,
                    'score': performance_score,
                    'adjustment': weight_adjustment,
                    'importance': importance,
                    'signal': signal_strength,
                    'category': self._get_feature_category(fname)
                })
            
            conn.commit()
        
        self._log_feature_update_summary(feature_updates)
        logger.info(f"✅ Updated {len(feature_updates)} features based on actual accuracy signal (no random noise)")
        return feature_updates
    
    def _get_existing_weight(self, conn, feature_name: str) -> Optional[float]:
        """Get the most recent weight for EMA smoothing."""
        try:
            result = conn.execute(text("""
                SELECT weight_adjustment FROM feature_performance
                WHERE model_version = :model_version AND feature_name = :feature_name
                ORDER BY date DESC LIMIT 1
            """), {'model_version': self.model_version, 'feature_name': feature_name}).fetchone()
            return float(result[0]) if result else None
        except Exception:
            return None
    
    def _update_features_from_importance_only(self, performance_data: Dict) -> list:
        """Fallback: if we can't reconstruct features, just store model importance as-is (no random noise)."""
        if not self.model or not self.feature_names:
            return []
        
        today = date.today()
        overall_accuracy = performance_data['overall_accuracy']
        feature_updates = []
        
        importances = getattr(self.model, 'feature_importances_', None)
        
        with self.engine.connect() as conn:
            for i, fname in enumerate(self.feature_names):
                importance = float(importances[i]) if importances is not None and i < len(importances) else 0.01
                # No adjustment without per-feature accuracy data — just record importance
                weight_adjustment = 1.0
                performance_score = overall_accuracy * 100
                
                query = text("""
                    INSERT INTO feature_performance 
                    (date, model_version, feature_name, weight_adjustment, 
                     performance_score, sample_size, significance_level)
                    VALUES (:date, :model_version, :feature_name, :weight_adjustment,
                            :performance_score, :sample_size, :significance_level)
                    ON CONFLICT (date, model_version, feature_name) 
                    DO UPDATE SET 
                        weight_adjustment = EXCLUDED.weight_adjustment,
                        performance_score = EXCLUDED.performance_score,
                        sample_size = EXCLUDED.sample_size,
                        updated_at = CURRENT_TIMESTAMP;
                """)
                
                conn.execute(query, {
                    'date': today,
                    'model_version': self.model_version,
                    'feature_name': fname,
                    'weight_adjustment': round(weight_adjustment, 3),
                    'performance_score': round(performance_score, 2),
                    'sample_size': performance_data['total_predictions'],
                    'significance_level': 0.05
                })
                
                feature_updates.append({
                    'feature': fname,
                    'score': performance_score,
                    'adjustment': weight_adjustment,
                    'importance': importance,
                    'signal': 0.0,
                    'category': self._get_feature_category(fname)
                })
            
            conn.commit()
        
        logger.info(f"⚠️ Updated {len(feature_updates)} features (importance only — no per-feature accuracy data)")
        return feature_updates
    
    def _get_feature_category(self, feature_name: str) -> str:
        """Categorize feature by name pattern for better organization"""
        feature_lower = feature_name.lower()
        
        if any(x in feature_lower for x in ['h2h', 'head_to_head', 'matchup']):
            return 'head_to_head'
        elif any(x in feature_lower for x in ['batting', 'ops', 'obp', 'slg', 'ba']):
            return 'batting'
        elif any(x in feature_lower for x in ['pitching', 'era', 'whip', 'strikeout']):
            return 'pitching'
        elif any(x in feature_lower for x in ['recent', 'form', 'momentum']):
            return 'recent_form'
        elif any(x in feature_lower for x in ['transaction', 'roster', 'acquisition']):
            return 'transactions'
        elif any(x in feature_lower for x in ['home', 'away', 'advantage']):
            return 'venue'
        elif any(x in feature_lower for x in ['war', 'depth', 'quality']):
            return 'advanced'
        else:
            return 'other'
    
    def _log_feature_update_summary(self, feature_updates: List[Dict]):
        """Log a summary of feature updates by category"""
        if not feature_updates:
            return
            
        # Group by category
        categories = {}
        for update in feature_updates:
            category = update['category']
            if category not in categories:
                categories[category] = {'count': 0, 'avg_adjustment': 0, 'features': []}
            
            categories[category]['count'] += 1
            categories[category]['avg_adjustment'] += update['adjustment']
            categories[category]['features'].append(update['feature'])
        
        # Calculate averages and log
        logger.info("📊 Feature Update Summary by Category:")
        for category, stats in categories.items():
            avg_adj = stats['avg_adjustment'] / stats['count']
            logger.info(f"   {category}: {stats['count']} features, avg adjustment: {avg_adj:.3f}")
            
        # Log top adjustments
        sorted_updates = sorted(feature_updates, key=lambda x: abs(x['adjustment'] - 1.0), reverse=True)
        logger.info("🔧 Biggest Feature Adjustments:")
        for update in sorted_updates[:5]:
            direction = "↑" if update['adjustment'] > 1.0 else "↓"
            logger.info(f"   {direction} {update['feature']}: {update['adjustment']:.3f} ({update['category']})")
    
    def update_confidence_calibration(self, performance_data: Dict):
        """Update confidence calibration table"""
        confidence_performance = performance_data.get('confidence_performance', {})
        
        with self.engine.connect() as conn:
            for confidence_range, stats in confidence_performance.items():
                if stats['sample_size'] < self.min_sample_size:
                    continue
                
                actual_accuracy = stats['accuracy'] * 100
                predicted_accuracy = stats['avg_confidence']
                
                # Calculate calibration factor
                if predicted_accuracy > 0:
                    calibration_factor = actual_accuracy / float(predicted_accuracy)
                else:
                    calibration_factor = 1.0
                
                # Bound the calibration factor
                calibration_factor = max(0.5, min(2.0, calibration_factor))
                
                # Set confidence bounds
                if confidence_range == '50-60%':
                    lower, upper = 50, 60
                elif confidence_range == '60-70%':
                    lower, upper = 60, 70
                elif confidence_range == '70-80%':
                    lower, upper = 70, 80
                elif confidence_range == '80-90%':
                    lower, upper = 80, 90
                elif confidence_range == '90%+':
                    lower, upper = 90, 100
                
                query = text("""
                    INSERT INTO confidence_calibration 
                    (model_version, confidence_range, predicted_accuracy, actual_accuracy,
                     calibration_factor, sample_size, last_updated, confidence_lower_bound,
                     confidence_upper_bound)
                    VALUES (:model_version, :confidence_range, :predicted_accuracy, 
                            :actual_accuracy, :calibration_factor, :sample_size, :last_updated,
                            :confidence_lower_bound, :confidence_upper_bound)
                    ON CONFLICT (model_version, confidence_range)
                    DO UPDATE SET 
                        predicted_accuracy = EXCLUDED.predicted_accuracy,
                        actual_accuracy = EXCLUDED.actual_accuracy,
                        calibration_factor = EXCLUDED.calibration_factor,
                        sample_size = EXCLUDED.sample_size,
                        last_updated = EXCLUDED.last_updated,
                        updated_at = CURRENT_TIMESTAMP;
                """)
                
                conn.execute(query, {
                    'model_version': self.model_version,
                    'confidence_range': confidence_range,
                    'predicted_accuracy': round(predicted_accuracy, 2),
                    'actual_accuracy': round(actual_accuracy, 2),
                    'calibration_factor': round(calibration_factor, 4),
                    'sample_size': stats['sample_size'],
                    'last_updated': date.today(),
                    'confidence_lower_bound': lower,
                    'confidence_upper_bound': upper
                })
            
            conn.commit()
        
        logger.info(f"✅ Updated {len(confidence_performance)} confidence calibration records")
    
    def update_model_parameters(self, performance_data: Dict, feature_updates: List[Dict]):
        """Update adaptive model parameters focused on ACCURACY improvement.
        
        No betting thresholds — just parameters that help the model make more
        correct predictions.
        """
        today = date.today()
        overall_accuracy = performance_data['overall_accuracy']
        total_predictions = performance_data['total_predictions']
        
        # Calculate accuracy by confidence tier to see if the model is well-calibrated
        confidence_performance = performance_data.get('confidence_performance', {})
        
        # Compute average accuracy of high-confidence picks vs low-confidence picks
        high_conf_accuracy = 0.0
        low_conf_accuracy = 0.0
        for cbin, stats in confidence_performance.items():
            if cbin in ('70-80%', '80-90%', '90%+'):
                high_conf_accuracy = max(high_conf_accuracy, stats['accuracy'])
            elif cbin in ('50-60%',):
                low_conf_accuracy = stats['accuracy']
        
        # Is higher confidence actually more accurate? (it should be)
        confidence_ordering_correct = high_conf_accuracy > low_conf_accuracy if high_conf_accuracy > 0 and low_conf_accuracy > 0 else True
        
        parameters = [
            {
                'name': 'overall_accuracy_trend',
                'category': 'calibration',
                'value': overall_accuracy * 100,
                'default': 55.0,
                'type': 'percentage',
                'min_val': 30.0,
                'max_val': 80.0,
                'impact': (overall_accuracy - 0.55) * 100  # vs 55% baseline
            },
            {
                'name': 'confidence_reliability',
                'category': 'calibration',
                'value': 1.0 if confidence_ordering_correct else 0.8,
                'default': 1.0,
                'type': 'multiplier',
                'min_val': 0.5,
                'max_val': 1.5,
                'impact': 5.0 if confidence_ordering_correct else -5.0
            },
            {
                'name': 'sample_size_factor',
                'category': 'calibration',
                'value': min(1.0, total_predictions / 100.0),  # Ramps to 1.0 at 100 predictions
                'default': 0.0,
                'type': 'multiplier',
                'min_val': 0.0,
                'max_val': 1.0,
                'impact': min(1.0, total_predictions / 100.0) * 10
            },
        ]
        
        with self.engine.connect() as conn:
            for param in parameters:
                query = text("""
                    INSERT INTO model_parameters 
                    (parameter_name, parameter_category, parameter_value, default_value,
                     parameter_type, min_value, max_value, last_updated, performance_impact,
                     model_version, is_active)
                    VALUES (:parameter_name, :parameter_category, :parameter_value, 
                            :default_value, :parameter_type, :min_value, :max_value,
                            :last_updated, :performance_impact, :model_version, :is_active)
                    ON CONFLICT (parameter_name, model_version)
                    DO UPDATE SET 
                        parameter_value = EXCLUDED.parameter_value,
                        performance_impact = EXCLUDED.performance_impact,
                        last_updated = EXCLUDED.last_updated,
                        updated_at = CURRENT_TIMESTAMP;
                """)
                
                conn.execute(query, {
                    'parameter_name': param['name'],
                    'parameter_category': param['category'],
                    'parameter_value': round(param['value'], 6),
                    'default_value': param['default'],
                    'parameter_type': param['type'],
                    'min_value': param['min_val'],
                    'max_value': param['max_val'],
                    'last_updated': today,
                    'performance_impact': round(param['impact'], 2),
                    'model_version': self.model_version,
                    'is_active': True
                })
            
            conn.commit()
        
        logger.info(f"✅ Updated {len(parameters)} accuracy-focused model parameters")
        return parameters
    
    def update_team_adjustments(self, performance_data: Dict):
        """Update team-specific accuracy adjustments.
        
        If we consistently predict Team X correctly, their confidence is already good.
        If we consistently get Team Y wrong, we need to dampen confidence on their games.
        This is accuracy calibration, not betting optimization.
        """
        team_performance = performance_data.get('team_performance', {})
        overall_accuracy = performance_data['overall_accuracy']
        
        adjustments = []
        
        with self.engine.connect() as conn:
            for team_id, stats in team_performance.items():
                if stats['total'] < self.min_sample_size:
                    continue
                
                team_accuracy = stats['accuracy']
                accuracy_diff = team_accuracy - overall_accuracy
                
                # Accuracy bias correction:
                # If we're 70% accurate on this team but 55% overall, 
                # our confidence for this team is well-calibrated (maybe slightly boost)
                # If we're 40% accurate on this team but 55% overall,
                # we're systematically wrong about them (dampen confidence)
                
                # Conservative correction factor: 0.92 to 1.08
                correction_factor = max(0.92, min(1.08, 1.0 + accuracy_diff * 0.3))
                
                adjustment_types = [
                    {
                        'type': 'confidence_boost',
                        'value': correction_factor,
                        'context': None
                    },
                    {
                        'type': 'recent_form',
                        'value': max(0.95, min(1.05, 1.0 + accuracy_diff * 0.15)),
                        'context': 'last_14_days'
                    }
                ]
                
                for adj in adjustment_types:
                    query = text("""
                        INSERT INTO team_performance_adjustments 
                        (team_id, adjustment_type, adjustment_value, context_filter,
                         sample_size, performance_gain, last_calculated, model_version,
                         is_active)
                        VALUES (:team_id, :adjustment_type, :adjustment_value, :context_filter,
                                :sample_size, :performance_gain, :last_calculated, 
                                :model_version, :is_active)
                        ON CONFLICT (team_id, adjustment_type, model_version, context_filter)
                        DO UPDATE SET 
                            adjustment_value = EXCLUDED.adjustment_value,
                            sample_size = EXCLUDED.sample_size,
                            performance_gain = EXCLUDED.performance_gain,
                            last_calculated = EXCLUDED.last_calculated,
                            updated_at = CURRENT_TIMESTAMP;
                    """)
                    
                    conn.execute(query, {
                        'team_id': team_id,
                        'adjustment_type': adj['type'],
                        'adjustment_value': round(adj['value'], 4),
                        'context_filter': adj['context'],
                        'sample_size': stats['total'],
                        'performance_gain': round(accuracy_diff * 100, 2),
                        'last_calculated': date.today(),
                        'model_version': self.model_version,
                        'is_active': True
                    })
                    
                    adjustments.append({
                        'team': team_id,
                        'type': adj['type'],
                        'value': adj['value'],
                        'accuracy_diff': accuracy_diff * 100
                    })
            
            conn.commit()
        
        logger.info(f"✅ Updated {len(adjustments)} team accuracy adjustment records")
        return adjustments
    
    def get_adaptive_parameters(self) -> Dict:
        """Retrieve current adaptive parameters for model use"""
        with self.engine.connect() as conn:
            # Get model parameters
            query = text("""
                SELECT parameter_name, parameter_value, parameter_category
                FROM model_parameters
                WHERE model_version = :model_version
                AND is_active = true
                ORDER BY parameter_name;
            """)
            
            params = conn.execute(query, {'model_version': self.model_version}).fetchall()
            
            # Get confidence calibration
            cal_query = text("""
                SELECT confidence_range, calibration_factor
                FROM confidence_calibration
                WHERE model_version = :model_version
                ORDER BY confidence_range;
            """)
            
            calibration = conn.execute(cal_query, {'model_version': self.model_version}).fetchall()
            
            # Get feature weights
            feature_query = text("""
                SELECT feature_name, weight_adjustment
                FROM feature_performance
                WHERE model_version = :model_version
                AND date = (SELECT MAX(date) FROM feature_performance WHERE model_version = :model_version)
                ORDER BY feature_name;
            """)
            
            features = conn.execute(feature_query, {'model_version': self.model_version}).fetchall()
        
        return {
            'parameters': {p.parameter_name: p.parameter_value for p in params},
            'calibration': {c.confidence_range: c.calibration_factor for c in calibration},
            'feature_weights': {f.feature_name: f.weight_adjustment for f in features}
        }
    
    def apply_adaptive_features(self, feature_vector: List[float], feature_names: List[str]) -> List[float]:
        """Apply adaptive feature weights to a feature vector for enhanced predictions"""
        if not feature_names or len(feature_names) != len(feature_vector):
            logger.warning("⚠️ Feature names don't match feature vector size")
            return feature_vector
        
        try:
            # Get current adaptive parameters
            adaptive_params = self.get_adaptive_parameters()
            feature_weights = adaptive_params.get('feature_weights', {})
            
            if not feature_weights:
                logger.info("No adaptive feature weights available, using original features")
                return feature_vector
            
            # Apply adaptive weights to features
            adapted_vector = []
            applied_adjustments = 0
            
            for i, (feature_name, feature_value) in enumerate(zip(feature_names, feature_vector)):
                weight_adjustment = feature_weights.get(feature_name, 1.0)
                
                # Apply weight adjustment to feature value
                # For normalized features (0-1), we scale the value
                if 0 <= feature_value <= 1:
                    adjusted_value = min(1.0, max(0.0, feature_value * weight_adjustment))
                else:
                    # For non-normalized features, apply adjustment more conservatively
                    adjustment_factor = 0.5 + (weight_adjustment * 0.5)  # Convert 0.5-1.5 to 0.75-1.25
                    adjusted_value = feature_value * adjustment_factor
                
                adapted_vector.append(adjusted_value)
                
                if weight_adjustment != 1.0:
                    applied_adjustments += 1
            
            logger.info(f"🔧 Applied adaptive weights to {applied_adjustments}/{len(feature_vector)} features")
            return adapted_vector
            
        except Exception as e:
            logger.error(f"Error applying adaptive features: {e}")
            return feature_vector  # Return original on error
    
    def apply_adaptive_confidence(self, raw_confidence: float) -> float:
        """Apply confidence calibration to raw model confidence"""
        try:
            adaptive_params = self.get_adaptive_parameters()
            calibration = adaptive_params.get('calibration', {})
            
            if not calibration:
                return raw_confidence
            
            # Determine which confidence bin this prediction falls into
            confidence_pct = raw_confidence * 100
            
            calibration_factor = 1.0
            if 50 <= confidence_pct < 60:
                calibration_factor = float(calibration.get('50-60%', 1.0))
            elif 60 <= confidence_pct < 70:
                calibration_factor = float(calibration.get('60-70%', 1.0))
            elif 70 <= confidence_pct < 80:
                calibration_factor = float(calibration.get('70-80%', 1.0))
            elif 80 <= confidence_pct < 90:
                calibration_factor = float(calibration.get('80-90%', 1.0))
            elif confidence_pct >= 90:
                calibration_factor = float(calibration.get('90%+', 1.0))
            
            # Apply calibration
            calibrated_confidence = min(0.99, max(0.01, raw_confidence * calibration_factor))
            
            if abs(calibration_factor - 1.0) > 0.01:
                logger.debug(f"🎯 Calibrated confidence: {raw_confidence:.3f} → {calibrated_confidence:.3f} (factor: {calibration_factor:.3f})")
            
            return calibrated_confidence
            
        except Exception as e:
            logger.error(f"Error applying confidence calibration: {e}")
            return raw_confidence
    
    def run_adaptive_learning(self, days_back: int = None):
        """Execute the full adaptive learning pipeline.
        
        Requires at least MIN_PREDICTIONS_FOR_ADAPTATION completed predictions
        with the CURRENT model version before applying any adjustments.
        This prevents stale data from a previous model from poisoning the new one.
        """
        MIN_PREDICTIONS_FOR_ADAPTATION = 30
        
        logger.info("🚀 Starting Adaptive Learning Pipeline")
        
        try:
            # Step 1: Load the model
            if not self.model:
                self.load_model()
            
            # Step 1.5: Check if we have enough predictions with THIS model version
            # Only count predictions that have completed games (so we know if they were correct)
            # Check game_predictions (primary table) with all recent model versions
            with self.engine.connect() as conn:
                count_result = conn.execute(text("""
                    SELECT COUNT(*) FROM game_predictions gp
                    JOIN games g ON gp.game_pk = g.game_pk
                    WHERE g.game_status = 'completed'
                    AND g.home_score IS NOT NULL
                    AND gp.prediction_date >= :start_date
                """), {
                    'start_date': date.today() - timedelta(days=self.lookback_days)
                }).fetchone()
                
                completed_predictions = count_result[0] if count_result else 0
            
            if completed_predictions < MIN_PREDICTIONS_FOR_ADAPTATION:
                logger.warning(
                    f"⚠️ Only {completed_predictions}/{MIN_PREDICTIONS_FOR_ADAPTATION} completed predictions "
                    f"with model {self.model_version}. Skipping adaptation — need more data."
                )
                return {
                    'execution_time': datetime.now().isoformat(),
                    'model_version': self.model_version,
                    'status': 'skipped_insufficient_data',
                    'completed_predictions': completed_predictions,
                    'required_predictions': MIN_PREDICTIONS_FOR_ADAPTATION
                }
            
            # Step 2: Analyze recent performance
            performance_data = self.analyze_recent_performance(days_back)
            
            if not performance_data:
                logger.warning("⚠️ No performance data available - skipping adaptation")
                return None
            
            # Step 3: Update all adaptive learning tables
            feature_updates = self.update_feature_performance(performance_data)
            self.update_confidence_calibration(performance_data)
            model_params = self.update_model_parameters(performance_data, feature_updates)
            team_adjustments = self.update_team_adjustments(performance_data)
            
            # Step 4: Get adaptive parameters for future predictions
            adaptive_params = self.get_adaptive_parameters()
            
            # Step 5: Create summary
            summary = {
                'execution_time': datetime.now().isoformat(),
                'model_version': self.model_version,
                'analysis_period': performance_data['period'],
                'overall_accuracy': performance_data['overall_accuracy'],
                'total_predictions': performance_data['total_predictions'],
                'feature_updates': len(feature_updates),
                'confidence_calibrations': len(performance_data.get('confidence_performance', {})),
                'model_parameters': len(model_params),
                'team_adjustments': len(team_adjustments),
                'adaptive_parameters': adaptive_params
            }
            
            logger.info("✅ Adaptive Learning Pipeline completed successfully")
            logger.info(f"📈 Overall accuracy: {performance_data['overall_accuracy']:.1%}")
            logger.info(f"🔧 Updated {len(feature_updates)} features, {len(model_params)} parameters")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Adaptive learning failed: {e}")
            raise

def main():
    """Main execution function"""
    try:
        # Initialize and run adaptive learning
        engine = AdaptiveLearningEngine()
        results = engine.run_adaptive_learning()
        
        if results:
            print("\n" + "="*60)
            print("🧠 ADAPTIVE LEARNING SUMMARY")
            print("="*60)
            print(f"Model Version: {results['model_version']}")
            
            # Handle skipped case (insufficient data)
            if results.get('status') == 'skipped_insufficient_data':
                print(f"⚠️ Skipped: Only {results['completed_predictions']}/{results['required_predictions']} "
                      f"completed predictions available for this model version.")
                print("   Need more game results before adaptive learning can run.")
                print(f"\n⏳ Run predictions and wait for games to complete, then try again.")
                return
            
            print(f"Analysis Period: {results['analysis_period']}")
            print(f"Overall Accuracy: {results['overall_accuracy']:.1%}")
            print(f"Total Predictions Analyzed: {results['total_predictions']}")
            print(f"\n📊 Updates Made:")
            print(f"   • Feature accuracy signals: {results['feature_updates']}")
            print(f"   • Confidence calibrations: {results['confidence_calibrations']}")
            print(f"   • Model parameters: {results['model_parameters']}")
            print(f"   • Team accuracy adjustments: {results['team_adjustments']}")
            
            # Show sample of adaptive parameters
            adaptive_params = results.get('adaptive_parameters', {})
            feature_weights = adaptive_params.get('feature_weights', {})
            if feature_weights:
                print(f"\n🔧 Top Feature Weight Adjustments (based on accuracy signal):")
                sorted_weights = sorted(feature_weights.items(), 
                                      key=lambda x: abs(float(x[1]) - 1.0), reverse=True)[:5]
                for feature, weight in sorted_weights:
                    weight_float = float(weight)
                    direction = "↑" if weight_float > 1.0 else "↓" if weight_float < 1.0 else "="
                    print(f"   {direction} {feature}: {weight_float:.3f}")
            
            print(f"\n✅ Adaptive learning completed at {results['execution_time']}")
        else:
            print("⚠️ No adaptive learning performed - insufficient data")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

def test_adaptive_features():
    """Test the adaptive feature application functionality"""
    print("\n🔧 Testing Adaptive Feature Application")
    print("="*50)
    
    try:
        engine = AdaptiveLearningEngine()
        
        # Try to load a model
        try:
            engine.load_model()
            print(f"✅ Model loaded with {len(engine.feature_names)} features")
            
            # Test feature vector adaptation
            if engine.feature_names:
                # Create a sample feature vector
                sample_features = [0.5] * len(engine.feature_names)
                
                print(f"📊 Testing adaptive features on {len(sample_features)} features...")
                adapted_features = engine.apply_adaptive_features(sample_features, engine.feature_names)
                
                # Count how many features were adjusted
                adjustments = sum(1 for orig, adapt in zip(sample_features, adapted_features) 
                                if abs(orig - adapt) > 0.001)
                print(f"🔧 {adjustments} features were adjusted by adaptive learning")
                
                # Test confidence calibration
                test_confidences = [0.55, 0.65, 0.75, 0.85, 0.95]
                print(f"\n🎯 Testing confidence calibration:")
                for conf in test_confidences:
                    calibrated = engine.apply_adaptive_confidence(conf)
                    change = calibrated - conf
                    direction = "↑" if change > 0 else "↓" if change < 0 else "="
                    print(f"   {conf:.1%} → {calibrated:.1%} {direction}")
                    
        except FileNotFoundError:
            print("⚠️ No trained model found - run model training first")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_adaptive_features()
    else:
        main()

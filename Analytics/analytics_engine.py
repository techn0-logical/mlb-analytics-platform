#!/usr/bin/env python3
"""
Simple MLB Analytics Engine
===========================

A streamlined, production-ready analytics system for MLB data analysis and predictions.
Maintains all core functionality with simple, clean functions.

Features:
- Team analysis with advanced metrics
- Game predictions with ML integration
- Trade and injury impact assessment
- Professional caching and error handling
- Full database integration

Author: MLB Analytics Team
Version: 4.0.0 (Simplified)
"""

import logging
import warnings
import sys
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'Database' / 'config'))

# Database imports
try:
    from Database.config.database import DatabaseConfig
    from Database.models.models import (
        Game, Team, Player, MLBTransaction, PlayerInjury,
        PlayerBattingStats, PlayerPitchingStats
    )
    from sqlalchemy import and_, or_, func, desc
    from sqlalchemy.orm import sessionmaker
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

# Scientific computing
try:
    import pandas as pd
    import numpy as np
    SCIENTIFIC_AVAILABLE = True
except ImportError:
    SCIENTIFIC_AVAILABLE = False

# Machine learning (optional)
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    import xgboost as xgb
    import pickle
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

@dataclass
class TeamStats:
    """Simple team statistics"""
    team_id: str
    team_name: str
    wins: int = 0
    losses: int = 0
    win_pct: float = 0.5
    runs_scored: int = 0
    runs_allowed: int = 0
    games_played: int = 0
    strength_rating: float = 0.5
    recent_form: float = 0.5
    home_advantage: float = 0.054
    trade_impact: float = 0.0
    injury_impact: float = 0.0
    confidence: float = 0.5

@dataclass 
class GamePrediction:
    """Simple game prediction"""
    home_team: str
    away_team: str
    game_date: date
    predicted_winner: str
    win_probability: float
    confidence_level: str
    factors: List[str] = field(default_factory=list)
    prediction_type: str = "statistical"  # "statistical", "ml", or "hybrid"

# =============================================================================
# GLOBAL CONFIGURATION
# =============================================================================

CONFIG = {
    'cache_ttl': 3600,  # 1 hour
    'min_games_analysis': 10,
    'min_games_prediction': 20,
    'confidence_high': 0.65,
    'confidence_medium': 0.55,
    'confidence_low': 0.51,
    'recent_games_window': 10,
    'trade_impact_days': 30
}

# Global cache and session
_cache = {}
_session = None

# =============================================================================
# UTILITY FUNCTIONS
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

def cache_key(*args) -> str:
    """Generate cache key"""
    return "|".join(str(arg) for arg in args)

def get_cached(key: str) -> Optional[Any]:
    """Get cached result if valid"""
    if key in _cache:
        result, timestamp = _cache[key]
        if datetime.now() - timestamp < timedelta(seconds=CONFIG['cache_ttl']):
            return result
        del _cache[key]
    return None

def set_cached(key: str, result: Any):
    """Store result in cache"""
    _cache[key] = (result, datetime.now())

def get_confidence_level(probability: float) -> str:
    """Get confidence level from probability"""
    if probability >= CONFIG['confidence_high']:
        return "high"
    elif probability >= CONFIG['confidence_medium']:
        return "medium"
    return "low"

def safe_divide(numerator, denominator, default=0.0):
    """Safe division with default value"""
    try:
        return numerator / denominator if denominator != 0 else default
    except:
        return default

# =============================================================================
# CORE ANALYSIS FUNCTIONS
# =============================================================================

def calculate_pythagorean(runs_scored: int, runs_allowed: int) -> float:
    """Calculate Pythagorean expectation"""
    if runs_scored <= 0 or runs_allowed <= 0:
        return 0.5
    exponent = 1.83  # Baseball-specific
    return (runs_scored ** exponent) / (runs_scored ** exponent + runs_allowed ** exponent)

def calculate_recent_form(games: List[Game], team_id: str, window: int = 10) -> float:
    """Calculate recent form over specified window"""
    if not games:
        return 0.5
    
    # Get most recent games
    recent_games = sorted(games, key=lambda x: x.game_date, reverse=True)[:window]
    
    if not recent_games:
        return 0.5
    
    wins = 0
    for game in recent_games:
        team_won = (
            (game.home_team_id == team_id and game.home_score > game.away_score) or
            (game.away_team_id == team_id and game.away_score > game.home_score)
        )
        if team_won:
            wins += 1
    
    return safe_divide(wins, len(recent_games), 0.5)

def get_trade_impact(team_id: str, days_back: int = 30) -> float:
    """Calculate recent trade impact for team"""
    try:
        session = get_session()
        cutoff_date = date.today() - timedelta(days=days_back)
        
        # Get recent trades
        trades = session.query(MLBTransaction).filter(
            and_(
                or_(
                    MLBTransaction.from_team_id == team_id,
                    MLBTransaction.to_team_id == team_id
                ),
                MLBTransaction.transaction_date >= cutoff_date
            )
        ).all()
        
        if not trades:
            return 0.0
        
        # Simple impact calculation
        impact = 0.0
        for trade in trades:
            if trade.to_team_id == team_id:  # Gain
                impact += 0.1
            elif trade.from_team_id == team_id:  # Loss
                impact -= 0.1
        
        # Normalize between -0.5 and 0.5
        return max(-0.5, min(0.5, impact))
        
    except Exception as e:
        logger.error(f"Error calculating trade impact: {e}")
        return 0.0

def get_injury_impact(team_id: str) -> float:
    """Calculate current injury impact for team"""
    try:
        session = get_session()
        
        # Get team players
        team_players = session.query(Player).filter(
            Player.current_team_id == team_id
        ).all()
        
        if not team_players:
            return 0.0
        
        player_ids = [p.player_id for p in team_players]
        
        # Get active injuries
        active_injuries = session.query(PlayerInjury).filter(
            and_(
                PlayerInjury.player_id.in_(player_ids),
                or_(
                    PlayerInjury.actual_return_date.is_(None),
                    PlayerInjury.actual_return_date > date.today()
                ),
                PlayerInjury.injury_date <= date.today()
            )
        ).all()
        
        if not active_injuries:
            return 0.0
        
        # Simple impact: 0.1 per injury, max 0.5
        impact = min(0.5, len(active_injuries) * 0.1)
        return impact
        
    except Exception as e:
        logger.error(f"Error calculating injury impact: {e}")
        return 0.0

# =============================================================================
# MAIN ANALYSIS FUNCTIONS  
# =============================================================================

def analyze_team(team_id: str, as_of_date: date = None) -> TeamStats:
    """Analyze team performance with all factors"""
    if as_of_date is None:
        as_of_date = date.today()
    
    # Check cache
    key = cache_key("team_analysis", team_id, as_of_date)
    cached = get_cached(key)
    if cached:
        return cached
    
    try:
        session = get_session()
        
        # Get team games up to analysis date
        games = session.query(Game).filter(
            and_(
                or_(Game.home_team_id == team_id, Game.away_team_id == team_id),
                Game.game_date <= as_of_date,
                Game.home_score.isnot(None),
                Game.away_score.isnot(None)
            )
        ).order_by(Game.game_date).all()
        
        if not games:
            logger.warning(f"No games found for team {team_id}")
            return TeamStats(team_id=team_id, team_name=team_id)
        
        # Calculate basic stats
        wins = losses = runs_scored = runs_allowed = 0
        home_wins = home_losses = 0
        
        for game in games:
            is_home = game.home_team_id == team_id
            
            if is_home:
                team_score = game.home_score
                opp_score = game.away_score
                if team_score > opp_score:
                    wins += 1
                    home_wins += 1
                else:
                    losses += 1
                    home_losses += 1
            else:
                team_score = game.away_score  
                opp_score = game.home_score
                if team_score > opp_score:
                    wins += 1
                else:
                    losses += 1
            
            runs_scored += team_score
            runs_allowed += opp_score
        
        games_played = len(games)
        win_pct = safe_divide(wins, games_played, 0.5)
        
        # Advanced calculations
        pythagorean = calculate_pythagorean(runs_scored, runs_allowed)
        recent_form = calculate_recent_form(games, team_id, CONFIG['recent_games_window'])
        
        # Calculate strength rating
        strength_rating = (win_pct * 0.5) + (pythagorean * 0.3) + (recent_form * 0.2)
        
        # Home field advantage
        home_total = home_wins + home_losses
        home_pct = safe_divide(home_wins, home_total, 0.5) if home_total > 0 else 0.5
        home_advantage = home_pct - 0.5
        
        # External factors
        trade_impact = get_trade_impact(team_id)
        injury_impact = get_injury_impact(team_id)
        
        # Calculate confidence
        confidence = 0.5
        if games_played >= CONFIG['min_games_analysis']:
            confidence += 0.2
        if games_played >= CONFIG['min_games_prediction']:
            confidence += 0.2
        confidence *= (1.0 - injury_impact * 0.3)  # Reduce confidence with injuries
        confidence = max(0.1, min(1.0, confidence))
        
        # Get team name
        team_name = get_team_name(team_id)
        
        result = TeamStats(
            team_id=team_id,
            team_name=team_name,
            wins=wins,
            losses=losses,
            win_pct=win_pct,
            runs_scored=runs_scored,
            runs_allowed=runs_allowed,
            games_played=games_played,
            strength_rating=strength_rating,
            recent_form=recent_form,
            home_advantage=home_advantage,
            trade_impact=trade_impact,
            injury_impact=injury_impact,
            confidence=confidence
        )
        
        # Cache result
        set_cached(key, result)
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing team {team_id}: {e}")
        return TeamStats(team_id=team_id, team_name=team_id)

def predict_game(home_team: str, away_team: str, game_date: date = None) -> GamePrediction:
    """Predict game outcome using comprehensive analysis"""
    if game_date is None:
        game_date = date.today()
    
    # Check cache
    key = cache_key("game_prediction", home_team, away_team, game_date)
    cached = get_cached(key)
    if cached:
        return cached
    
    try:
        # Analyze both teams
        home_stats = analyze_team(home_team, game_date)
        away_stats = analyze_team(away_team, game_date)
        
        factors = []
        
        # Base probability starts with home field advantage
        home_prob = 0.5 + home_stats.home_advantage
        
        # Team strength difference (40% weight)
        strength_diff = home_stats.strength_rating - away_stats.strength_rating
        home_prob += strength_diff * 0.4
        
        if abs(strength_diff) > 0.1:
            stronger = home_team if strength_diff > 0 else away_team
            factors.append(f"Team strength: {stronger} ({abs(strength_diff):.3f})")
        
        # Recent form (25% weight)
        form_diff = home_stats.recent_form - away_stats.recent_form
        home_prob += form_diff * 0.25
        
        if abs(form_diff) > 0.2:
            hot_team = home_team if form_diff > 0 else away_team
            factors.append(f"Recent form: {hot_team} ({abs(form_diff):.3f})")
        
        # Trade impact (15% weight)
        trade_diff = home_stats.trade_impact - away_stats.trade_impact
        home_prob += trade_diff * 0.15
        
        if abs(trade_diff) > 0.1:
            factors.append(f"Trade impact favors {'home' if trade_diff > 0 else 'away'}")
        
        # Injury impact (20% weight) - injuries hurt performance
        injury_diff = away_stats.injury_impact - home_stats.injury_impact
        home_prob += injury_diff * 0.20
        
        if home_stats.injury_impact > 0.2:
            factors.append(f"Home team injury concerns ({home_stats.injury_impact:.2f})")
        if away_stats.injury_impact > 0.2:
            factors.append(f"Away team injury concerns ({away_stats.injury_impact:.2f})")
        
        # Ensure probability bounds
        home_prob = max(0.05, min(0.95, home_prob))
        
        # Determine winner and final probability
        predicted_winner = home_team if home_prob > 0.5 else away_team
        win_probability = home_prob if home_prob > 0.5 else 1 - home_prob
        
        # Calculate overall confidence
        confidence = min(home_stats.confidence, away_stats.confidence)
        
        # Reduce confidence for close games (less certain)
        if abs(home_prob - 0.5) < 0.05:
            confidence *= 0.8
            
        confidence_level = get_confidence_level(confidence)
        
        result = GamePrediction(
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            predicted_winner=predicted_winner,
            win_probability=win_probability,
            confidence_level=confidence_level,
            factors=factors,
            prediction_type="statistical"
        )
        
        # Cache result
        set_cached(key, result)
        return result
        
    except Exception as e:
        logger.error(f"Error predicting {away_team} @ {home_team}: {e}")
        return GamePrediction(
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            predicted_winner=home_team,
            win_probability=0.54,
            confidence_level="low",
            factors=["Error in analysis - using default prediction"]
        )

# =============================================================================
# MACHINE LEARNING FUNCTIONS
# =============================================================================

class SimpleMLModel:
    """Simplified ML model for game predictions"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_columns = None
        
    def create_features(self, games_data: List[Dict]) -> pd.DataFrame:
        """Create simple features for ML"""
        if not SCIENTIFIC_AVAILABLE:
            return pd.DataFrame()
        
        df = pd.DataFrame(games_data)
        if df.empty:
            return df
        
        # Remove any leaky columns
        outcome_cols = ['home_score', 'away_score', 'winner_team_id', 'home_win']
        for col in outcome_cols:
            if col in df.columns:
                logger.warning(f"Removing leaky column: {col}")
                df = df.drop(columns=[col])
        
        # Basic features
        df['is_home'] = 1
        if 'game_date' in df.columns:
            df['game_date'] = pd.to_datetime(df['game_date'])
            df['day_of_week'] = df['game_date'].dt.dayofweek
            df['month'] = df['game_date'].dt.month
            df['is_weekend'] = (df['game_date'].dt.dayofweek >= 5).astype(int)
        
        return df
    
    def train(self, games_data: List[Dict]) -> Dict[str, Any]:
        """Train ML model"""
        if not ML_AVAILABLE:
            return {'success': False, 'error': 'ML libraries not available'}
        
        try:
            # Preserve targets before feature engineering
            games_df = pd.DataFrame(games_data)
            
            if 'winner_team_id' in games_df.columns and 'home_team_id' in games_df.columns:
                targets = (games_df['winner_team_id'] == games_df['home_team_id']).astype(int)
            elif 'home_win' in games_df.columns:
                targets = games_df['home_win'].astype(int)
            else:
                return {'success': False, 'error': 'No target variable found'}
            
            # Create features
            df = self.create_features(games_data)
            if df.empty:
                return {'success': False, 'error': 'No features created'}
            
            # Add targets back
            df['target'] = targets
            
            # Prepare features
            feature_cols = [col for col in df.columns if col not in [
                'game_id', 'game_pk', 'game_date', 'home_team_id', 'away_team_id', 'target'
            ]]
            
            X = df[feature_cols].select_dtypes(include=[np.number]).fillna(0)
            y = df['target']
            
            if X.empty:
                return {'success': False, 'error': 'No numeric features'}
            
            self.feature_columns = list(X.columns)
            
            # Split and train
            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
            
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_val_scaled = self.scaler.transform(X_val)
            
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            val_pred = self.model.predict(X_val_scaled)
            from sklearn.metrics import accuracy_score
            accuracy = accuracy_score(y_val, val_pred)
            
            self.is_trained = True
            
            logger.info(f"ML model trained: {accuracy:.3f} accuracy")
            return {'success': True, 'accuracy': accuracy, 'features': len(self.feature_columns)}
            
        except Exception as e:
            logger.error(f"ML training error: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict_ml(self, home_team: str, away_team: str, game_date: date = None) -> Optional[float]:
        """Make ML prediction"""
        if not self.is_trained:
            return None
        
        try:
            # Create dummy data
            dummy_game = {
                'home_team_id': home_team,
                'away_team_id': away_team,
                'game_date': game_date or date.today()
            }
            
            df = self.create_features([dummy_game])
            if df.empty:
                return None
            
            X = df[self.feature_columns].fillna(0)
            X_scaled = self.scaler.transform(X)
            
            prob = self.model.predict_proba(X_scaled)[0]
            return prob[1]  # Home team win probability
            
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return None

# Global ML model instance
ml_model = SimpleMLModel()

def train_ml_model(games_data: List[Dict]) -> Dict[str, Any]:
    """Train the ML model"""
    return ml_model.train(games_data)

def predict_game_with_ml(home_team: str, away_team: str, game_date: date = None) -> GamePrediction:
    """Predict game with ML + statistical hybrid"""
    # Get statistical prediction
    stat_prediction = predict_game(home_team, away_team, game_date)
    
    # Get ML prediction if available
    ml_prob = ml_model.predict_ml(home_team, away_team, game_date)
    
    if ml_prob is None:
        return stat_prediction
    
    # Blend predictions: 60% statistical, 40% ML
    stat_prob = stat_prediction.win_probability
    if stat_prediction.predicted_winner != home_team:
        stat_prob = 1 - stat_prob
    
    blended_prob = stat_prob * 0.6 + ml_prob * 0.4
    
    # Update prediction
    predicted_winner = home_team if blended_prob > 0.5 else away_team
    win_probability = blended_prob if blended_prob > 0.5 else 1 - blended_prob
    
    # Enhanced factors
    enhanced_factors = stat_prediction.factors + ["ML model integration", "Hybrid prediction"]
    
    return GamePrediction(
        home_team=home_team,
        away_team=away_team,
        game_date=game_date or date.today(),
        predicted_winner=predicted_winner,
        win_probability=win_probability,
        confidence_level=stat_prediction.confidence_level,
        factors=enhanced_factors,
        prediction_type="hybrid"
    )

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_team_name(team_id: str) -> str:
    """Get full team name"""
    team_names = {
        'AZ': 'Arizona Diamondbacks', 'ATL': 'Atlanta Braves', 'BAL': 'Baltimore Orioles',
        'BOS': 'Boston Red Sox', 'CHC': 'Chicago Cubs', 'CHW': 'Chicago White Sox',
        'CIN': 'Cincinnati Reds', 'CLE': 'Cleveland Guardians', 'COL': 'Colorado Rockies',
        'DET': 'Detroit Tigers', 'HOU': 'Houston Astros', 'KC': 'Kansas City Royals',
        'LAA': 'Los Angeles Angels', 'LAD': 'Los Angeles Dodgers', 'MIA': 'Miami Marlins',
        'MIL': 'Milwaukee Brewers', 'MIN': 'Minnesota Twins', 'NYM': 'New York Mets',
        'NYY': 'New York Yankees', 'OAK': 'Oakland Athletics', 'PHI': 'Philadelphia Phillies',
        'PIT': 'Pittsburgh Pirates', 'SD': 'San Diego Padres', 'SF': 'San Francisco Giants',
        'SEA': 'Seattle Mariners', 'STL': 'St. Louis Cardinals', 'TB': 'Tampa Bay Rays',
        'TEX': 'Texas Rangers', 'TOR': 'Toronto Blue Jays', 'WSH': 'Washington Nationals'
    }
    return team_names.get(team_id, team_id)

def get_system_status() -> Dict[str, Any]:
    """Get system status"""
    return {
        'database_available': DATABASE_AVAILABLE,
        'scientific_available': SCIENTIFIC_AVAILABLE,
        'ml_available': ML_AVAILABLE,
        'ml_trained': ml_model.is_trained,
        'cache_size': len(_cache),
        'config': CONFIG
    }

def clear_cache():
    """Clear the cache"""
    global _cache
    _cache = {}
    logger.info("Cache cleared")

# =============================================================================
# COMPATIBILITY LAYER
# =============================================================================

class SabermetricCalculator:
    """Compatibility class for existing code"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.is_trained = True
    
    def predict_game(self, home_team_id: str, away_team_id: str, game_date: date = None,
                    save_prediction: bool = False, allow_historical: bool = False) -> Optional[GamePrediction]:
        """Predict game - compatibility method"""
        try:
            if ml_model.is_trained:
                return predict_game_with_ml(home_team_id, away_team_id, game_date)
            else:
                return predict_game(home_team_id, away_team_id, game_date)
        except Exception as e:
            logger.error(f"Compatibility prediction error: {e}")
            return None

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("🚀 Simple MLB Analytics Engine")
    print("=" * 50)
    
    if not DATABASE_AVAILABLE:
        print("❌ Database not available")
        exit(1)
    
    # Test system
    print(f"📊 System Status: {get_system_status()}")
    
    # Test team analysis
    print("\n🔍 Testing team analysis...")
    stats = analyze_team("LAD")
    print(f"Team: {stats.team_name}")
    print(f"Record: {stats.wins}-{stats.losses} ({stats.win_pct:.3f})")
    print(f"Strength: {stats.strength_rating:.3f}")
    
    # Test prediction
    print("\n🎯 Testing prediction...")
    pred = predict_game("LAD", "SF")
    print(f"Prediction: {pred.predicted_winner} ({pred.win_probability:.1%})")
    print(f"Confidence: {pred.confidence_level}")
    
    print("\n✅ All tests completed!")
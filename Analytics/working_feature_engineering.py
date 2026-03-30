#!/usr/bin/env python3
"""
WORKING Enhanced Feature Engineering System
===========================================

Simplified version that focuses on the core features that will improve accuracy
without complex SQL queries that need debugging.
"""

import sys
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    from Database.config.database import db_config
    from sqlalchemy import text
except ImportError:
    print("Database not available")

import logging
logger = logging.getLogger(__name__)

class WorkingFeatureEngineer:
    """
    Simplified but effective feature engineering that actually works.
    Uses in-memory caching for season-level stats to avoid redundant DB queries.
    """
    
    def __init__(self):
        self.SessionLocal = db_config.create_session_factory()
        self.session = None
        # Cache: keyed by (team_id, season) for batting/pitching, (team_id, date_str) for transactions
        self._batting_cache = {}
        self._pitching_cache = {}
        self._transaction_cache = {}
        self._h2h_cache = {}
        self._starter_cache = {}
        self._bullpen_cache = {}
    
    def get_session(self):
        """Get database session"""
        if self.session is None:
            self.session = self.SessionLocal()
        return self.session
    
    def close_session(self):
        """Close database session"""
        if self.session:
            self.session.close()
            self.session = None
    
    def clear_cache(self):
        """Clear all feature caches"""
        self._batting_cache.clear()
        self._pitching_cache.clear()
        self._transaction_cache.clear()
        self._h2h_cache.clear()
        self._starter_cache.clear()
        self._bullpen_cache.clear()
    
    def create_team_batting_features(self, team_id: str, as_of_date: date, prefix: str = "team") -> Dict[str, float]:
        """Create batting features from player stats aggregation.
        
        Args:
            team_id: The team abbreviation (e.g., 'NYY')
            as_of_date: Date to query stats as of
            prefix: Feature name prefix ('home' or 'away') for consistent naming
        
        Early season logic (before May): uses previous year's full-season stats instead
        of current year's tiny sample sizes, which produce extreme noise.
        Falls back to the most recent season with data if current season has none.
        Uses in-memory cache keyed by (team_id, season_year) since stats are season-level.
        """
        session = self.get_session()
        raw_year = as_of_date.year if isinstance(as_of_date, date) else int(str(as_of_date)[:4])
        
        # Early season override: use prior year until May 1 of current year
        # Small early-season samples (~20 AB) produce extreme noise in batting features
        if isinstance(as_of_date, date) and as_of_date.month <= 4 and as_of_date.year == date.today().year:
            season_year = raw_year - 1
        else:
            season_year = raw_year
        cache_key = (team_id, season_year)
        
        # Check cache for raw stats (prefix-independent)
        if cache_key not in self._batting_cache:
            # Query with fallback: try target season first, then most recent available
            batting_query = text('''
                WITH target_season AS (
                    SELECT COALESCE(
                        (SELECT season FROM player_batting_stats 
                         WHERE team_id = :team_id AND season = :season_year
                         LIMIT 1),
                        (SELECT MAX(season) FROM player_batting_stats 
                         WHERE team_id = :team_id)
                    ) AS season
                )
                SELECT 
                    COUNT(*) as player_count,
                    AVG(batting_average) as avg_ba,
                    AVG(ops) as avg_ops,
                    AVG(on_base_percentage) as avg_obp,
                    AVG(slugging_percentage) as avg_slg,
                    SUM(home_runs) as total_hrs,
                    SUM(rbis) as total_rbis,
                    SUM(stolen_bases) as total_sbs,
                    AVG(COALESCE(war, 0)) as avg_war
                FROM player_batting_stats 
                WHERE team_id = :team_id 
                AND season = (SELECT season FROM target_season)
            ''')
            
            result = session.execute(batting_query, {
                'team_id': team_id,
                'season_year': season_year
            }).fetchone()
            
            self._batting_cache[cache_key] = result
        
        result = self._batting_cache[cache_key]
        
        if result and result[0] > 0:
            (player_count, avg_ba, avg_ops, avg_obp, avg_slg, 
             total_hrs, total_rbis, total_sbs, avg_war) = result
            
            # Convert to float and normalize
            # NOTE: Normalization ranges set wide enough for spring training inflated stats
            # so that teams remain differentiated (not all clipped to 1.0)
            return {
                f'{prefix}_batting_avg': min(float(avg_ba or 0.250) / 0.350, 1.0),
                f'{prefix}_ops': min(float(avg_ops or 0.700) / 1.200, 1.0),
                f'{prefix}_obp': min(float(avg_obp or 0.320) / 0.500, 1.0),
                f'{prefix}_slg': min(float(avg_slg or 0.400) / 0.700, 1.0),
                f'{prefix}_power': min(float(total_hrs or 100) / 250.0, 1.0),
                f'{prefix}_production': min(float(total_rbis or 400) / 800.0, 1.0),
                f'{prefix}_speed': min(float(total_sbs or 50) / 150.0, 1.0),
                f'{prefix}_batting_war': max(0, min(float(avg_war or 0) / 3.0, 1.0)) if float(avg_war or 0) > 0 else 0.5,
                f'{prefix}_batting_depth': min(int(player_count or 15) / 25.0, 1.0)
            }
        else:
            # Default values if no data
            return {
                f'{prefix}_batting_avg': 0.500,
                f'{prefix}_ops': 0.500,
                f'{prefix}_obp': 0.500,
                f'{prefix}_slg': 0.500,
                f'{prefix}_power': 0.500,
                f'{prefix}_production': 0.500,
                f'{prefix}_speed': 0.500,
                f'{prefix}_batting_war': 0.500,
                f'{prefix}_batting_depth': 0.500
            }
    
    def create_team_pitching_features(self, team_id: str, as_of_date: date, prefix: str = "team") -> Dict[str, float]:
        """Create pitching features from player stats aggregation.
        
        Args:
            team_id: The team abbreviation (e.g., 'NYY')
            as_of_date: Date to query stats as of
            prefix: Feature name prefix ('home' or 'away') for consistent naming
        
        Early season logic (before May): uses previous year's full-season stats instead
        of current year's tiny sample sizes, which produce extreme noise.
        Falls back to the most recent season with data if current season has none.
        Uses in-memory cache keyed by (team_id, season_year) since stats are season-level.
        """
        session = self.get_session()
        raw_year = as_of_date.year if isinstance(as_of_date, date) else int(str(as_of_date)[:4])
        
        # Early season override: use prior year until May 1 of current year
        if isinstance(as_of_date, date) and as_of_date.month <= 4 and as_of_date.year == date.today().year:
            season_year = raw_year - 1
        else:
            season_year = raw_year
        cache_key = (team_id, season_year)
        
        # Check cache for raw stats (prefix-independent)
        if cache_key not in self._pitching_cache:
            # Query with fallback: try target season first, then most recent available
            pitching_query = text('''
                WITH target_season AS (
                    SELECT COALESCE(
                        (SELECT season FROM player_pitching_stats 
                         WHERE team_id = :team_id AND season = :season_year
                         LIMIT 1),
                        (SELECT MAX(season) FROM player_pitching_stats 
                         WHERE team_id = :team_id)
                    ) AS season
                )
                SELECT 
                    COUNT(*) as player_count,
                    AVG(era) as avg_era,
                    AVG(whip) as avg_whip,
                    AVG(k_per_9) as avg_k9,
                    AVG(bb_per_9) as avg_bb9,
                    SUM(wins) as total_wins,
                    SUM(saves) as total_saves,
                    AVG(COALESCE(war, 0)) as avg_war
                FROM player_pitching_stats 
                WHERE team_id = :team_id 
                AND season = (SELECT season FROM target_season)
            ''')
            
            result = session.execute(pitching_query, {
                'team_id': team_id,
                'season_year': season_year
            }).fetchone()
            
            self._pitching_cache[cache_key] = result
        
        result = self._pitching_cache[cache_key]
        
        if result and result[0] > 0:
            (player_count, avg_era, avg_whip, avg_k9, avg_bb9, 
             total_wins, total_saves, avg_war) = result
            
            # Convert to float and normalize (lower ERA/WHIP is better)
            # NOTE: Normalization ranges set wide enough for spring training inflated stats
            return {
                f'{prefix}_era_quality': max(0, 1 - float(avg_era or 4.50) / 9.00),
                f'{prefix}_whip_quality': max(0, 1 - float(avg_whip or 1.30) / 2.50),
                f'{prefix}_strikeout_rate': min(float(avg_k9 or 8.0) / 15.0, 1.0),
                f'{prefix}_control': max(0, 1 - float(avg_bb9 or 3.5) / 8.0),
                f'{prefix}_wins': min(float(total_wins or 50) / 100.0, 1.0),
                f'{prefix}_saves': min(float(total_saves or 20) / 50.0, 1.0),
                f'{prefix}_pitching_war': max(0, min(float(avg_war or 0) / 3.0, 1.0)) if float(avg_war or 0) > 0 else 0.5,
                f'{prefix}_pitching_depth': min(int(player_count or 10) / 15.0, 1.0)
            }
        else:
            # Default values if no data
            return {
                f'{prefix}_era_quality': 0.500,
                f'{prefix}_whip_quality': 0.500,
                f'{prefix}_strikeout_rate': 0.500,
                f'{prefix}_control': 0.500,
                f'{prefix}_wins': 0.500,
                f'{prefix}_saves': 0.500,
                f'{prefix}_pitching_war': 0.500,
                f'{prefix}_pitching_depth': 0.500
            }
    
    def create_transaction_features(self, team_id: str, as_of_date: date, days: int = 30, prefix: str = "team") -> Dict[str, float]:
        """Create simple transaction features.
        
        Args:
            team_id: The team abbreviation (e.g., 'NYY')
            as_of_date: Date to query transactions as of
            days: Lookback window in days
            prefix: Feature name prefix ('home' or 'away') for consistent naming
        
        Uses cache keyed by (team_id, month_bucket) to reduce DB queries during training.
        """
        session = self.get_session()
        
        lookback_date = as_of_date - timedelta(days=days)
        # Cache by month bucket — transactions don't change day-to-day for training purposes
        cache_key = (team_id, as_of_date.year, as_of_date.month)
        
        if cache_key not in self._transaction_cache:
            transaction_query = text('''
                SELECT 
                    COUNT(*) as total_transactions,
                    COUNT(CASE WHEN to_team_id = :team_id THEN 1 END) as acquisitions,
                    COUNT(CASE WHEN from_team_id = :team_id THEN 1 END) as departures,
                    COUNT(CASE WHEN transaction_type LIKE '%trade%' THEN 1 END) as trades
                FROM mlb_transactions 
                WHERE (from_team_id = :team_id OR to_team_id = :team_id)
                AND transaction_date >= :lookback_date
                AND transaction_date <= :as_of_date
            ''')
            
            result = session.execute(transaction_query, {
                'team_id': team_id,
                'as_of_date': as_of_date,
                'lookback_date': lookback_date
            }).fetchone()
            
            self._transaction_cache[cache_key] = result
        
        result = self._transaction_cache[cache_key]
        
        if result:
            total_trans, acquisitions, departures, trades = result
            return {
                f'{prefix}_roster_activity': min(int(total_trans or 0) / 10.0, 1.0),
                f'{prefix}_acquisitions': int(acquisitions or 0),
                f'{prefix}_departures': int(departures or 0),
                f'{prefix}_net_roster_change': float((acquisitions or 0) - (departures or 0)),
                f'{prefix}_trade_activity': min(int(trades or 0) / 5.0, 1.0),
                f'{prefix}_roster_stability': max(0, 1 - int(total_trans or 0) / 20.0)
            }
        else:
            return {
                f'{prefix}_roster_activity': 0.1,
                f'{prefix}_acquisitions': 0,
                f'{prefix}_departures': 0,
                f'{prefix}_net_roster_change': 0.0,
                f'{prefix}_trade_activity': 0.1,
                f'{prefix}_roster_stability': 0.9
            }
    
    def create_starter_features(self, team_id: str, as_of_date: date, prefix: str = "team",
                                  game_pk: int = None) -> Dict[str, float]:
        """Create starting pitcher features from pitcher_game_logs.
        
        For historical games (training): if game_pk is provided, looks up the actual starter.
        For future games (prediction): identifies the probable starter based on rotation.
        
        Features are based on the starter's last 5 starts (rolling form), which captures
        current performance better than season-level aggregates.
        
        Returns normalized features for: ERA, WHIP, K/9, BB/9, quality start rate,
        average pitch count, and innings depth.
        """
        session = self.get_session()
        cache_key = (team_id, str(as_of_date), game_pk)
        
        if cache_key in self._starter_cache:
            return self._apply_prefix(self._starter_cache[cache_key], prefix)
        
        defaults = {
            'starter_era': 0.500,
            'starter_whip': 0.500,
            'starter_k_rate': 0.500,
            'starter_control': 0.500,
            'starter_quality_start_pct': 0.500,
            'starter_avg_ip': 0.500,
            'starter_avg_pitches': 0.500,
        }
        
        # Step 1: Identify the starter
        starter_id = None
        
        if game_pk:
            # Historical: look up who actually started
            row = session.execute(text('''
                SELECT pitcher_id FROM pitcher_game_logs
                WHERE game_pk = :gpk AND pitcher_team_id = :team AND is_starter = true
                LIMIT 1
            '''), {'gpk': game_pk, 'team': team_id}).fetchone()
            if row:
                starter_id = row[0]
        
        if not starter_id:
            # Prediction / fallback: find the most likely next starter
            # Logic: the pitcher who started most recently for this team,
            # but NOT in the last 4 days (standard 5-man rotation rest)
            rest_cutoff = as_of_date - timedelta(days=4)
            row = session.execute(text('''
                SELECT pitcher_id FROM pitcher_game_logs
                WHERE pitcher_team_id = :team AND is_starter = true
                AND game_date < :as_of AND game_date <= :rest_cutoff
                ORDER BY game_date DESC
                LIMIT 1
            '''), {'team': team_id, 'as_of': as_of_date, 'rest_cutoff': rest_cutoff}).fetchone()
            if row:
                starter_id = row[0]
        
        if not starter_id:
            self._starter_cache[cache_key] = defaults
            return self._apply_prefix(defaults, prefix)
        
        # Step 2: Get last 5 starts for this pitcher (before as_of_date)
        starts = session.execute(text('''
            SELECT innings_pitched, earned_runs, hits_allowed, walks, strikeouts,
                   pitches_thrown, is_quality_start
            FROM pitcher_game_logs
            WHERE pitcher_id = :pid AND is_starter = true
            AND game_date < :as_of
            ORDER BY game_date DESC
            LIMIT 5
        '''), {'pid': starter_id, 'as_of': as_of_date}).fetchall()
        
        if not starts:
            self._starter_cache[cache_key] = defaults
            return self._apply_prefix(defaults, prefix)
        
        # Step 3: Compute rolling stats from last 5 starts
        total_ip = sum(float(s[0]) for s in starts)
        total_er = sum(int(s[1]) for s in starts)
        total_h = sum(int(s[2]) for s in starts)
        total_bb = sum(int(s[3]) for s in starts)
        total_k = sum(int(s[4]) for s in starts)
        avg_pitches = sum(int(s[5] or 0) for s in starts) / len(starts)
        qs_count = sum(1 for s in starts if s[6])
        
        era = (9 * total_er / total_ip) if total_ip > 0 else 4.50
        whip = ((total_h + total_bb) / total_ip) if total_ip > 0 else 1.30
        k_per_9 = (9 * total_k / total_ip) if total_ip > 0 else 8.0
        bb_per_9 = (9 * total_bb / total_ip) if total_ip > 0 else 3.5
        avg_ip = total_ip / len(starts)
        qs_pct = qs_count / len(starts)
        
        result = {
            'starter_era': max(0, 1 - era / 9.0),          # Lower ERA = higher value
            'starter_whip': max(0, 1 - whip / 2.5),         # Lower WHIP = higher value
            'starter_k_rate': min(k_per_9 / 15.0, 1.0),     # Higher K/9 = higher value
            'starter_control': max(0, 1 - bb_per_9 / 8.0),  # Lower BB/9 = higher value
            'starter_quality_start_pct': qs_pct,
            'starter_avg_ip': min(avg_ip / 8.0, 1.0),       # Deeper = better
            'starter_avg_pitches': min(avg_pitches / 110.0, 1.0),
        }
        
        self._starter_cache[cache_key] = result
        return self._apply_prefix(result, prefix)
    
    def create_bullpen_features(self, team_id: str, as_of_date: date, prefix: str = "team") -> Dict[str, float]:
        """Create bullpen performance features from pitcher_game_logs.
        
        Looks at all relief appearances for this team in the last 14 days.
        Captures recent bullpen form: ERA, WHIP, K rate, and workload.
        
        Returns normalized features.
        """
        session = self.get_session()
        cache_key = (team_id, str(as_of_date))
        
        if cache_key in self._bullpen_cache:
            return self._apply_prefix(self._bullpen_cache[cache_key], prefix)
        
        defaults = {
            'bullpen_era': 0.500,
            'bullpen_whip': 0.500,
            'bullpen_k_rate': 0.500,
        }
        
        lookback = as_of_date - timedelta(days=14)
        
        result = session.execute(text('''
            SELECT SUM(innings_pitched), SUM(earned_runs), SUM(hits_allowed),
                   SUM(walks), SUM(strikeouts), COUNT(*)
            FROM pitcher_game_logs
            WHERE pitcher_team_id = :team AND is_starter = false
            AND game_date >= :lookback AND game_date < :as_of
        '''), {'team': team_id, 'lookback': lookback, 'as_of': as_of_date}).fetchone()
        
        if not result or not result[0] or float(result[0]) == 0:
            self._bullpen_cache[cache_key] = defaults
            return self._apply_prefix(defaults, prefix)
        
        total_ip, total_er, total_h, total_bb, total_k, appearances = result
        total_ip = float(total_ip)
        
        era = (9 * int(total_er) / total_ip) if total_ip > 0 else 4.50
        whip = ((int(total_h) + int(total_bb)) / total_ip) if total_ip > 0 else 1.30
        k_per_9 = (9 * int(total_k) / total_ip) if total_ip > 0 else 8.0
        
        bp_result = {
            'bullpen_era': max(0, 1 - era / 9.0),
            'bullpen_whip': max(0, 1 - whip / 2.5),
            'bullpen_k_rate': min(k_per_9 / 15.0, 1.0),
        }
        
        self._bullpen_cache[cache_key] = bp_result
        return self._apply_prefix(bp_result, prefix)
    
    @staticmethod
    def _apply_prefix(features: Dict[str, float], prefix: str) -> Dict[str, float]:
        """Apply a prefix (home/away) to feature names"""
        return {f'{prefix}_{k}': v for k, v in features.items()}
    
    def create_head_to_head_features(self, home_team: str, away_team: str, as_of_date: date) -> Dict[str, float]:
        """Create head-to-head matchup features (bidirectional — checks both home/away combos).
        
        Uses cache keyed by (home_team, away_team, year) to reduce DB queries during training.
        Note: H2H is direction-sensitive (home vs away matters for home_advantage), so cache key includes order.
        """
        session = self.get_session()
        
        # Cache by year — H2H history doesn't change significantly within a month
        cache_key = (home_team, away_team, as_of_date.year, as_of_date.month)
        
        if cache_key in self._h2h_cache:
            return self._h2h_cache[cache_key]
        
        # Last 3 seasons of H2H games — REGULAR SEASON ONLY (Apr-Oct)
        # Spring training H2H is noise: different rosters, no strategy, ties allowed
        lookback_date = as_of_date.replace(year=as_of_date.year - 3)
        
        # Bidirectional: get ALL games between these two teams regardless of home/away
        h2h_query = text('''
            SELECT 
                COUNT(*) as total_games,
                COUNT(CASE WHEN winner_team_id = :home_team THEN 1 END) as home_team_wins,
                COUNT(CASE WHEN winner_team_id = :away_team THEN 1 END) as away_team_wins,
                AVG(CASE WHEN home_team_id = :home_team THEN home_score
                         WHEN away_team_id = :home_team THEN away_score END) as avg_home_team_score,
                AVG(CASE WHEN home_team_id = :away_team THEN home_score
                         WHEN away_team_id = :away_team THEN away_score END) as avg_away_team_score,
                COUNT(CASE WHEN home_team_id = :home_team AND winner_team_id = :home_team THEN 1 END) as home_team_wins_at_home,
                COUNT(CASE WHEN home_team_id = :home_team THEN 1 END) as home_team_games_at_home
            FROM games 
            WHERE (
                (home_team_id = :home_team AND away_team_id = :away_team)
                OR
                (home_team_id = :away_team AND away_team_id = :home_team)
            )
            AND game_date >= :lookback_date
            AND game_date <= :as_of_date
            AND EXTRACT(MONTH FROM game_date) BETWEEN 4 AND 10
        ''')
        
        result = session.execute(h2h_query, {
            'home_team': home_team,
            'away_team': away_team,
            'as_of_date': as_of_date,
            'lookback_date': lookback_date
        }).fetchone()
        
        if result and result[0] > 0:
            (total_games, home_team_wins, away_team_wins, 
             avg_home_team_score, avg_away_team_score,
             home_team_wins_at_home, home_team_games_at_home) = result
            
            # Overall win pct for today's home team across ALL matchups
            overall_win_pct = float(home_team_wins) / float(total_games) if total_games > 0 else 0.5
            
            # Home-field specific: how does today's home team do when actually AT HOME vs this opponent
            home_field_pct = (float(home_team_wins_at_home) / float(home_team_games_at_home) 
                              if home_team_games_at_home and home_team_games_at_home > 0 else 0.5)
            
            h2h_result = {
                'h2h_total_games': int(total_games),
                'h2h_home_win_pct': overall_win_pct,
                'h2h_away_win_pct': 1.0 - overall_win_pct,
                'h2h_home_advantage': max(0, home_field_pct - 0.5),
                'h2h_avg_home_score': float(avg_home_team_score or 4.5),
                'h2h_avg_away_score': float(avg_away_team_score or 4.5),
                'h2h_scoring_advantage': float(avg_home_team_score or 4.5) - float(avg_away_team_score or 4.5)
            }
        else:
            # No H2H history - use league averages
            h2h_result = {
                'h2h_total_games': 0,
                'h2h_home_win_pct': 0.54,  # League average home win rate
                'h2h_away_win_pct': 0.46,
                'h2h_home_advantage': 0.04,
                'h2h_avg_home_score': 4.5,
                'h2h_avg_away_score': 4.5,
                'h2h_scoring_advantage': 0.0
            }
        
        self._h2h_cache[cache_key] = h2h_result
        return h2h_result
    
    def create_game_features(self, home_team: str, away_team: str, game_date,
                              home_game_pk: int = None) -> Dict[str, float]:
        """Create comprehensive game features with consistent home/away naming.
        
        Args:
            home_team: Home team abbreviation
            away_team: Away team abbreviation
            game_date: Date of the game
            home_game_pk: Optional game_pk for historical games (enables exact starter lookup)
        """
        
        # Ensure game_date is a date object, not a string
        if isinstance(game_date, str):
            from datetime import datetime as dt
            game_date = dt.strptime(game_date, '%Y-%m-%d').date()
        
        logger.debug(f"Creating WORKING features for {away_team} @ {home_team} on {game_date}")
        
        features = {}
        
        # Team batting features (using generic home/away prefixes)
        home_batting = self.create_team_batting_features(home_team, game_date, prefix="home")
        away_batting = self.create_team_batting_features(away_team, game_date, prefix="away")
        features.update(home_batting)
        features.update(away_batting)
        
        # Team pitching features (using generic home/away prefixes)
        home_pitching = self.create_team_pitching_features(home_team, game_date, prefix="home")
        away_pitching = self.create_team_pitching_features(away_team, game_date, prefix="away")
        features.update(home_pitching)
        features.update(away_pitching)
        
        # Starting pitcher features (rolling form from game logs)
        home_starter = self.create_starter_features(home_team, game_date, prefix="home",
                                                     game_pk=home_game_pk)
        away_starter = self.create_starter_features(away_team, game_date, prefix="away",
                                                     game_pk=home_game_pk)
        features.update(home_starter)
        features.update(away_starter)
        
        # Bullpen features (last 14 days from game logs)
        home_bullpen = self.create_bullpen_features(home_team, game_date, prefix="home")
        away_bullpen = self.create_bullpen_features(away_team, game_date, prefix="away")
        features.update(home_bullpen)
        features.update(away_bullpen)
        
        # Transaction features (using generic home/away prefixes)
        home_transactions = self.create_transaction_features(home_team, game_date, prefix="home")
        away_transactions = self.create_transaction_features(away_team, game_date, prefix="away")
        features.update(home_transactions)
        features.update(away_transactions)
        
        # Head-to-head features (already use generic h2h_ prefix)
        h2h_features = self.create_head_to_head_features(home_team, away_team, game_date)
        features.update(h2h_features)
        
        # Comparative features (now using generic home/away names)
        features.update({
            'batting_advantage': features.get('home_ops', 0.5) - features.get('away_ops', 0.5),
            'pitching_advantage': features.get('home_era_quality', 0.5) - features.get('away_era_quality', 0.5),
            'war_advantage': features.get('home_batting_war', 0.5) - features.get('away_batting_war', 0.5),
            'roster_stability_advantage': features.get('home_roster_stability', 0.5) - features.get('away_roster_stability', 0.5),
            'starter_era_advantage': features.get('home_starter_era', 0.5) - features.get('away_starter_era', 0.5),
            'bullpen_era_advantage': features.get('home_bullpen_era', 0.5) - features.get('away_bullpen_era', 0.5),
        })
        
        return features

def test_working_features():
    """Test the working feature engineering system"""
    
    print("🚀 Testing WORKING Enhanced Feature Engineering System")
    print("="*60)
    
    engineer = WorkingFeatureEngineer()
    
    try:
        # Test with real teams and date
        test_date = date(2025, 4, 15)
        home_team = "NYY"
        away_team = "BOS"
        
        print(f"📊 Testing features for: {away_team} @ {home_team} on {test_date}")
        print()
        
        # Generate comprehensive features
        features = engineer.create_game_features(home_team, away_team, test_date)
        
        print(f"✅ Successfully generated {len(features)} features!")
        print()
        
        # Verify all features use generic home/away naming (not team-specific)
        team_specific = [k for k in features.keys() if k.startswith(('NYY_', 'BOS_', 'LAD_'))]
        if team_specific:
            print(f"❌ WARNING: Found team-specific feature names: {team_specific}")
        else:
            print(f"✅ All features use generic home/away naming!")
        
        # Categorize and display features
        home_features = [k for k in features.keys() if k.startswith('home_')]
        away_features = [k for k in features.keys() if k.startswith('away_')]
        h2h_features = [k for k in features.keys() if k.startswith('h2h_')]
        comparative_features = [k for k in features.keys() if 'advantage' in k.lower()]
        
        print(f"\n� HOME TEAM FEATURES ({len(home_features)}):")
        for feature in sorted(home_features)[:6]:
            print(f"   {feature}: {features[feature]:.3f}")
        
        print(f"\n� AWAY TEAM FEATURES ({len(away_features)}):")
        for feature in sorted(away_features)[:6]:
            print(f"   {feature}: {features[feature]:.3f}")
        
        print(f"\n🎯 HEAD-TO-HEAD FEATURES ({len(h2h_features)}):")
        for feature in sorted(h2h_features):
            print(f"   {feature}: {features[feature]:.3f}")
        
        print(f"\n⚖️ COMPARATIVE ADVANTAGES ({len(comparative_features)}):")
        for feature in sorted(comparative_features):
            print(f"   {feature}: {features[feature]:+.3f}")
        
        print(f"\n📈 Feature Summary:")
        print(f"   • Home features: {len(home_features)}")
        print(f"   • Away features: {len(away_features)}")
        print(f"   • Head-to-head features: {len(h2h_features)}")
        print(f"   • Comparative features: {len(comparative_features)}")
        print(f"   • TOTAL: {len(features)} features")
        
        # Test with a DIFFERENT matchup to verify feature names are identical
        print(f"\n🔄 Testing second matchup (LAD @ HOU) to verify consistent naming...")
        features2 = engineer.create_game_features("HOU", "LAD", test_date)
        
        if set(features.keys()) == set(features2.keys()):
            print(f"   ✅ Feature names are IDENTICAL across matchups! ({len(features2)} features)")
        else:
            diff = set(features.keys()).symmetric_difference(set(features2.keys()))
            print(f"   ❌ Feature names differ! Differences: {diff}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        engineer.close_session()

if __name__ == "__main__":
    test_working_features()
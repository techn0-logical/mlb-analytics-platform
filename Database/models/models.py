"""
MLB Betting Analytics Database Models
Professional SQLAlchemy models for comprehensive baseball analytics and betting intelligence.

This module contains all database models organized by functional area:
- Base models and mixins for common functionality
- Team and game core data models
- Advanced sabermetric and Statcast metrics
- Player performance and matchup analysis
- Betting odds, market consensus, and value opportunities
- Weather conditions and environmental factors
- Pitcher-specific matchup analytics and predictions
- Trades, transactions, and injury tracking
- Daily player status and availability monitoring

Author: MLB Analytics Team
Created: September 2025
Updated: October 2025
"""

# Core SQLAlchemy imports
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import (
    Column, String, Integer, BigInteger, Date, DateTime, DECIMAL, Numeric,
    ForeignKey, UniqueConstraint, Boolean, Text, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, declared_attr

# Import the Base from database config
from ..config.database import Base


# =============================================================================
# BASE MODEL CLASSES AND MIXINS
# =============================================================================

class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to models"""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=func.current_timestamp(), nullable=False)
    
    @declared_attr
    def updated_at(cls):
        return Column(DateTime, default=func.current_timestamp(), 
                     onupdate=func.current_timestamp(), nullable=True)


class AuditMixin:
    """Mixin to add audit fields for tracking changes"""
    
    @declared_attr
    def changed_by(cls):
        return Column(String(100), nullable=True, default='system')
    
    @declared_attr
    def changed_at(cls):
        return Column(DateTime, default=func.current_timestamp(), nullable=False)


class BaseModel(Base, TimestampMixin):
    """Abstract base model with common functionality for all database models"""
    
    __abstract__ = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary with proper serialization"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            # Handle datetime and date serialization
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            elif hasattr(value, 'isoformat'):  # This covers date objects too
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model instance from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def __repr__(self) -> str:
        """String representation of model"""
        class_name = self.__class__.__name__
        primary_key = getattr(self, self.__mapper__.primary_key[0].name, 'unknown')
        return f"<{class_name}(id={primary_key})>"


# =============================================================================
# CORE GAME AND TEAM MODELS
# =============================================================================

class Team(BaseModel):
    """MLB Teams lookup table with stadium and location information"""
    __tablename__ = 'teams'
    
    # Primary key
    team_id = Column(String(3), primary_key=True)  # 'NYY', 'LAD', 'AZ'
    
    # Team information
    team_name = Column(String(50), nullable=False)  # 'New York Yankees'
    city = Column(String(50), nullable=False)
    stadium_name = Column(String(100), nullable=False)
    
    # Location for weather API calls
    latitude = Column(DECIMAL(10, 8), nullable=False)
    longitude = Column(DECIMAL(11, 8), nullable=False)
    
    # Relationships
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
    team_stats = relationship("TeamStats", back_populates="team")
    betting_odds_home = relationship("BettingOdds", foreign_keys="BettingOdds.home_team_id", back_populates="home_team")
    betting_odds_away = relationship("BettingOdds", foreign_keys="BettingOdds.away_team_id", back_populates="away_team")
    
    # Trades and injuries relationships
    transactions_from = relationship("MLBTransaction", foreign_keys="MLBTransaction.from_team_id", back_populates="from_team")
    transactions_to = relationship("MLBTransaction", foreign_keys="MLBTransaction.to_team_id", back_populates="to_team")
    player_history = relationship("PlayerTeamHistory", foreign_keys="PlayerTeamHistory.team_id", back_populates="team")
    player_injuries = relationship("PlayerInjury", foreign_keys="PlayerInjury.team_id", back_populates="team")
    daily_statuses = relationship("DailyPlayerStatus", foreign_keys="DailyPlayerStatus.team_id", back_populates="team")
    
    def __repr__(self):
        return f"<Team(id={self.team_id}, name={self.team_name})>"


class Game(BaseModel):
    """MLB Games from PyBaseball statcast data with quality control"""
    __tablename__ = 'games'
    
    # Primary key (MLB game ID)
    game_pk = Column(BigInteger, primary_key=True)
    
    # Game details
    game_date = Column(Date, nullable=False)
    home_score = Column(Integer)
    away_score = Column(Integer)
    game_status = Column(String(20), default='scheduled')
    
    # Data quality flag - excludes games from ML training/testing
    data_quality_flag = Column(String(50), nullable=True, 
                              comment='Data quality issues: incomplete, suspended, postponed, etc.')
    
    # Foreign keys
    home_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    away_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    winner_team_id = Column(String(3), ForeignKey('teams.team_id'))
    
    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    winner_team = relationship("Team", foreign_keys=[winner_team_id])
    pitches = relationship("Pitch", back_populates="game", cascade="all, delete-orphan")
    weather_conditions = relationship("WeatherConditions", back_populates="game", uselist=False)
    betting_odds = relationship("BettingOdds", back_populates="game")
    market_consensus = relationship("MarketConsensus", back_populates="game", uselist=False)
    value_opportunities = relationship("ValueOpportunity", back_populates="game")
    predictions = relationship("GamePrediction", back_populates="game")
    
    def __repr__(self):
        return f"<Game(pk={self.game_pk}, {self.away_team_id}@{self.home_team_id}, {self.game_date})>"
    
    def is_valid_for_ml(self) -> bool:
        """Check if game is valid for machine learning training/testing"""
        return (
            self.data_quality_flag is None and
            self.game_status == 'completed' and
            self.home_score is not None and
            self.away_score is not None and
            self.winner_team_id is not None and
            self.home_score != self.away_score  # No ties in MLB
        )
    
    def get_data_quality_issues(self) -> list:
        """Return list of data quality issues with this game"""
        issues = []
        
        if self.data_quality_flag:
            issues.append(f"Flagged: {self.data_quality_flag}")
        
        if self.game_status != 'completed':
            issues.append(f"Status: {self.game_status}")
            
        if self.home_score is None or self.away_score is None:
            issues.append("Missing scores")
            
        if self.winner_team_id is None and self.game_status == 'completed':
            issues.append("Missing winner")
            
        if (self.home_score is not None and self.away_score is not None and 
            self.home_score == self.away_score):
            issues.append("Tied game (impossible in MLB)")
            
        return issues


class Pitch(BaseModel):
    """Individual pitch data from statcast (high volume table)"""
    __tablename__ = 'pitches'
    
    # Primary key (auto-increment)
    pitch_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key to game
    game_pk = Column(BigInteger, ForeignKey('games.game_pk'), nullable=False)
    
    # Player IDs
    pitcher_id = Column(BigInteger, nullable=False)
    batter_id = Column(BigInteger, nullable=False)
    
    # Pitch details
    inning = Column(Integer, nullable=False)
    pitch_type = Column(String(5))  # 'FF', 'SL', 'CU'
    release_speed = Column(DECIMAL(4, 1))  # MPH
    events = Column(String(50))  # 'single', 'home_run', 'strikeout'
    description = Column(String(50))  # 'ball', 'called_strike', 'foul'
    
    # Score at time of pitch
    home_score = Column(Integer, nullable=False, default=0)
    away_score = Column(Integer, nullable=False, default=0)
    
    # Relationship
    game = relationship("Game", back_populates="pitches")
    
    def __repr__(self):
        return f"<Pitch(id={self.pitch_id}, game={self.game_pk}, type={self.pitch_type})>"


class TeamStats(BaseModel):
    """Season performance metrics for teams"""
    __tablename__ = 'team_stats'
    
    # Primary key (auto-increment)
    stat_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key to team
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    
    # Season and games
    season = Column(Integer, nullable=False)
    games_played = Column(Integer, default=0)
    
    # Performance metrics
    runs_scored = Column(Integer, default=0)
    runs_allowed = Column(Integer, default=0)
    batting_avg = Column(DECIMAL(4, 3))  # .000 to 1.000
    era = Column(DECIMAL(4, 2))  # Earned Run Average
    ops = Column(DECIMAL(4, 3))  # On-base Plus Slugging
    whip = Column(DECIMAL(4, 2))  # Walks + Hits per Inning Pitched
    
    # Relationship
    team = relationship("Team", back_populates="team_stats")
    
    # Unique constraint
    __table_args__ = (UniqueConstraint('team_id', 'season', name='uq_team_season'),)
    
    def __repr__(self):
        return f"<TeamStats(team={self.team_id}, season={self.season}, games={self.games_played})>"


# =============================================================================
# WEATHER CONDITIONS MODEL
# =============================================================================

class WeatherConditions(BaseModel):
    """Weather conditions for games from OpenWeatherMap API"""
    __tablename__ = 'weather_conditions'
    
    # Primary key (auto-increment)
    weather_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key to game (one-to-one relationship)
    game_pk = Column(BigInteger, ForeignKey('games.game_pk'), nullable=False, unique=True)
    
    # Game timing
    game_time = Column(DateTime, nullable=False)  # Game start time
    
    # Weather measurements
    temperature = Column(DECIMAL(4, 1))  # Fahrenheit
    humidity = Column(Integer)  # Percentage (0-100)
    wind_speed = Column(DECIMAL(4, 1))  # MPH
    wind_direction = Column(String(3))  # 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'
    conditions = Column(String(50))  # 'Clear', 'Cloudy', 'Rain', etc.
    pressure = Column(DECIMAL(6, 2))  # Barometric pressure (up to 9999.99 hPa)
    
    # Relationship
    game = relationship("Game", back_populates="weather_conditions")
    
    def __repr__(self):
        return f"<WeatherConditions(game={self.game_pk}, temp={self.temperature}°F, {self.conditions})>"
    
    def is_favorable_for_offense(self) -> bool:
        """
        Determine if weather conditions favor offensive play
        Warm, dry conditions with tailwinds typically favor hitters
        """
        if not all([self.temperature, self.humidity, self.wind_speed]):
            return None
            
        # Favorable conditions: warm (75-85°F), low humidity (<60%), moderate wind
        temp_favorable = 75 <= float(self.temperature) <= 85
        humidity_favorable = self.humidity < 60
        wind_favorable = self.wind_speed < 15  # Not too windy
        
        return temp_favorable and humidity_favorable and wind_favorable
    
    def get_wind_factor(self) -> str:
        """Categorize wind impact on game"""
        if not self.wind_speed:
            return "unknown"
            
        speed = float(self.wind_speed)
        if speed < 5:
            return "calm"
        elif speed < 15:
            return "moderate"
        elif speed < 25:
            return "strong"
        else:
            return "extreme"


# =============================================================================
# ADVANCED TEAM METRICS MODELS
# =============================================================================

class AdvancedTeamPitchingMetrics(BaseModel):
    """Advanced pitching metrics from FanGraphs/PyBaseball with Statcast integration"""
    __tablename__ = 'advanced_team_pitching_metrics'
    
    # Primary key
    metric_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key and identifiers
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    as_of_date = Column(Date, nullable=False)
    
    # Traditional stats
    era = Column(DECIMAL(4, 2))
    whip = Column(DECIMAL(4, 2))
    
    # Advanced sabermetric stats
    fip = Column(DECIMAL(4, 2))                    # Fielding Independent Pitching
    xfip = Column(DECIMAL(4, 2))                   # Expected FIP
    siera = Column(DECIMAL(4, 2))                  # Skill-Interactive ERA
    k_percent = Column(DECIMAL(5, 2))              # Strikeout percentage
    bb_percent = Column(DECIMAL(5, 2))             # Walk percentage
    k_bb_percent = Column(DECIMAL(5, 2))           # K-BB percentage
    hr_9 = Column(DECIMAL(4, 2))                   # Home runs per 9 innings
    
    # Advanced metrics (100 = league average)
    stuff_plus = Column(Integer)                   # Stuff+ rating
    location_plus = Column(Integer)                # Location+ rating
    pitching_plus = Column(Integer)                # Overall Pitching+ rating
    era_minus = Column(Integer)                    # ERA- (lower is better)
    fip_minus = Column(Integer)                    # FIP- (lower is better)
    
    # Statcast aggregates (against this team's pitching)
    avg_exit_velocity_against = Column(DECIMAL(4, 1))     # Average exit velocity allowed
    hard_hit_percent_against = Column(DECIMAL(5, 2))      # Hard hit rate allowed
    barrel_percent_against = Column(DECIMAL(5, 2))        # Barrel rate allowed
    avg_launch_angle_against = Column(DECIMAL(4, 1))      # Average launch angle allowed
    
    # Metadata
    games_analyzed = Column(Integer)
    data_quality_score = Column(DECIMAL(3, 2))    # 0.0 to 1.0 quality score
    
    # Relationships
    team = relationship("Team", backref="advanced_pitching_metrics")
    composite_metrics = relationship("CompositeTeamMetrics", back_populates="pitching_metrics")
    
    # Unique constraint
    __table_args__ = (UniqueConstraint('team_id', 'season', 'as_of_date', name='uq_team_pitching_date'),)
    
    def __repr__(self):
        return f"<AdvancedPitchingMetrics(team={self.team_id}, season={self.season}, fip={self.fip})>"


class AdvancedTeamBattingMetrics(BaseModel):
    """Advanced batting metrics including wOBA, wRC+, and comprehensive Statcast data"""
    __tablename__ = 'advanced_team_batting_metrics'
    
    # Primary key
    metric_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key and identifiers
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    as_of_date = Column(Date, nullable=False)
    
    # Traditional stats
    avg = Column(DECIMAL(4, 3))                    # Batting average
    obp = Column(DECIMAL(4, 3))                    # On-base percentage
    slg = Column(DECIMAL(4, 3))                    # Slugging percentage
    ops = Column(DECIMAL(4, 3))                    # OPS
    
    # Advanced sabermetric stats
    woba = Column(DECIMAL(4, 3))                   # Weighted On-Base Average
    wrc_plus = Column(Integer)                     # Weighted Runs Created Plus (100 = average)
    iso = Column(DECIMAL(4, 3))                    # Isolated Power (SLG - AVG)
    babip = Column(DECIMAL(4, 3))                  # Batting Average on Balls in Play
    bb_percent = Column(DECIMAL(5, 2))             # Walk percentage
    k_percent = Column(DECIMAL(5, 2))              # Strikeout percentage
    
    # Statcast metrics
    avg_exit_velocity = Column(DECIMAL(4, 1))      # Average exit velocity
    hard_hit_percent = Column(DECIMAL(5, 2))       # Hard hit percentage (95+ mph)
    barrel_percent = Column(DECIMAL(5, 2))         # Barrel percentage
    avg_launch_angle = Column(DECIMAL(4, 1))       # Average launch angle
    max_exit_velocity = Column(DECIMAL(4, 1))      # Maximum exit velocity
    
    # Expected stats (based on Statcast data)
    xba = Column(DECIMAL(4, 3))                    # Expected batting average
    xslg = Column(DECIMAL(4, 3))                   # Expected slugging
    xwoba = Column(DECIMAL(4, 3))                  # Expected wOBA
    
    # Metadata
    games_analyzed = Column(Integer)
    batted_balls_analyzed = Column(Integer)        # Number of batted balls in Statcast data
    data_quality_score = Column(DECIMAL(3, 2))    # 0.0 to 1.0 quality score
    
    # Relationships
    team = relationship("Team", backref="advanced_batting_metrics")
    composite_metrics = relationship("CompositeTeamMetrics", back_populates="batting_metrics")
    
    # Unique constraint
    __table_args__ = (UniqueConstraint('team_id', 'season', 'as_of_date', name='uq_team_batting_date'),)
    
    def __repr__(self):
        return f"<AdvancedBattingMetrics(team={self.team_id}, season={self.season}, woba={self.woba})>"


class CompositeTeamMetrics(BaseModel):
    """Composite team metrics derived from pitching + batting data for betting analysis"""
    __tablename__ = 'composite_team_metrics'
    
    # Primary key
    composite_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key and identifiers
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    as_of_date = Column(Date, nullable=False)
    
    # Reference to component metrics
    pitching_metric_id = Column(BigInteger, ForeignKey('advanced_team_pitching_metrics.metric_id'))
    batting_metric_id = Column(BigInteger, ForeignKey('advanced_team_batting_metrics.metric_id'))
    
    # Derived composite scores (0-10 scale)
    run_prevention_score = Column(DECIMAL(4, 2))   # Pitching effectiveness score
    run_creation_score = Column(DECIMAL(4, 2))     # Offensive effectiveness score
    overall_team_rating = Column(DECIMAL(4, 2))    # Combined team rating
    
    # Specialized ratings (0-10 scale)
    power_rating = Column(DECIMAL(4, 2))           # Exit velocity + barrel rate
    contact_quality = Column(DECIMAL(4, 2))        # Hard hit % + contact skills
    pitching_quality = Column(DECIMAL(4, 2))       # Stuff + command + results
    
    # Market performance indicators
    expectation_differential = Column(DECIMAL(5, 2)) # Actual vs expected performance gap
    clutch_performance = Column(DECIMAL(4, 2))       # Performance in high-leverage situations
    
    # Metadata
    calculation_method = Column(String(50))         # Method used for calculations
    confidence_score = Column(DECIMAL(3, 2))       # Confidence in these metrics (0-1)
    
    # Relationships
    team = relationship("Team", backref="composite_metrics")
    pitching_metrics = relationship("AdvancedTeamPitchingMetrics", back_populates="composite_metrics")
    batting_metrics = relationship("AdvancedTeamBattingMetrics", back_populates="composite_metrics")
    
    # Unique constraint
    __table_args__ = (UniqueConstraint('team_id', 'season', 'as_of_date', name='uq_team_composite_date'),)
    
    def __repr__(self):
        return f"<CompositeTeamMetrics(team={self.team_id}, season={self.season}, rating={self.overall_team_rating})>"


class TeamStatcastAggregates(BaseModel):
    """Aggregated Statcast data by team and date range for trend analysis"""
    __tablename__ = 'team_statcast_aggregates'
    
    # Primary key
    aggregate_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key and identifiers
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    date_range_start = Column(Date, nullable=False)
    date_range_end = Column(Date, nullable=False)
    
    # Offensive Statcast metrics
    avg_exit_velocity = Column(DECIMAL(4, 1))
    max_exit_velocity = Column(DECIMAL(4, 1))
    avg_launch_angle = Column(DECIMAL(4, 1))
    hard_hit_count = Column(Integer)
    total_batted_balls = Column(Integer)
    hard_hit_percentage = Column(DECIMAL(5, 2))
    barrel_count = Column(Integer)
    barrel_percentage = Column(DECIMAL(5, 2))
    
    # Expected performance
    expected_ba = Column(DECIMAL(4, 3))
    expected_slg = Column(DECIMAL(4, 3))
    expected_woba = Column(DECIMAL(4, 3))
    
    # Pitching Statcast metrics (when this team is pitching)
    opp_avg_exit_velocity = Column(DECIMAL(4, 1))
    opp_hard_hit_percentage = Column(DECIMAL(5, 2))
    opp_barrel_percentage = Column(DECIMAL(5, 2))
    
    # Metadata
    games_included = Column(Integer)
    pitches_analyzed = Column(Integer)
    batted_balls_analyzed = Column(Integer)
    
    # Relationships
    team = relationship("Team", backref="statcast_aggregates")
    
    # Unique constraint
    __table_args__ = (UniqueConstraint('team_id', 'season', 'date_range_start', 'date_range_end', 
                                      name='uq_team_statcast_range'),)
    
    def __repr__(self):
        return f"<TeamStatcastAggregates(team={self.team_id}, {self.date_range_start} to {self.date_range_end})>"


class TeamPerformanceTrends(BaseModel):
    """Team performance trends and momentum indicators for betting insights"""
    __tablename__ = 'team_performance_trends'
    
    # Primary key
    trend_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key and identifiers
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    as_of_date = Column(Date, nullable=False)
    
    # Recent performance windows
    last_5_games_wl_pct = Column(DECIMAL(4, 3))    # Last 5 games win %
    last_10_games_wl_pct = Column(DECIMAL(4, 3))   # Last 10 games win %
    last_20_games_wl_pct = Column(DECIMAL(4, 3))   # Last 20 games win %
    
    # Trend indicators
    run_differential_trend = Column(DECIMAL(5, 2)) # Runs/game trend (positive = improving)
    pitching_trend = Column(DECIMAL(5, 2))         # ERA trend
    offensive_trend = Column(DECIMAL(5, 2))        # wOBA trend
    
    # Situational performance
    home_wl_pct = Column(DECIMAL(4, 3))
    away_wl_pct = Column(DECIMAL(4, 3))
    vs_above_500_pct = Column(DECIMAL(4, 3))       # vs teams with winning record
    vs_division_pct = Column(DECIMAL(4, 3))        # vs division opponents
    
    # Rest and fatigue indicators
    avg_rest_days = Column(DECIMAL(3, 1))
    back_to_back_record = Column(String(10))       # "3-2" format
    travel_games_record = Column(String(10))       # Record in games after travel
    
    # Momentum indicators
    current_streak = Column(Integer)               # Current win/loss streak (+ = wins, - = losses)
    longest_win_streak = Column(Integer)
    longest_loss_streak = Column(Integer)
    
    # Relationships
    team = relationship("Team", backref="performance_trends")
    
    # Unique constraint
    __table_args__ = (UniqueConstraint('team_id', 'season', 'as_of_date', name='uq_team_trends_date'),)
    
    def __repr__(self):
        return f"<TeamPerformanceTrends(team={self.team_id}, season={self.season}, streak={self.current_streak})>"


# =============================================================================
# BETTING AND MARKET ANALYSIS MODELS
# =============================================================================

class BettingOdds(BaseModel):
    """Enhanced betting odds from The Odds API for MLB with comprehensive utility methods"""
    __tablename__ = 'betting_odds'
    
    # Primary key (auto-increment)
    odds_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key to game
    game_pk = Column(BigInteger, ForeignKey('games.game_pk'), nullable=False)
    
    # Sportsbook information (DraftKings, FanDuel, BetMGM)
    sportsbook = Column(String(50), nullable=False)
    sportsbook_key = Column(String(30), nullable=False)  # API key: 'draftkings', 'fanduel', 'betmgm'
    
    # Team references
    home_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    away_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    
    # === MONEYLINE (h2h market) ===
    home_moneyline = Column(Integer)  # e.g., -150 (bet 150 to win 100)
    away_moneyline = Column(Integer)  # e.g., +130 (bet 100 to win 130)
    
    # === RUN LINE (spreads market) ===
    home_spread_line = Column(Numeric(3, 1))    # Usually +1.5
    home_spread_odds = Column(Integer)          # Odds for home +1.5
    away_spread_line = Column(Numeric(3, 1))    # Usually -1.5
    away_spread_odds = Column(Integer)          # Odds for away -1.5
    
    # === TOTALS (over/under market) ===
    total_line = Column(Numeric(4, 1))          # e.g., 8.5 runs
    over_odds = Column(Integer)                 # Odds for Over 8.5
    under_odds = Column(Integer)                # Odds for Under 8.5
    
    # === METADATA ===
    odds_timestamp = Column(DateTime, nullable=False)    # When odds were captured
    sportsbook_last_update = Column(DateTime)           # When sportsbook last updated
    market_status = Column(String(20), default='pre_game')  # 'pre_game', 'live', 'closed'
    
    # Relationships
    game = relationship("Game", back_populates="betting_odds")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="betting_odds_home")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="betting_odds_away")
    
    # Unique constraint (one record per game/sportsbook/timestamp combination)
    __table_args__ = (
        UniqueConstraint('game_pk', 'sportsbook_key', 'odds_timestamp', 
                        name='uq_game_sportsbook_time'),
    )
    
    def __repr__(self):
        return (f"<BettingOdds(game={self.game_pk}, {self.sportsbook}, "
                f"ML={self.home_moneyline}/{self.away_moneyline})>")
    
    def get_moneyline_implied_probability(self, team: str = 'home') -> float:
        """Convert moneyline odds to implied probability"""
        odds = self.home_moneyline if team == 'home' else self.away_moneyline
        if odds is None:
            return None
        return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)
    
    def calculate_moneyline_edge(self, true_probability: float, team: str = 'home') -> float:
        """Calculate betting edge for moneyline (expected value)"""
        market_prob = self.get_moneyline_implied_probability(team)
        if not all([market_prob, true_probability]):
            return None
        
        odds = self.home_moneyline if team == 'home' else self.away_moneyline
        if odds > 0:
            profit = odds
        else:
            profit = 100 / (abs(odds) / 100)
            
        expected_value = (true_probability * profit) - ((1 - true_probability) * 100)
        return expected_value


class MarketConsensus(BaseModel):
    """Consensus odds calculated from multiple sportsbooks for market-wide betting sentiment"""
    __tablename__ = 'market_consensus'
    
    # Primary key
    consensus_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key to game
    game_pk = Column(BigInteger, ForeignKey('games.game_pk'), nullable=False)
    
    # === CONSENSUS MONEYLINE ===
    consensus_home_ml = Column(Integer)                 # Average home moneyline
    consensus_away_ml = Column(Integer)                 # Average away moneyline
    consensus_home_prob = Column(Numeric(5, 4))         # Market home win probability
    consensus_away_prob = Column(Numeric(5, 4))         # Market away win probability
    
    # === CONSENSUS SPREAD ===
    consensus_spread_line = Column(Numeric(3, 1))       # Most common spread
    consensus_home_spread_odds = Column(Integer)        # Average home spread odds
    consensus_away_spread_odds = Column(Integer)        # Average away spread odds
    
    # === CONSENSUS TOTALS ===
    consensus_total_line = Column(Numeric(4, 1))        # Most common total
    consensus_over_odds = Column(Integer)               # Average over odds
    consensus_under_odds = Column(Integer)              # Average under odds
    
    # === MARKET INTELLIGENCE ===
    bookmaker_count = Column(Integer, nullable=False)   # How many books averaged
    line_movement_direction = Column(String(10))        # 'home', 'away', 'stable'
    steam_detected = Column(Boolean, default=False)     # Sharp money indicator
    
    # Timing
    analysis_timestamp = Column(DateTime, nullable=False)
    
    # Relationships
    game = relationship("Game", back_populates="market_consensus")
    
    def __repr__(self):
        return (f"<MarketConsensus(game={self.game_pk}, books={self.bookmaker_count}, "
                f"ML={self.consensus_home_ml}/{self.consensus_away_ml})>")


class ValueOpportunity(BaseModel):
    """Identified betting value opportunities with Kelly criterion and grading"""
    __tablename__ = 'value_opportunities'
    
    # Primary key
    opportunity_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key to game
    game_pk = Column(BigInteger, ForeignKey('games.game_pk'), nullable=False)
    
    # === OPPORTUNITY DETAILS ===
    opportunity_type = Column(String(20), nullable=False)  # 'moneyline', 'spread', 'total'
    bet_side = Column(String(20), nullable=False)         # 'home', 'away', 'over', 'under'
    
    # === MODEL VS MARKET ===
    model_probability = Column(Numeric(5, 4), nullable=False)    # Your model's probability
    market_probability = Column(Numeric(5, 4), nullable=False)   # Market consensus probability
    edge_percentage = Column(Numeric(6, 2), nullable=False)      # Model edge over market
    
    # === BEST BOOK TO BET ===
    recommended_sportsbook = Column(String(50), nullable=False)  # Which book to bet
    recommended_sportsbook_key = Column(String(30), nullable=False)  # API key
    recommended_odds = Column(Integer, nullable=False)           # Odds at that book
    expected_value = Column(Numeric(8, 2))                       # Expected value in dollars (for $100 bet)
    kelly_bet_percentage = Column(Numeric(5, 2))                 # Optimal bet size %
    
    # === CONFIDENCE GRADING ===
    model_confidence = Column(String(10), nullable=False)        # 'high', 'medium', 'low'
    opportunity_grade = Column(String(5))                        # 'A+', 'A', 'B+', 'B', 'C'
    
    # Timing
    expires_at = Column(DateTime)  # When game starts (opportunity expires)
    
    # Relationships
    game = relationship("Game", back_populates="value_opportunities")
    
    def __repr__(self):
        return (f"<ValueOpportunity({self.opportunity_type} {self.bet_side}, "
                f"edge={self.edge_percentage}%, grade={self.opportunity_grade})>")
    
    def is_active(self) -> bool:
        """Check if opportunity is still active (game hasn't started)"""
        from datetime import datetime
        return self.expires_at is None or datetime.now() < self.expires_at


# =============================================================================
# TRADES AND INJURIES MODELS
# =============================================================================

class MLBTransaction(BaseModel):
    """MLB transactions including trades, signings, releases, and other roster moves"""
    __tablename__ = 'mlb_transactions'
    
    # Primary key
    transaction_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Transaction details
    transaction_date = Column(Date, nullable=False)
    transaction_type = Column(String(20), nullable=False)  # 'trade', 'signing', 'release', 'waiver', 'option'
    description = Column(Text, nullable=False)  # Full transaction description
    
    # Primary player involved
    player_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    from_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=True)
    to_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=True)
    
    # Trade specifics
    is_multi_player_trade = Column(Boolean, default=False)
    trade_group_id = Column(String(50), nullable=True)  # Groups related transactions
    cash_considerations = Column(DECIMAL(12, 2), nullable=True)  # Dollar amount
    draft_picks_involved = Column(Text, nullable=True)  # JSON array of draft pick details
    
    # Contract details
    contract_years = Column(Integer, nullable=True)
    contract_value = Column(DECIMAL(12, 2), nullable=True)
    guaranteed_money = Column(DECIMAL(12, 2), nullable=True)
    
    # Data sources and validation
    source = Column(String(50), nullable=False, default='mlb_api')  # 'mlb_api', 'espn', 'manual'
    verified = Column(Boolean, default=False)
    verification_date = Column(Date, nullable=True)
    
    # Season context
    season = Column(Integer, nullable=False)
    is_deadline_trade = Column(Boolean, default=False)  # Trade deadline transactions
    is_offseason = Column(Boolean, default=False)
    
    # Relationships
    player = relationship("Player", foreign_keys=[player_id])
    from_team = relationship("Team", foreign_keys=[from_team_id])
    to_team = relationship("Team", foreign_keys=[to_team_id])
    
    def __repr__(self):
        return f"<MLBTransaction({self.transaction_type}: {self.player_id} {self.from_team_id}->{self.to_team_id}, {self.transaction_date})>"
    
    @property
    def is_trade(self) -> bool:
        """Check if this transaction is a trade"""
        return self.transaction_type == 'trade'
    
    @property
    def involves_money(self) -> bool:
        """Check if transaction involves cash considerations"""
        return self.cash_considerations is not None and self.cash_considerations > 0


class PlayerTeamHistory(BaseModel):
    """Complete history of player team affiliations and roster status"""
    __tablename__ = 'player_team_history'
    
    # Primary key
    history_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Player and team
    player_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    
    # Time period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # NULL for current team
    season = Column(Integer, nullable=False)
    
    # Roster details
    roster_status = Column(String(20), nullable=False)  # 'active', 'dl', 'minors', 'suspended'
    jersey_number = Column(Integer, nullable=True)
    primary_position = Column(String(5), nullable=True)
    
    # Transaction that caused this assignment
    transaction_id = Column(BigInteger, ForeignKey('mlb_transactions.transaction_id'), nullable=True)
    acquisition_type = Column(String(20), nullable=False)  # 'trade', 'signing', 'draft', 'claim'
    
    # Performance indicators during this stint
    games_played = Column(Integer, default=0)
    games_started = Column(Integer, default=0)
    days_on_roster = Column(Integer, nullable=True)
    
    # Salary information (if available)
    annual_salary = Column(DECIMAL(12, 2), nullable=True)
    prorated_salary = Column(DECIMAL(12, 2), nullable=True)
    
    # Status flags
    is_current = Column(Boolean, default=False)
    is_active_roster = Column(Boolean, default=True)
    
    # Relationships
    player = relationship("Player", foreign_keys=[player_id])
    team = relationship("Team", foreign_keys=[team_id])
    transaction = relationship("MLBTransaction", foreign_keys=[transaction_id])
    
    # Unique constraint to prevent overlapping periods
    __table_args__ = (
        UniqueConstraint('player_id', 'team_id', 'start_date', name='uq_player_team_start'),
    )
    
    def __repr__(self):
        return f"<PlayerTeamHistory({self.player_id} with {self.team_id}: {self.start_date} to {self.end_date or 'current'})>"
    
    @property
    def days_with_team(self) -> int:
        """Calculate days with team (current date if still active)"""
        end = self.end_date or datetime.now().date()
        return (end - self.start_date).days
    
    def is_active_period(self) -> bool:
        """Check if this is the player's current team assignment"""
        return self.end_date is None and self.is_current


class PlayerInjury(BaseModel):
    """Player injury records and recovery tracking"""
    __tablename__ = 'player_injuries'
    
    # Primary key
    injury_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Player and team context
    player_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Injury details
    injury_date = Column(Date, nullable=False)
    injury_type = Column(String(50), nullable=False)  # 'shoulder', 'elbow', 'hamstring', etc.
    injury_severity = Column(String(20), nullable=False)  # 'minor', 'moderate', 'severe', 'season_ending'
    body_part = Column(String(30), nullable=False)  # 'right_shoulder', 'left_knee', etc.
    injury_description = Column(Text, nullable=True)  # Detailed description
    
    # Timeline
    expected_return_date = Column(Date, nullable=True)
    actual_return_date = Column(Date, nullable=True)
    days_missed = Column(Integer, nullable=True)
    games_missed = Column(Integer, default=0)
    
    # IL (Injured List) details
    il_designation = Column(String(10), nullable=True)  # '10-day', '15-day', '60-day'
    il_start_date = Column(Date, nullable=True)
    il_end_date = Column(Date, nullable=True)
    
    # Recovery tracking
    recovery_status = Column(String(20), default='injured')  # 'injured', 'rehabbing', 'cleared', 'returned'
    rehab_assignment = Column(Boolean, default=False)
    surgery_required = Column(Boolean, default=False)
    surgery_date = Column(Date, nullable=True)
    
    # Performance impact flags
    affects_batting = Column(Boolean, default=False)
    affects_fielding = Column(Boolean, default=False)
    affects_running = Column(Boolean, default=False)
    affects_throwing = Column(Boolean, default=False)
    
    # Data sources
    source = Column(String(50), nullable=False, default='mlb_api')
    last_updated = Column(DateTime, default=func.current_timestamp())
    
    # Relationships
    player = relationship("Player", foreign_keys=[player_id])
    team = relationship("Team", foreign_keys=[team_id])
    
    def __repr__(self):
        return f"<PlayerInjury({self.player_id}: {self.injury_type} on {self.injury_date}, severity={self.injury_severity})>"
    
    @property
    def is_active_injury(self) -> bool:
        """Check if injury is currently active"""
        return self.recovery_status in ['injured', 'rehabbing'] and self.actual_return_date is None
    
    @property
    def expected_days_out(self) -> int:
        """Calculate expected days out from injury"""
        if self.expected_return_date and self.injury_date:
            return (self.expected_return_date - self.injury_date).days
        return 0
    
    def impacts_position(self, position: str) -> bool:
        """Check if injury affects specific position performance"""
        position_impacts = {
            'P': self.affects_throwing,
            'C': self.affects_throwing or self.affects_fielding,
            '1B': self.affects_fielding,
            '2B': self.affects_fielding or self.affects_running,
            '3B': self.affects_fielding or self.affects_throwing,
            'SS': self.affects_fielding or self.affects_throwing or self.affects_running,
            'OF': self.affects_running or self.affects_throwing,
            'DH': self.affects_batting
        }
        return position_impacts.get(position, False)


class DailyPlayerStatus(BaseModel):
    """Daily player availability and status tracking"""
    __tablename__ = 'daily_player_status'
    
    # Primary key
    status_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Player and date
    player_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    status_date = Column(Date, nullable=False)
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    
    # Availability status
    roster_status = Column(String(20), nullable=False)  # 'active', 'il_10', 'il_15', 'il_60', 'suspended', 'bereavement'
    game_status = Column(String(20), nullable=False)  # 'available', 'questionable', 'doubtful', 'out', 'dtd'
    
    # Injury/health related
    injury_status = Column(String(20), default='healthy')  # 'healthy', 'injured', 'recovering', 'day_to_day'
    current_injury_id = Column(BigInteger, ForeignKey('player_injuries.injury_id'), nullable=True)
    
    # Performance factors
    rest_days = Column(Integer, default=0)  # Consecutive days without playing
    recent_usage = Column(String(20), nullable=True)  # 'heavy', 'normal', 'light', 'rested'
    fatigue_score = Column(DECIMAL(3, 2), nullable=True)  # 0.0 to 1.0 fatigue indicator
    
    # Probable starter info (for pitchers)
    is_probable_starter = Column(Boolean, default=False)
    start_date = Column(Date, nullable=True)
    days_rest_pitching = Column(Integer, nullable=True)
    
    # Load management
    is_load_managed = Column(Boolean, default=False)
    load_management_reason = Column(String(100), nullable=True)
    
    # Data tracking
    last_updated = Column(DateTime, default=func.current_timestamp())
    data_source = Column(String(30), default='mlb_api')
    
    # Relationships
    player = relationship("Player", foreign_keys=[player_id])
    team = relationship("Team", foreign_keys=[team_id])
    current_injury = relationship("PlayerInjury", foreign_keys=[current_injury_id])
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('player_id', 'status_date', name='uq_player_daily_status'),
    )
    
    def __repr__(self):
        return f"<DailyPlayerStatus({self.player_id} on {self.status_date}: {self.game_status})>"
    
    @property
    def is_available(self) -> bool:
        """Check if player is available to play"""
        return (self.roster_status == 'active' and 
                self.game_status in ['available', 'questionable'] and
                self.injury_status in ['healthy', 'day_to_day'])
    
    @property
    def availability_percentage(self) -> float:
        """Calculate availability percentage based on status"""
        if self.game_status == 'available' and self.injury_status == 'healthy':
            return 1.0
        elif self.game_status == 'questionable':
            return 0.5
        elif self.game_status == 'doubtful':
            return 0.2
        else:
            return 0.0


class PlayerTradeImpact(BaseModel):
    """Analysis of player performance impact from trades and team changes"""
    __tablename__ = 'player_trade_impact'
    
    # Primary key
    impact_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Player and transaction
    player_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    transaction_id = Column(BigInteger, ForeignKey('mlb_transactions.transaction_id'), nullable=False)
    
    # Time periods for comparison
    analysis_date = Column(Date, nullable=False)
    pre_trade_start = Column(Date, nullable=False)
    pre_trade_end = Column(Date, nullable=False)
    post_trade_start = Column(Date, nullable=False)
    post_trade_end = Column(Date, nullable=True)  # NULL for ongoing
    
    # Performance metrics (batting)
    pre_trade_avg = Column(DECIMAL(4, 3), nullable=True)
    post_trade_avg = Column(DECIMAL(4, 3), nullable=True)
    avg_change = Column(DECIMAL(5, 3), nullable=True)
    
    pre_trade_ops = Column(DECIMAL(4, 3), nullable=True)
    post_trade_ops = Column(DECIMAL(4, 3), nullable=True)
    ops_change = Column(DECIMAL(5, 3), nullable=True)
    
    pre_trade_wrc_plus = Column(Integer, nullable=True)
    post_trade_wrc_plus = Column(Integer, nullable=True)
    wrc_plus_change = Column(Integer, nullable=True)
    
    # Performance metrics (pitching)
    pre_trade_era = Column(DECIMAL(4, 2), nullable=True)
    post_trade_era = Column(DECIMAL(4, 2), nullable=True)
    era_change = Column(DECIMAL(5, 2), nullable=True)
    
    pre_trade_whip = Column(DECIMAL(4, 2), nullable=True)
    post_trade_whip = Column(DECIMAL(4, 2), nullable=True)
    whip_change = Column(DECIMAL(5, 2), nullable=True)
    
    pre_trade_fip = Column(DECIMAL(4, 2), nullable=True)
    post_trade_fip = Column(DECIMAL(4, 2), nullable=True)
    fip_change = Column(DECIMAL(5, 2), nullable=True)
    
    # Context factors
    games_pre_trade = Column(Integer, default=0)
    games_post_trade = Column(Integer, default=0)
    
    ballpark_factor_change = Column(DECIMAL(4, 2), nullable=True)  # Offensive environment change
    league_change = Column(Boolean, default=False)  # AL to NL or vice versa
    role_change = Column(String(50), nullable=True)  # 'starter_to_reliever', 'bench_to_starter', etc.
    
    # Impact assessment
    overall_impact_score = Column(DECIMAL(5, 2), nullable=True)  # -10 to +10 scale
    impact_category = Column(String(20), nullable=True)  # 'positive', 'negative', 'neutral', 'insufficient_data'
    confidence_level = Column(DECIMAL(3, 2), nullable=True)  # 0.0 to 1.0
    
    # Analysis metadata
    sample_size_adequate = Column(Boolean, default=False)
    analysis_notes = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=func.current_timestamp())
    
    # Relationships
    player = relationship("Player", foreign_keys=[player_id])
    transaction = relationship("MLBTransaction", foreign_keys=[transaction_id])
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('player_id', 'transaction_id', name='uq_player_transaction_impact'),
    )
    
    def __repr__(self):
        return f"<PlayerTradeImpact({self.player_id}, impact={self.overall_impact_score}, category={self.impact_category})>"
    
    @property
    def has_positive_impact(self) -> bool:
        """Check if trade had positive impact on performance"""
        return self.overall_impact_score is not None and self.overall_impact_score > 1.0
    
    @property
    def performance_change_summary(self) -> dict:
        """Get summary of key performance changes"""
        return {
            'batting': {
                'avg_change': float(self.avg_change) if self.avg_change else None,
                'ops_change': float(self.ops_change) if self.ops_change else None,
                'wrc_plus_change': self.wrc_plus_change
            },
            'pitching': {
                'era_change': float(self.era_change) if self.era_change else None,
                'whip_change': float(self.whip_change) if self.whip_change else None,
                'fip_change': float(self.fip_change) if self.fip_change else None
            }
        }

class Player(BaseModel):
    """MLB Players lookup table with comprehensive biographical and career information"""
    __tablename__ = 'players'
    
    # Primary key (MLB Statcast ID)
    player_id = Column(BigInteger, primary_key=True)
    
    # External IDs for data integration
    fangraphs_id = Column(String(10), nullable=True, unique=True, comment='FanGraphs ID (IDfg)')
    baseball_reference_id = Column(String(10), nullable=True, unique=True, comment='Baseball Reference ID')
    
    # Name information
    name_first = Column(String(50), nullable=False)
    name_last = Column(String(50), nullable=False)
    name_display = Column(String(100), nullable=False, comment='Display name: "Ronald Acuña Jr."')
    name_suffix = Column(String(10), nullable=True, comment='Jr., Sr., III, etc.')
    
    # Biographical information
    birth_date = Column(Date, nullable=True)
    birth_country = Column(String(50), nullable=True)
    birth_state = Column(String(50), nullable=True)
    birth_city = Column(String(50), nullable=True)
    
    # Physical attributes
    height_inches = Column(Integer, nullable=True, comment='Height in inches')
    weight_lbs = Column(Integer, nullable=True, comment='Weight in pounds')
    bats = Column(String(1), nullable=True, comment='L, R, or S (switch)')
    throws = Column(String(1), nullable=True, comment='L or R')
    
    # Career information
    mlb_debut_date = Column(Date, nullable=True)
    final_game_date = Column(Date, nullable=True, comment='NULL for active players')
    is_active = Column(Boolean, default=True, nullable=False)
    primary_position = Column(String(5), nullable=True, comment='C, 1B, 2B, 3B, SS, LF, CF, RF, DH, P')
    
    # Jersey information
    jersey_number = Column(Integer, nullable=True)
    current_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=True)
    
    # Relationships
    current_team = relationship("Team", foreign_keys=[current_team_id])
    batting_stats = relationship("PlayerBattingStats", back_populates="player", cascade="all, delete-orphan")
    pitching_stats = relationship("PlayerPitchingStats", back_populates="player", cascade="all, delete-orphan")
    pitcher_matchups = relationship("PlayerMatchup", foreign_keys="PlayerMatchup.pitcher_id", back_populates="pitcher")
    batter_matchups = relationship("PlayerMatchup", foreign_keys="PlayerMatchup.batter_id", back_populates="batter")
    
    # Trades and injuries relationships
    transactions = relationship("MLBTransaction", foreign_keys="MLBTransaction.player_id", back_populates="player")
    team_history = relationship("PlayerTeamHistory", foreign_keys="PlayerTeamHistory.player_id", back_populates="player")
    injuries = relationship("PlayerInjury", foreign_keys="PlayerInjury.player_id", back_populates="player")
    daily_status = relationship("DailyPlayerStatus", foreign_keys="DailyPlayerStatus.player_id", back_populates="player")
    trade_impacts = relationship("PlayerTradeImpact", foreign_keys="PlayerTradeImpact.player_id", back_populates="player")
    
    # Indexes for common queries
    __table_args__ = (
        UniqueConstraint('name_display', 'birth_date', name='unique_player_name_birth'),
    )
    
    def __repr__(self):
        return f"<Player(id={self.player_id}, name={self.name_display}, team={self.current_team_id})>"
    
    @property
    def age(self):
        """Calculate current age if birth_date is available"""
        if not self.birth_date:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))


class PlayerBattingStats(BaseModel):
    """Comprehensive player batting statistics with traditional and advanced metrics"""
    __tablename__ = 'player_batting_stats'
    
    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign keys
    player_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Basic counting stats
    games = Column(Integer, default=0)
    plate_appearances = Column(Integer, default=0)
    at_bats = Column(Integer, default=0)
    hits = Column(Integer, default=0)
    home_runs = Column(Integer, default=0)
    runs = Column(Integer, default=0)
    rbis = Column(Integer, default=0)
    walks = Column(Integer, default=0)
    strikeouts = Column(Integer, default=0)
    stolen_bases = Column(Integer, default=0)
    
    # Traditional rate stats
    batting_average = Column(DECIMAL(4, 3), nullable=True)
    on_base_percentage = Column(DECIMAL(4, 3), nullable=True)
    slugging_percentage = Column(DECIMAL(4, 3), nullable=True)
    ops = Column(DECIMAL(4, 3), nullable=True)
    
    # Advanced sabermetrics
    woba = Column(DECIMAL(4, 3), nullable=True, comment='Weighted On-Base Average')
    wrc_plus = Column(Integer, nullable=True, comment='wRC+ (100 = league average)')
    war = Column(DECIMAL(4, 1), nullable=True, comment='Wins Above Replacement')
    
    # Statcast metrics
    avg_exit_velocity = Column(DECIMAL(4, 1), nullable=True, comment='Average exit velocity (mph)')
    hard_hit_percent = Column(DECIMAL(5, 2), nullable=True, comment='Hard hit percentage (95+ mph)')
    barrel_percent = Column(DECIMAL(5, 2), nullable=True, comment='Barrel percentage')
    
    # Relationships
    player = relationship("Player", back_populates="batting_stats")
    team = relationship("Team")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'team_id', name='unique_player_season_team_batting'),
    )
    
    def __repr__(self):
        return f"<PlayerBattingStats(player_id={self.player_id}, season={self.season}, AVG={self.batting_average})>"


class PlayerPitchingStats(BaseModel):
    """Comprehensive player pitching statistics with Stuff+ and advanced metrics"""
    __tablename__ = 'player_pitching_stats'
    
    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign keys
    player_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Basic counting stats
    games = Column(Integer, default=0)
    games_started = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    innings_pitched = Column(DECIMAL(5, 1), nullable=True)
    hits_allowed = Column(Integer, default=0)
    runs_allowed = Column(Integer, default=0)
    earned_runs_allowed = Column(Integer, default=0)
    home_runs_allowed = Column(Integer, default=0)
    walks_allowed = Column(Integer, default=0)
    strikeouts = Column(Integer, default=0)
    
    # Traditional rate stats
    era = Column(DECIMAL(4, 2), nullable=True, comment='Earned Run Average')
    whip = Column(DECIMAL(4, 2), nullable=True, comment='Walks + Hits per Inning Pitched')
    
    # Advanced sabermetrics
    fip = Column(DECIMAL(4, 2), nullable=True, comment='Fielding Independent Pitching')
    xfip = Column(DECIMAL(4, 2), nullable=True, comment='Expected Fielding Independent Pitching')
    war = Column(DECIMAL(4, 1), nullable=True, comment='Wins Above Replacement')
    
    # Stuff+ metrics (Advanced pitch modeling)
    stuff_plus = Column(Integer, nullable=True, comment='Overall Stuff+ rating (100 = average)')
    location_plus = Column(Integer, nullable=True, comment='Location+ rating (100 = average)')
    pitching_plus = Column(Integer, nullable=True, comment='Combined Pitching+ rating (100 = average)')
    
    # Role information
    starter_reliever = Column(String(10), nullable=True, comment='SP, RP, CL')
    
    # Relationships
    player = relationship("Player", back_populates="pitching_stats")
    team = relationship("Team")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'team_id', name='unique_player_season_team_pitching'),
    )
    
    def __repr__(self):
        return f"<PlayerPitchingStats(player_id={self.player_id}, season={self.season}, ERA={self.era})>"


class PlayerMatchup(BaseModel):
    """Historical pitcher vs batter matchup performance with sample size assessment"""
    __tablename__ = 'player_matchups'
    
    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign keys
    pitcher_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    batter_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    
    # Overall matchup stats
    total_plate_appearances = Column(Integer, default=0)
    total_at_bats = Column(Integer, default=0)
    total_hits = Column(Integer, default=0)
    total_home_runs = Column(Integer, default=0)
    total_walks = Column(Integer, default=0)
    total_strikeouts = Column(Integer, default=0)
    
    # Calculated rates
    batting_average = Column(DECIMAL(4, 3), nullable=True)
    on_base_percentage = Column(DECIMAL(4, 3), nullable=True)
    slugging_percentage = Column(DECIMAL(4, 3), nullable=True)
    ops = Column(DECIMAL(4, 3), nullable=True)
    
    # Data quality and recency
    last_matchup_date = Column(Date, nullable=True, comment='Most recent plate appearance')
    confidence_level = Column(String(10), nullable=True, comment='high, medium, low based on sample size')
    
    # Relationships
    pitcher = relationship("Player", foreign_keys=[pitcher_id], back_populates="pitcher_matchups")
    batter = relationship("Player", foreign_keys=[batter_id], back_populates="batter_matchups")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('pitcher_id', 'batter_id', name='unique_pitcher_batter_matchup'),
    )
    
    def __repr__(self):
        return f"<PlayerMatchup(pitcher={self.pitcher_id}, batter={self.batter_id}, PA={self.total_plate_appearances})>"


class PlayerMatchupSummary(BaseModel):
    """Aggregated matchup performance summaries for quick lookups and platoon analysis"""
    __tablename__ = 'player_matchup_summaries'
    
    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign keys
    player_id = Column(BigInteger, ForeignKey('players.player_id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Aggregated performance vs different handedness
    vs_lhp_plate_appearances = Column(Integer, default=0, comment='vs Left-handed pitching')
    vs_lhp_batting_average = Column(DECIMAL(4, 3), nullable=True)
    vs_lhp_ops = Column(DECIMAL(4, 3), nullable=True)
    
    vs_rhp_plate_appearances = Column(Integer, default=0, comment='vs Right-handed pitching')
    vs_rhp_batting_average = Column(DECIMAL(4, 3), nullable=True)
    vs_rhp_ops = Column(DECIMAL(4, 3), nullable=True)
    
    # Platoon differential
    platoon_split_ops = Column(DECIMAL(4, 3), nullable=True, comment='Difference in OPS vs opposite/same handedness')
    
    # Relationships
    player = relationship("Player")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('player_id', 'season', name='unique_player_season_matchup_summary'),
    )
    
    def __repr__(self):
        return f"<PlayerMatchupSummary(player_id={self.player_id}, season={self.season})>"


# =============================================================================
# PITCHER MATCHUP AND PREDICTION MODELS
# =============================================================================

class PitcherTeamMatchup(BaseModel):
    """Historical pitcher performance vs specific teams for betting analytics"""
    __tablename__ = 'pitcher_team_matchups'
    
    # Primary key
    matchup_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign keys
    pitcher_id = Column(BigInteger, nullable=False)
    opposing_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Matchup Performance Metrics
    games_started = Column(Integer, default=0)
    innings_pitched = Column(DECIMAL(4, 1), default=0.0)
    era_vs_team = Column(DECIMAL(4, 2))
    whip_vs_team = Column(DECIMAL(4, 2))
    strikeouts_vs_team = Column(Integer, default=0)
    walks_vs_team = Column(Integer, default=0)
    hits_allowed_vs_team = Column(Integer, default=0)
    home_runs_allowed_vs_team = Column(Integer, default=0)
    
    # Advanced Metrics
    batting_avg_against = Column(DECIMAL(4, 3))
    ops_against = Column(DECIMAL(4, 3))
    quality_starts = Column(Integer, default=0)
    
    # Win/Loss Record
    wins_vs_team = Column(Integer, default=0)
    losses_vs_team = Column(Integer, default=0)
    
    # Relationships
    opposing_team = relationship("Team", foreign_keys=[opposing_team_id])
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('pitcher_id', 'opposing_team_id', 'season', 
                        name='uq_pitcher_team_season'),
    )
    
    def __repr__(self):
        return f"<PitcherTeamMatchup(pitcher={self.pitcher_id}, vs={self.opposing_team_id}, ERA={self.era_vs_team})>"
    
    def get_effectiveness_score(self) -> float:
        """Calculate pitcher effectiveness vs this team (0-100 scale)"""
        if not self.era_vs_team or not self.whip_vs_team:
            return 50.0  # Neutral if no data
        
        # Lower ERA and WHIP = higher effectiveness
        era_score = max(0, 100 - (float(self.era_vs_team) * 20))
        whip_score = max(0, 100 - (float(self.whip_vs_team) * 50))
        
        # Weight by innings pitched (more data = more reliable)
        reliability_weight = min(1.0, float(self.innings_pitched or 0) / 50.0)
        
        return ((era_score + whip_score) / 2) * reliability_weight


class BullpenTeamMatchup(BaseModel):
    """Bullpen performance vs specific teams for closer and relief analysis"""
    __tablename__ = 'bullpen_team_matchups'
    
    # Primary key
    matchup_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign keys
    team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    opposing_team_id = Column(String(3), ForeignKey('teams.team_id'), nullable=False)
    season = Column(Integer, nullable=False)
    
    # Bullpen Performance Metrics
    games_pitched = Column(Integer, default=0)
    innings_pitched = Column(DECIMAL(4, 1), default=0.0)
    era_vs_team = Column(DECIMAL(4, 2))
    whip_vs_team = Column(DECIMAL(4, 2))
    saves_vs_team = Column(Integer, default=0)
    blown_saves_vs_team = Column(Integer, default=0)
    
    # Closer-Specific Metrics
    closer_era_vs_team = Column(DECIMAL(4, 2))
    closer_saves_vs_team = Column(Integer, default=0)
    closer_blown_saves_vs_team = Column(Integer, default=0)
    closer_success_rate = Column(DECIMAL(4, 3))
    
    # Relationships
    bullpen_team = relationship("Team", foreign_keys=[team_id])
    opposing_team = relationship("Team", foreign_keys=[opposing_team_id])
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('team_id', 'opposing_team_id', 'season', 
                        name='uq_bullpen_team_season'),
    )
    
    def __repr__(self):
        return f"<BullpenTeamMatchup({self.team_id} bullpen vs {self.opposing_team_id})>"


class GamePrediction(BaseModel):
    """Store game predictions and track accuracy for model validation"""
    __tablename__ = 'game_predictions'
    
    # Primary key
    prediction_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key to game
    game_pk = Column(BigInteger, ForeignKey('games.game_pk'), nullable=False)
    
    # Prediction Details
    prediction_date = Column(Date, nullable=False)
    model_version = Column(String(50), nullable=False)
    
    # Winner Predictions
    predicted_winner = Column(String(3), ForeignKey('teams.team_id'))
    win_probability = Column(DECIMAL(4, 3))
    confidence_score = Column(DECIMAL(4, 3))
    
    # Run Total Predictions
    predicted_total_runs = Column(DECIMAL(4, 1))
    over_under_line = Column(DECIMAL(4, 1))
    over_under_prediction = Column(String(5))
    
    # Key Factors
    primary_factors = Column(Text)  # JSON string of contributing factors
    
    # Actual Results (filled in after game)
    actual_winner = Column(String(3), ForeignKey('teams.team_id'))
    actual_total_runs = Column(Integer)
    prediction_correct = Column(Integer)  # 1 = correct, 0 = incorrect, NULL = pending
    
    # Relationships
    game = relationship("Game", back_populates="predictions")
    predicted_winner_team = relationship("Team", foreign_keys=[predicted_winner])
    actual_winner_team = relationship("Team", foreign_keys=[actual_winner])
    
    def __repr__(self):
        return f"<GamePrediction(game={self.game_pk}, winner={self.predicted_winner}, prob={self.win_probability})>"


# =============================================================================
# MODEL REGISTRY AND UTILITY FUNCTIONS
# =============================================================================

# Export all models for easy importing
__all__ = [
    # Base classes
    'Base',
    'BaseModel', 
    'TimestampMixin',
    'AuditMixin',
    
    # Core game models
    'Team',
    'Game', 
    'Pitch',
    'TeamStats',
    
    # Weather models
    'WeatherConditions',
    
    # Advanced metrics models
    'AdvancedTeamPitchingMetrics',
    'AdvancedTeamBattingMetrics',
    'CompositeTeamMetrics',
    'TeamStatcastAggregates',
    'TeamPerformanceTrends',
    
    # Betting models
    'BettingOdds',
    'MarketConsensus', 
    'ValueOpportunity',
    
    # Player models
    'Player',
    'PlayerBattingStats',
    'PlayerPitchingStats',
    'PlayerMatchup',
    'PlayerMatchupSummary',
    
    # Pitcher matchup models
    'PitcherTeamMatchup',
    'BullpenTeamMatchup',
    'GamePrediction',
    
    # Trades and injuries models
    'MLBTransaction',
    'PlayerTeamHistory',
    'PlayerInjury',
    'DailyPlayerStatus',
    'PlayerTradeImpact'
]

# Model registry for dynamic access
MODEL_REGISTRY = {
    'teams': Team,
    'games': Game,
    'pitches': Pitch,
    'team_stats': TeamStats,
    'weather_conditions': WeatherConditions,
    'betting_odds': BettingOdds,
    'market_consensus': MarketConsensus,
    'value_opportunities': ValueOpportunity,
    'advanced_team_pitching_metrics': AdvancedTeamPitchingMetrics,
    'advanced_team_batting_metrics': AdvancedTeamBattingMetrics,
    'composite_team_metrics': CompositeTeamMetrics,
    'team_statcast_aggregates': TeamStatcastAggregates,
    'team_performance_trends': TeamPerformanceTrends,
    'players': Player,
    'player_batting_stats': PlayerBattingStats,
    'player_pitching_stats': PlayerPitchingStats,
    'player_matchups': PlayerMatchup,
    'player_matchup_summaries': PlayerMatchupSummary,
    'pitcher_team_matchups': PitcherTeamMatchup,
    'bullpen_team_matchups': BullpenTeamMatchup,
    'game_predictions': GamePrediction,
    'mlb_transactions': MLBTransaction,
    'player_team_history': PlayerTeamHistory,
    'player_injuries': PlayerInjury,
    'daily_player_status': DailyPlayerStatus,
    'player_trade_impact': PlayerTradeImpact
}


def get_model_by_table_name(table_name: str):
    """
    Get model class by table name
    
    Args:
        table_name: Name of the database table
        
    Returns:
        Model class or None if not found
    """
    return MODEL_REGISTRY.get(table_name)


def get_all_model_classes():
    """
    Get list of all model classes
    
    Returns:
        List of all model classes
    """
    return list(MODEL_REGISTRY.values())


def get_table_names():
    """
    Get list of all table names
    
    Returns:
        List of all table names
    """
    return list(MODEL_REGISTRY.keys())


def validate_model_registry():
    """
    Validate that all models in __all__ are in the registry
    
    Returns:
        Tuple of (missing_from_registry, missing_from_all)
    """
    all_models = set(__all__)
    registry_models = set(MODEL_REGISTRY.values())
    
    # Remove base classes from comparison
    base_classes = {'Base', 'BaseModel', 'TimestampMixin', 'AuditMixin'}
    all_models -= base_classes
    
    # Convert registry values to their names for comparison
    registry_model_names = {model.__name__ for model in registry_models}
    
    missing_from_registry = all_models - registry_model_names
    missing_from_all = registry_model_names - all_models
    
    return missing_from_registry, missing_from_all


# =============================================================================
# MODULE INITIALIZATION AND VALIDATION
# =============================================================================

# Validate model registry consistency
missing_from_registry, missing_from_all = validate_model_registry()

if missing_from_registry:
    print(f"Warning: Models in __all__ but not in registry: {missing_from_registry}")

if missing_from_all:
    print(f"Warning: Models in registry but not in __all__: {missing_from_all}")
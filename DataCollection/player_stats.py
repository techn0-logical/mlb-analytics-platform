"""
Player Statistics Collection Module
===================================

Comprehensive player statistics collection using PyBaseball and MLB Stats API.
Collects batting stats, pitching stats, daily status, and matchup data.

Features:
- Season-long batting and pitching statistics
- Daily player status and availability
- Advanced Statcast metrics integration
- Intelligent deduplication and updates
- Professional error handling and logging

Author: MLB Analytics Team
Version: 1.0.0
"""

import logging
import sys
import os
import warnings
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

try:
    from Database.config.database import DatabaseConfig
    from Database.models.models import (
        Player, PlayerBattingStats, PlayerPitchingStats,
        DailyPlayerStatus, Team, Game
    )
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text, and_
    from .utils import log_error
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root with virtual environment activated")
    sys.exit(1)

# Configure logging
logger = logging.getLogger(__name__)

# Import MLB Stats API (check different possible import paths)
MLB_API_AVAILABLE = False
mlb = None

# Try to import from requests for direct API calls (like other modules do)
try:
    import requests
    MLB_API_AVAILABLE = True
    logger.info("✅ Direct MLB API access available via requests")
except ImportError:
    pass

class PlayerStatsCollector:
    """Comprehensive player statistics collector"""
    
    # Season phase dates (updated annually)
    # Spring training typically runs late Feb through late Mar
    SPRING_TRAINING_START_MONTH_DAY = (2, 20)   # Feb 20
    REGULAR_SEASON_START_MONTH_DAY = (3, 25)     # Mar 25 (Opening Day 2026; adjust yearly)
    
    def __init__(self):
        self.db_config = DatabaseConfig()
        self.engine = self.db_config.create_engine()
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Set up MLB Stats API connection using direct requests
        self.base_url = "https://statsapi.mlb.com/api/v1"
        self.api_available = MLB_API_AVAILABLE
        
        if not self.api_available:
            logger.warning("MLB Stats API not available - player stats collection will be limited")
        else:
            logger.info("✅ MLB Stats API initialized successfully")
    
    def _determine_game_type(self, season: int) -> str:
        """
        Determine the correct gameType for the MLB Stats API based on the date
        and season being collected.
        
        Returns:
            'S' for spring training, 'R' for regular season
        """
        today = date.today()
        
        # If collecting a past season, always use regular season stats
        if season < today.year:
            return 'R'
        
        # If collecting the current year, check if regular season has started
        if season == today.year:
            regular_season_start = date(
                today.year,
                self.REGULAR_SEASON_START_MONTH_DAY[0],
                self.REGULAR_SEASON_START_MONTH_DAY[1]
            )
            if today < regular_season_start:
                logger.info(f"📅 Season {season}: Pre-regular-season → using spring training stats (gameType=S)")
                return 'S'
            else:
                logger.info(f"📅 Season {season}: Regular season active → using regular season stats (gameType=R)")
                return 'R'
        
        # Future season — shouldn't happen often, but use spring training if available
        logger.info(f"📅 Season {season}: Future season → using spring training stats (gameType=S)")
        return 'S'
    
    def _make_api_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to the MLB Stats API"""
        if not self.api_available:
            return {}
        
        try:
            import requests
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, params=params or {}, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return {}
    
    def _ensure_player_exists(self, player_id: int) -> bool:
        """Ensure player exists in database, create if missing"""
        
        try:
            # Check if player already exists
            existing_player = self.session.query(Player).filter_by(player_id=player_id).first()
            if existing_player:
                return True
            
            # Get player info from MLB API
            player_data = self._make_api_request(f'people/{player_id}')
            
            if not player_data.get('people'):
                logger.warning(f"Could not fetch player data for ID {player_id}")
                return False
            
            player_info = player_data['people'][0]
            
            # Extract player details
            full_name = player_info.get('fullName', 'Unknown Player')
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else 'Unknown'
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else 'Player'
            
            # Convert height to inches if available
            height_inches = None
            if player_info.get('height'):
                height_str = player_info['height']  # Format: "6' 7"
                try:
                    feet_inches = height_str.replace('"', '').split("'")
                    if len(feet_inches) == 2:
                        feet = int(feet_inches[0].strip())
                        inches = int(feet_inches[1].strip()) if feet_inches[1].strip() else 0
                        height_inches = feet * 12 + inches
                except:
                    pass
            
            # Parse birth date
            birth_date = None
            if player_info.get('birthDate'):
                try:
                    from datetime import datetime
                    birth_date = datetime.strptime(player_info['birthDate'], '%Y-%m-%d').date()
                except:
                    pass
            
            # Parse debut date
            debut_date = None
            if player_info.get('mlbDebutDate'):
                try:
                    debut_date = datetime.strptime(player_info['mlbDebutDate'], '%Y-%m-%d').date()
                except:
                    pass
            
            # Create new player record
            new_player = Player(
                player_id=player_id,
                name_first=first_name,
                name_last=last_name,
                name_display=full_name,
                birth_date=birth_date,
                birth_country=player_info.get('birthCountry'),
                birth_state=player_info.get('birthStateProvince'),
                birth_city=player_info.get('birthCity'),
                height_inches=height_inches,
                weight_lbs=player_info.get('weight'),
                bats=player_info.get('batSide', {}).get('code'),
                throws=player_info.get('pitchHand', {}).get('code'),
                mlb_debut_date=debut_date,
                is_active=player_info.get('active', True),
                primary_position=player_info.get('primaryPosition', {}).get('abbreviation'),
                jersey_number=player_info.get('primaryNumber')
            )
            
            self.session.add(new_player)
            self.session.commit()
            
            logger.info(f"✅ Created player record: {full_name} (ID: {player_id})")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to create player {player_id}: {str(e)}")
            return False
    
    def collect_current_season_batting_stats(self, season: int = None) -> Dict[str, Any]:
        """Collect current season batting statistics for all players using MLB Stats API.
        
        Iterates all 30 teams, fetches each team's active roster, and pulls
        individual player spring training (gameType=S) or regular season (gameType=R)
        batting stats depending on the date.
        """
        
        if not self.api_available:
            return {'success': False, 'error': 'MLB Stats API not available'}
        
        current_season = season or date.today().year
        game_type = self._determine_game_type(current_season)
        game_type_label = "spring training" if game_type == 'S' else "regular season"
        logger.info(f"🏏 Collecting {current_season} {game_type_label} batting statistics (roster-based)...")
        
        total_inserted = 0
        total_updated = 0
        total_skipped = 0
        teams_processed = 0
        
        try:
            # Iterate all 30 MLB teams
            for team_abbr, mlb_team_id in self._get_mlb_team_id_map().items():
                try:
                    # Get active roster for this team
                    roster_data = self._make_api_request(f'teams/{mlb_team_id}/roster', {
                        'rosterType': 'active',
                        'season': current_season
                    })
                    
                    roster = roster_data.get('roster', [])
                    if not roster:
                        logger.warning(f"   ⚠️  No roster found for {team_abbr}")
                        continue
                    
                    team_inserted = 0
                    team_updated = 0
                    
                    for player_entry in roster:
                        player_id = player_entry.get('person', {}).get('id')
                        if not player_id:
                            continue
                        
                        # Fetch individual player's batting stats
                        stats_data = self._make_api_request(f'people/{player_id}/stats', {
                            'stats': 'season',
                            'season': current_season,
                            'gameType': game_type,
                            'group': 'hitting'
                        })
                        
                        stat_info = None
                        if stats_data.get('stats'):
                            for sg in stats_data['stats']:
                                splits = sg.get('splits', [])
                                if splits:
                                    stat_info = splits[0].get('stat', {})
                                    break
                        
                        if not stat_info or int(stat_info.get('atBats', 0)) == 0:
                            total_skipped += 1
                            continue
                        
                        # Ensure player exists in database
                        if not self._ensure_player_exists(player_id):
                            total_skipped += 1
                            continue
                        
                        # Map to database format
                        player_data = self._map_leaderboard_batting_data(
                            stat_info, player_id, team_abbr, current_season
                        )
                        
                        if not player_data:
                            continue
                        
                        # Check if record exists
                        existing = self.session.query(PlayerBattingStats).filter_by(
                            player_id=player_id,
                            season=current_season,
                            team_id=team_abbr
                        ).first()
                        
                        if existing:
                            for key, value in player_data.items():
                                if hasattr(existing, key) and value is not None:
                                    setattr(existing, key, value)
                            team_updated += 1
                        else:
                            new_record = PlayerBattingStats(**player_data)
                            self.session.add(new_record)
                            team_inserted += 1
                    
                    self.session.commit()
                    total_inserted += team_inserted
                    total_updated += team_updated
                    teams_processed += 1
                    
                    if team_inserted + team_updated > 0:
                        logger.info(f"   ⚾ {team_abbr}: {team_inserted} new, {team_updated} updated batters")
                    
                except Exception as e:
                    self.session.rollback()
                    logger.error(f"   ❌ Failed to collect batting for {team_abbr}: {str(e)}")
            
            logger.info(f"   ✅ Batting complete: {total_inserted} new, {total_updated} updated across {teams_processed} teams ({total_skipped} skipped)")
            
            return {
                'success': True,
                'source': 'player_batting_stats',
                'season': current_season,
                'game_type': game_type_label,
                'inserted': total_inserted,
                'updated': total_updated,
                'teams_processed': teams_processed
            }
            
        except Exception as e:
            self.session.rollback()
            error_msg = f"Failed to collect batting stats: {str(e)}"
            log_error("Player Batting Stats", error_msg)
            return {'success': False, 'error': error_msg}
    
    def collect_current_season_pitching_stats(self, season: int = None) -> Dict[str, Any]:
        """Collect current season pitching statistics for all players using MLB Stats API.
        
        Iterates all 30 teams, fetches each team's active roster, and pulls
        individual player spring training (gameType=S) or regular season (gameType=R)
        pitching stats depending on the date.
        """
        
        if not self.api_available:
            return {'success': False, 'error': 'MLB Stats API not available'}
        
        current_season = season or date.today().year
        game_type = self._determine_game_type(current_season)
        game_type_label = "spring training" if game_type == 'S' else "regular season"
        logger.info(f"⚾ Collecting {current_season} {game_type_label} pitching statistics (roster-based)...")
        
        total_inserted = 0
        total_updated = 0
        total_skipped = 0
        teams_processed = 0
        
        try:
            # Iterate all 30 MLB teams
            for team_abbr, mlb_team_id in self._get_mlb_team_id_map().items():
                try:
                    # Get active roster for this team
                    roster_data = self._make_api_request(f'teams/{mlb_team_id}/roster', {
                        'rosterType': 'active',
                        'season': current_season
                    })
                    
                    roster = roster_data.get('roster', [])
                    if not roster:
                        continue
                    
                    team_inserted = 0
                    team_updated = 0
                    
                    for player_entry in roster:
                        player_id = player_entry.get('person', {}).get('id')
                        if not player_id:
                            continue
                        
                        # Fetch individual player's pitching stats
                        stats_data = self._make_api_request(f'people/{player_id}/stats', {
                            'stats': 'season',
                            'season': current_season,
                            'gameType': game_type,
                            'group': 'pitching'
                        })
                        
                        stat_info = None
                        if stats_data.get('stats'):
                            for sg in stats_data['stats']:
                                splits = sg.get('splits', [])
                                if splits:
                                    stat_info = splits[0].get('stat', {})
                                    break
                        
                        if not stat_info or float(stat_info.get('inningsPitched', 0)) == 0:
                            total_skipped += 1
                            continue
                        
                        # Ensure player exists in database
                        if not self._ensure_player_exists(player_id):
                            total_skipped += 1
                            continue
                        
                        # Map to database format
                        player_data = self._map_leaderboard_pitching_data(
                            stat_info, player_id, team_abbr, current_season
                        )
                        
                        if not player_data:
                            continue
                        
                        # Check if record exists
                        existing = self.session.query(PlayerPitchingStats).filter_by(
                            player_id=player_id,
                            season=current_season,
                            team_id=team_abbr
                        ).first()
                        
                        if existing:
                            for key, value in player_data.items():
                                if hasattr(existing, key) and value is not None:
                                    setattr(existing, key, value)
                            team_updated += 1
                        else:
                            new_record = PlayerPitchingStats(**player_data)
                            self.session.add(new_record)
                            team_inserted += 1
                    
                    self.session.commit()
                    total_inserted += team_inserted
                    total_updated += team_updated
                    teams_processed += 1
                    
                    if team_inserted + team_updated > 0:
                        logger.info(f"   🥎 {team_abbr}: {team_inserted} new, {team_updated} updated pitchers")
                    
                except Exception as e:
                    self.session.rollback()
                    logger.error(f"   ❌ Failed to collect pitching for {team_abbr}: {str(e)}")
            
            logger.info(f"   ✅ Pitching complete: {total_inserted} new, {total_updated} updated across {teams_processed} teams ({total_skipped} skipped)")
            
            return {
                'success': True,
                'source': 'player_pitching_stats',
                'season': current_season,
                'game_type': game_type_label,
                'inserted': total_inserted,
                'updated': total_updated,
                'teams_processed': teams_processed
            }
            
        except Exception as e:
            self.session.rollback()
            error_msg = f"Failed to collect pitching stats: {str(e)}"
            log_error("Player Pitching Stats", error_msg)
            return {'success': False, 'error': error_msg}
    
    def collect_multi_season_stats(self, seasons: List[int] = None):
        """
        Collect player stats for multiple seasons
        
        Args:
            seasons: List of seasons to collect. Defaults to [2023, 2024, 2025]
        """
        if seasons is None:
            seasons = [2023, 2024, 2025]
        
        logger.info(f"🏆 Starting multi-season player stats collection for seasons: {seasons}")
        
        total_batting_success = 0
        total_pitching_success = 0
        total_batting_errors = 0
        total_pitching_errors = 0
        
        for season in seasons:
            logger.info(f"📅 Collecting player stats for {season} season")
            try:
                # Collect batting stats for this season
                batting_result = self.collect_current_season_batting_stats(season)
                if batting_result['success']:
                    total_batting_success += batting_result['inserted'] + batting_result['updated']
                    logger.info(f"   ⚾ Batting {season}: {batting_result['inserted']} new, {batting_result['updated']} updated")
                else:
                    total_batting_errors += 1
                    logger.error(f"   ❌ Batting {season} failed: {batting_result.get('error', 'Unknown error')}")
                
                # Collect pitching stats for this season
                pitching_result = self.collect_current_season_pitching_stats(season)
                if pitching_result['success']:
                    total_pitching_success += pitching_result['inserted'] + pitching_result['updated']
                    logger.info(f"   🥎 Pitching {season}: {pitching_result['inserted']} new, {pitching_result['updated']} updated")
                else:
                    total_pitching_errors += 1
                    logger.error(f"   ❌ Pitching {season} failed: {pitching_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Failed to collect stats for season {season}: {str(e)}")
                total_batting_errors += 1
                total_pitching_errors += 1
        
        total_success = total_batting_success + total_pitching_success
        total_errors = total_batting_errors + total_pitching_errors
        
        logger.info(f"🏆 Multi-season collection completed:")
        logger.info(f"   📊 Total records processed: {total_success}")
        logger.info(f"   ⚾ Batting records: {total_batting_success}")
        logger.info(f"   🥎 Pitching records: {total_pitching_success}")
        logger.info(f"   ❌ Total errors: {total_errors}")
        
        return {
            'success': total_errors == 0,
            'total_records': total_success,
            'batting_records': total_batting_success,
            'pitching_records': total_pitching_success,
            'total_errors': total_errors,
            'seasons_processed': seasons
        }
    
    def collect_daily_player_status(self, target_date: date = None) -> Dict[str, Any]:
        """Collect daily player status and availability"""
        
        target_date = target_date or date.today()
        logger.info(f"👥 Collecting player status for {target_date}...")
        
        try:
            # Get games for the target date
            games_query = text("""
                SELECT game_pk, home_team_id, away_team_id
                FROM games 
                WHERE game_date = :target_date
            """)
            
            games = self.session.execute(games_query, {'target_date': target_date}).fetchall()
            
            if not games:
                logger.info(f"   📭 No games scheduled for {target_date}")
                return {'success': True, 'inserted': 0, 'updated': 0, 'message': 'No games scheduled'}
            
            # Process each game to get rosters and status
            total_inserted = 0
            total_updated = 0
            
            for game in games:
                home_result = self._collect_team_daily_status(game.home_team_id, target_date, game.game_pk)
                away_result = self._collect_team_daily_status(game.away_team_id, target_date, game.game_pk)
                
                total_inserted += home_result[0] + away_result[0]
                total_updated += home_result[1] + away_result[1]
            
            logger.info(f"   ✅ Player Status: {total_inserted} new, {total_updated} updated")
            
            return {
                'success': True,
                'source': 'daily_player_status',
                'date': str(target_date),
                'inserted': total_inserted,
                'updated': total_updated,
                'games_processed': len(games)
            }
            
        except Exception as e:
            error_msg = f"Failed to collect daily player status: {str(e)}"
            log_error("Daily Player Status", error_msg)
            return {'success': False, 'error': error_msg}
    
    def _mlb_team_id_to_abbr(self, mlb_team_id: int) -> str:
        """Convert MLB Stats API team ID to our team abbreviation"""
        team_map = {
            108: 'LAA', 109: 'AZ', 110: 'BAL', 111: 'BOS', 112: 'CHC', 
            113: 'CIN', 114: 'CLE', 115: 'COL', 116: 'DET', 117: 'HOU',
            118: 'KC', 119: 'LAD', 120: 'WSH', 121: 'NYM', 133: 'OAK',  # Fixed WSH
            134: 'PIT', 135: 'SD', 136: 'SEA', 137: 'SF', 138: 'STL',
            139: 'TB', 140: 'TEX', 141: 'TOR', 142: 'MIN', 143: 'PHI',
            144: 'ATL', 145: 'CHW', 146: 'MIA', 147: 'NYY', 158: 'MIL'  # Fixed CHW
        }
        return team_map.get(mlb_team_id)
    
    def _get_mlb_team_id_map(self) -> Dict[str, int]:
        """Get mapping of team abbreviation -> MLB Stats API team ID for all 30 teams"""
        return {
            'LAA': 108, 'AZ': 109, 'BAL': 110, 'BOS': 111, 'CHC': 112,
            'CIN': 113, 'CLE': 114, 'COL': 115, 'DET': 116, 'HOU': 117,
            'KC': 118, 'LAD': 119, 'WSH': 120, 'NYM': 121, 'OAK': 133,
            'PIT': 134, 'SD': 135, 'SEA': 136, 'SF': 137, 'STL': 138,
            'TB': 139, 'TEX': 140, 'TOR': 141, 'MIN': 142, 'PHI': 143,
            'ATL': 144, 'CHW': 145, 'MIA': 146, 'NYY': 147, 'MIL': 158
        }
    
    def _collect_player_batting_stats(self, player_id: int, team_id: str, season: int) -> Tuple[int, int]:
        """Collect batting stats for a specific player"""
        try:
            # Get player stats from MLB API
            stats_data = self._make_api_request('people', {
                'personId': player_id,
                'hydrate': 'stats',
                'stats': 'season',
                'gameType': 'R',
                'season': season
            })
            
            if not stats_data.get('people'):
                return (0, 0)
            
            player_data = stats_data['people'][0]
            stats = player_data.get('stats', [])
            
            # Find batting stats
            batting_stats = None
            for stat_group in stats:
                if stat_group.get('group', {}).get('displayName') == 'hitting':
                    batting_stats = stat_group.get('stats', [{}])[0].get('stat', {})
                    break
            
            if not batting_stats:
                return (0, 0)
            
            # Map to database format
            player_data = self._map_mlb_batting_data(batting_stats, player_id, team_id, season)
            
            if not player_data:
                return (0, 0)
            
            # Check if record exists
            existing = self.session.query(PlayerBattingStats).filter_by(
                player_id=player_data['player_id'],
                season=season,
                team_id=team_id
            ).first()
            
            if existing:
                # Update existing record
                for key, value in player_data.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                self.session.commit()
                return (0, 1)
            else:
                # Create new record
                new_record = PlayerBattingStats(**player_data)
                self.session.add(new_record)
                self.session.commit()
                return (1, 0)
                
        except Exception as e:
            logger.error(f"Failed to collect batting stats for player {player_id}: {str(e)}")
            return (0, 0)
    
    def _collect_player_pitching_stats(self, player_id: int, team_id: str, season: int) -> Tuple[int, int]:
        """Collect pitching stats for a specific player"""
        try:
            # Get player stats from MLB API
            stats_data = self._make_api_request('people', {
                'personId': player_id,
                'hydrate': 'stats',
                'stats': 'season',
                'gameType': 'R',
                'season': season
            })
            
            if not stats_data.get('people'):
                return (0, 0)
            
            player_data = stats_data['people'][0]
            stats = player_data.get('stats', [])
            
            # Find pitching stats
            pitching_stats = None
            for stat_group in stats:
                if stat_group.get('group', {}).get('displayName') == 'pitching':
                    pitching_stats = stat_group.get('stats', [{}])[0].get('stat', {})
                    break
            
            if not pitching_stats:
                return (0, 0)
            
            # Map to database format
            player_data = self._map_mlb_pitching_data(pitching_stats, player_id, team_id, season)
            
            if not player_data:
                return (0, 0)
            
            # Check if record exists
            existing = self.session.query(PlayerPitchingStats).filter_by(
                player_id=player_data['player_id'],
                season=season,
                team_id=team_id
            ).first()
            
            if existing:
                # Update existing record
                for key, value in player_data.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                self.session.commit()
                return (0, 1)
            else:
                # Create new record
                new_record = PlayerPitchingStats(**player_data)
                self.session.add(new_record)
                self.session.commit()
                return (1, 0)
                
        except Exception as e:
            logger.error(f"Failed to collect pitching stats for player {player_id}: {str(e)}")
            return (0, 0)
    def _map_mlb_batting_data(self, stats: Dict, player_id: int, team_id: str, season: int) -> Dict[str, Any]:
        """Map MLB Stats API batting data to database schema"""
        
        def safe_float(value, default=0.0):
            if value is None or value == '':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        return {
            'player_id': player_id,
            'season': season,
            'team_id': team_id,
            'games_played': safe_int(stats.get('gamesPlayed')),
            'plate_appearances': safe_int(stats.get('plateAppearances')),
            'at_bats': safe_int(stats.get('atBats')),
            'runs': safe_int(stats.get('runs')),
            'hits': safe_int(stats.get('hits')),
            'doubles': safe_int(stats.get('doubles')),
            'triples': safe_int(stats.get('triples')),
            'home_runs': safe_int(stats.get('homeRuns')),
            'rbi': safe_int(stats.get('rbi')),
            'stolen_bases': safe_int(stats.get('stolenBases')),
            'caught_stealing': safe_int(stats.get('caughtStealing')),
            'walks': safe_int(stats.get('baseOnBalls')),
            'strikeouts': safe_int(stats.get('strikeOuts')),
            'batting_average': safe_float(stats.get('avg')),
            'on_base_percentage': safe_float(stats.get('obp')),
            'slugging_percentage': safe_float(stats.get('slg')),
            'ops': safe_float(stats.get('ops')),
            'hit_by_pitch': safe_int(stats.get('hitByPitch')),
            'sacrifice_hits': safe_int(stats.get('sacBunts')),
            'sacrifice_flies': safe_int(stats.get('sacFlies')),
            'intentional_walks': safe_int(stats.get('intentionalWalks')),
            'left_on_base': safe_int(stats.get('leftOnBase')),
            'wrc_plus': None,  # Not available in MLB Stats API
            'war': None,       # Not available in MLB Stats API
            'last_updated': datetime.now()
        }
    
    def _map_leaderboard_batting_data(self, stats: Dict, player_id: int, team_id: str, season: int) -> Dict[str, Any]:
        """Map MLB Stats API leaderboard batting data to database schema"""
        
        def safe_float(value, default=0.0):
            if value is None or value == '':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        return {
            'player_id': player_id,
            'season': season,
            'team_id': team_id,
            'games': safe_int(stats.get('gamesPlayed')),
            'plate_appearances': safe_int(stats.get('plateAppearances')),
            'at_bats': safe_int(stats.get('atBats')),
            'runs': safe_int(stats.get('runs')),
            'hits': safe_int(stats.get('hits')),
            'home_runs': safe_int(stats.get('homeRuns')),
            'rbis': safe_int(stats.get('rbi')),
            'stolen_bases': safe_int(stats.get('stolenBases')),
            'walks': safe_int(stats.get('baseOnBalls')),
            'strikeouts': safe_int(stats.get('strikeOuts')),
            'batting_average': safe_float(stats.get('avg')),
            'on_base_percentage': safe_float(stats.get('obp')),
            'slugging_percentage': safe_float(stats.get('slg')),
            'ops': safe_float(stats.get('ops')),
            # Advanced stats (set to None for now)
            'woba': None,
            'wrc_plus': None,
            'war': None,
            'avg_exit_velocity': None,
            'hard_hit_percent': None,
            'barrel_percent': None
        }
    
    def _map_leaderboard_pitching_data(self, stats: Dict, player_id: int, team_id: str, season: int) -> Dict[str, Any]:
        """Map MLB Stats API leaderboard pitching data to database schema"""
        
        def safe_float(value, default=0.0):
            if value is None or value == '':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        return {
            'player_id': player_id,
            'season': season,
            'team_id': team_id,
            'games': safe_int(stats.get('gamesPlayed')),
            'games_started': safe_int(stats.get('gamesStarted')),
            'wins': safe_int(stats.get('wins')),
            'losses': safe_int(stats.get('losses')),
            'saves': safe_int(stats.get('saves')),
            'innings_pitched': safe_float(stats.get('inningsPitched')),
            'hits_allowed': safe_int(stats.get('hits')),
            'runs_allowed': safe_int(stats.get('runs')),
            'earned_runs_allowed': safe_int(stats.get('earnedRuns')),
            'walks_allowed': safe_int(stats.get('baseOnBalls')),
            'strikeouts': safe_int(stats.get('strikeOuts')),
            'home_runs_allowed': safe_int(stats.get('homeRuns')),
            'era': safe_float(stats.get('era')),
            'whip': safe_float(stats.get('whip')),
            # Advanced stats (set to None for now)
            'fip': None,
            'xfip': None,
            'war': None,
            'stuff_plus': None,
            'location_plus': None,
            'pitching_plus': None,
            'starter_reliever': None
        }
    
    def _map_mlb_pitching_data(self, stats: Dict, player_id: int, team_id: str, season: int) -> Dict[str, Any]:
        """Map MLB Stats API pitching data to database schema"""
        
        def safe_float(value, default=0.0):
            if value is None or value == '':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        return {
            'player_id': player_id,
            'season': season,
            'team_id': team_id,
            'games_played': safe_int(stats.get('gamesPlayed')),
            'games_started': safe_int(stats.get('gamesStarted')),
            'wins': safe_int(stats.get('wins')),
            'losses': safe_int(stats.get('losses')),
            'saves': safe_int(stats.get('saves')),
            'innings_pitched': safe_float(stats.get('inningsPitched')),
            'hits_allowed': safe_int(stats.get('hits')),
            'runs_allowed': safe_int(stats.get('runs')),
            'earned_runs': safe_int(stats.get('earnedRuns')),
            'walks': safe_int(stats.get('baseOnBalls')),
            'strikeouts': safe_int(stats.get('strikeOuts')),
            'home_runs_allowed': safe_int(stats.get('homeRuns')),
            'era': safe_float(stats.get('era')),
            'whip': safe_float(stats.get('whip')),
            'k_9': safe_float(stats.get('strikeoutsPer9Inn')),
            'bb_9': safe_float(stats.get('walksPer9Inn')),
            'hr_9': safe_float(stats.get('homeRunsPer9')),
            'k_bb_ratio': safe_float(stats.get('strikeoutWalkRatio')),
            'babip': None,     # Not directly available in MLB Stats API
            'fip': None,       # Not available in MLB Stats API
            'xfip': None,      # Not available in MLB Stats API
            'war': None,       # Not available in MLB Stats API
            'complete_games': safe_int(stats.get('completeGames')),
            'shutouts': safe_int(stats.get('shutouts')),
            'holds': safe_int(stats.get('holds')),
            'blown_saves': safe_int(stats.get('blownSaves')),
            'hit_by_pitch': safe_int(stats.get('hitBatsmen')),
            'wild_pitches': safe_int(stats.get('wildPitches')),
            'balks': safe_int(stats.get('balks')),
            'last_updated': datetime.now()
        }
    
    def _collect_team_daily_status(self, team_id: str, target_date: date, game_pk: int) -> Tuple[int, int]:
        """Collect daily status for players on a specific team"""
        
        inserted = 0
        updated = 0
        
        try:
            if not self.api_available:
                return 0, 0
            
            # Get roster for the team
            roster_data = self._make_api_request('teams', {
                'teamId': self._get_mlb_team_id(team_id), 
                'rosterType': 'active'
            })
            
            if not roster_data.get('teams'):
                return 0, 0
            
            roster = roster_data['teams'][0].get('roster', [])
            
            for player_info in roster:
                player = player_info.get('person', {})
                player_id = player.get('id')
                
                if not player_id:
                    continue
                
                # Create daily status record
                status_data = {
                    'player_id': player_id,
                    'status_date': target_date,
                    'team_id': team_id,
                    'is_active': True,
                    'roster_status': player_info.get('status', {}).get('description', 'Active'),
                    'jersey_number': player_info.get('jerseyNumber'),
                    'position': player_info.get('position', {}).get('abbreviation'),
                    'game_pk': game_pk
                }
                
                # Check if record exists
                existing = self.session.query(DailyPlayerStatus).filter_by(
                    player_id=player_id,
                    status_date=target_date,
                    team_id=team_id
                ).first()
                
                if existing:
                    # Update existing
                    for key, value in status_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    updated += 1
                else:
                    # Create new
                    new_status = DailyPlayerStatus(**status_data)
                    self.session.add(new_status)
                    inserted += 1
            
            self.session.commit()
            
        except Exception as e:
            self.session.rollback()
            log_error("Team Daily Status", f"Failed to process team {team_id}: {str(e)}")
            return 0, 0
        
        return inserted, updated
    
    def _get_mlb_team_id(self, team_abbr: str) -> int:
        """Convert team abbreviation to MLB Stats API team ID"""
        
        # MLB team ID mapping
        mlb_team_ids = {
            'LAA': 108, 'HOU': 117, 'OAK': 133, 'SEA': 136, 'TEX': 140,
            'CHW': 145, 'CLE': 114, 'DET': 116, 'KC': 118, 'MIN': 142,
            'NYY': 147, 'BAL': 110, 'BOS': 111, 'TB': 139, 'TOR': 141,
            'ATL': 144, 'MIA': 146, 'NYM': 121, 'PHI': 143, 'WSH': 120,
            'CHC': 112, 'CIN': 113, 'MIL': 158, 'PIT': 134, 'STL': 138,
            'AZ': 109, 'COL': 115, 'LAD': 119, 'SD': 135, 'SF': 137
        }
        
        return mlb_team_ids.get(team_abbr, 0)
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to integer"""
        try:
            if value is None or value == '' or str(value).lower() == 'nan':
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float"""
        try:
            if value is None or value == '' or str(value).lower() == 'nan':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None


def collect_all_player_stats(season: int = None) -> Dict[str, Any]:
    """
    Main function to collect all player statistics
    """
    collector = PlayerStatsCollector()
    
    results = {
        'batting_stats': collector.collect_current_season_batting_stats(season),
        'pitching_stats': collector.collect_current_season_pitching_stats(season)
    }
    
    return results


def collect_daily_player_status(target_date: date = None) -> Dict[str, Any]:
    """
    Main function to collect daily player status
    """
    collector = PlayerStatsCollector()
    return collector.collect_daily_player_status(target_date)
    
    def _collect_team_daily_status(self, team_id: str, target_date: date, game_pk: int) -> Tuple[int, int]:
        """Collect daily status for players on a specific team"""
        
        inserted = 0
        updated = 0
        
        try:
            if not self.api_available:
                return 0, 0
            
            # Get roster for the team
            roster_data = self._make_api_request('teams', {
                'teamId': self._get_mlb_team_id(team_id), 
                'rosterType': 'active'
            })
            
            if not roster_data.get('teams'):
                return 0, 0
            
            roster = roster_data['teams'][0].get('roster', [])
            
            for player_info in roster:
                player = player_info.get('person', {})
                player_id = player.get('id')
                
                if not player_id:
                    continue
                
                # Create daily status record
                status_data = {
                    'player_id': player_id,
                    'status_date': target_date,
                    'team_id': team_id,
                    'is_active': True,
                    'roster_status': player_info.get('status', {}).get('description', 'Active'),
                    'jersey_number': player_info.get('jerseyNumber'),
                    'position': player_info.get('position', {}).get('abbreviation'),
                    'game_pk': game_pk
                }
                
                # Check if record exists
                existing = self.session.query(DailyPlayerStatus).filter_by(
                    player_id=player_id,
                    status_date=target_date,
                    team_id=team_id
                ).first()
                
                if existing:
                    # Update existing
                    for key, value in status_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    updated += 1
                else:
                    # Create new
                    new_status = DailyPlayerStatus(**status_data)
                    self.session.add(new_status)
                    inserted += 1
            
            self.session.commit()
            
        except Exception as e:
            logger.warning(f"   ⚠️  Failed to collect status for team {team_id}: {str(e)}")
            self.session.rollback()
        
        return inserted, updated
    
    def _map_batting_data(self, row: pd.Series, season: int) -> Optional[Dict]:
        """Map PyBaseball batting data to database schema"""
        
        try:
            # Extract player ID - PyBaseball uses different ID fields
            player_id = None
            for id_field in ['mlbid', 'key_mlbam', 'playerid', 'IDfg']:
                if id_field in row and pd.notna(row[id_field]):
                    player_id = int(row[id_field])
                    break
            
            if not player_id:
                return None
            
            # Map team abbreviation to team_id
            team_id = self._map_team_name_to_id(row.get('Team', ''))
            
            if not team_id:
                return None
            
            return {
                'player_id': player_id,
                'team_id': team_id,
                'season': season,
                'games': self._safe_int(row.get('G')),
                'plate_appearances': self._safe_int(row.get('PA')),
                'at_bats': self._safe_int(row.get('AB')),
                'hits': self._safe_int(row.get('H')),
                'singles': self._safe_int(row.get('1B')),
                'doubles': self._safe_int(row.get('2B')),
                'triples': self._safe_int(row.get('3B')),
                'home_runs': self._safe_int(row.get('HR')),
                'runs': self._safe_int(row.get('R')),
                'rbis': self._safe_int(row.get('RBI')),
                'walks': self._safe_int(row.get('BB')),
                'strikeouts': self._safe_int(row.get('SO')),
                'stolen_bases': self._safe_int(row.get('SB')),
                'caught_stealing': self._safe_int(row.get('CS')),
                'batting_average': self._safe_decimal(row.get('AVG')),
                'on_base_percentage': self._safe_decimal(row.get('OBP')),
                'slugging_percentage': self._safe_decimal(row.get('SLG')),
                'ops': self._safe_decimal(row.get('OPS')),
                'woba': self._safe_decimal(row.get('wOBA')),
                'wrc_plus': self._safe_int(row.get('wRC+')),
                'war': self._safe_decimal(row.get('WAR')),
                'babip': self._safe_decimal(row.get('BABIP'))
            }
            
        except Exception as e:
            logger.warning(f"Failed to map batting data: {str(e)}")
            return None
    
    def _map_pitching_data(self, row: pd.Series, season: int) -> Optional[Dict]:
        """Map PyBaseball pitching data to database schema"""
        
        try:
            # Extract player ID
            player_id = None
            for id_field in ['mlbid', 'key_mlbam', 'playerid', 'IDfg']:
                if id_field in row and pd.notna(row[id_field]):
                    player_id = int(row[id_field])
                    break
            
            if not player_id:
                return None
            
            # Map team abbreviation to team_id
            team_id = self._map_team_name_to_id(row.get('Team', ''))
            
            if not team_id:
                return None
            
            return {
                'player_id': player_id,
                'team_id': team_id,
                'season': season,
                'games': self._safe_int(row.get('G')),
                'games_started': self._safe_int(row.get('GS')),
                'wins': self._safe_int(row.get('W')),
                'losses': self._safe_int(row.get('L')),
                'saves': self._safe_int(row.get('SV')),
                'innings_pitched': self._safe_decimal(row.get('IP')),
                'hits_allowed': self._safe_int(row.get('H')),
                'runs_allowed': self._safe_int(row.get('R')),
                'earned_runs_allowed': self._safe_int(row.get('ER')),
                'home_runs_allowed': self._safe_int(row.get('HR')),
                'walks_allowed': self._safe_int(row.get('BB')),
                'strikeouts': self._safe_int(row.get('SO')),
                'era': self._safe_decimal(row.get('ERA')),
                'whip': self._safe_decimal(row.get('WHIP')),
                'fip': self._safe_decimal(row.get('FIP')),
                'xfip': self._safe_decimal(row.get('xFIP')),
                'war': self._safe_decimal(row.get('WAR')),
                'stuff_plus': self._safe_int(row.get('Stuff+')),
                'location_plus': self._safe_int(row.get('Location+')),
                'pitching_plus': self._safe_int(row.get('Pitching+'))
            }
            
        except Exception as e:
            logger.warning(f"Failed to map pitching data: {str(e)}")
            return None
    
    def _map_team_name_to_id(self, team_name: str) -> Optional[str]:
        """Map team name/abbreviation to team_id"""
        
        if not team_name:
            return None
        
        # Team mapping dictionary (expand as needed)
        team_mapping = {
            'LAA': 'LAA', 'HOU': 'HOU', 'OAK': 'OAK', 'SEA': 'SEA', 'TEX': 'TEX',
            'CHW': 'CHW', 'CLE': 'CLE', 'DET': 'DET', 'KC': 'KC', 'MIN': 'MIN',
            'NYY': 'NYY', 'BAL': 'BAL', 'BOS': 'BOS', 'TB': 'TB', 'TOR': 'TOR',
            'ATL': 'ATL', 'MIA': 'MIA', 'NYM': 'NYM', 'PHI': 'PHI', 'WSH': 'WSH',
            'CHC': 'CHC', 'CIN': 'CIN', 'MIL': 'MIL', 'PIT': 'PIT', 'STL': 'STL',
            'AZ': 'AZ', 'COL': 'COL', 'LAD': 'LAD', 'SD': 'SD', 'SF': 'SF'
        }
        
        return team_mapping.get(team_name.upper())
    
    def _get_mlb_team_id(self, team_abbr: str) -> int:
        """Convert team abbreviation to MLB Stats API team ID"""
        
        # MLB team ID mapping
        mlb_team_ids = {
            'LAA': 108, 'HOU': 117, 'OAK': 133, 'SEA': 136, 'TEX': 140,
            'CHW': 145, 'CLE': 114, 'DET': 116, 'KC': 118, 'MIN': 142,
            'NYY': 147, 'BAL': 110, 'BOS': 111, 'TB': 139, 'TOR': 141,
            'ATL': 144, 'MIA': 146, 'NYM': 121, 'PHI': 143, 'WSH': 120,
            'CHC': 112, 'CIN': 113, 'MIL': 158, 'PIT': 134, 'STL': 138,
            'AZ': 109, 'COL': 115, 'LAD': 119, 'SD': 135, 'SF': 137
        }
        
        return mlb_team_ids.get(team_abbr, 0)
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to integer"""
        try:
            if pd.isna(value) or value == '' or value is None:
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def _safe_decimal(self, value) -> Optional[float]:
        """Safely convert value to decimal"""
        try:
            if pd.isna(value) or value == '' or value is None:
                return None
            return round(float(value), 3)
        except (ValueError, TypeError):
            return None
    
    def __del__(self):
        """Cleanup database session"""
        if hasattr(self, 'session'):
            self.session.close()

# Main collection functions (following your existing pattern)

def collect_player_batting_stats(season: int = None) -> Dict[str, Any]:
    """Collect batting statistics for all players"""
    collector = PlayerStatsCollector()
    return collector.collect_current_season_batting_stats(season)

def collect_player_pitching_stats(season: int = None) -> Dict[str, Any]:
    """Collect pitching statistics for all players"""
    collector = PlayerStatsCollector()
    return collector.collect_current_season_pitching_stats(season)

def collect_daily_player_status(target_date: date = None) -> Dict[str, Any]:
    """Collect daily player status and availability"""
    collector = PlayerStatsCollector()
    return collector.collect_daily_player_status(target_date)

def collect_all_player_stats(season: int = None) -> Dict[str, Any]:
    """Collect all player statistics (batting + pitching)"""
    logger.info("🏆 Starting comprehensive player stats collection")
    
    results = []
    overall_success = True
    
    try:
        # Collect batting stats
        batting_result = collect_player_batting_stats(season)
        results.append(batting_result)
        
        if not batting_result['success']:
            overall_success = False
        
        # Collect pitching stats
        pitching_result = collect_player_pitching_stats(season)
        results.append(pitching_result)
        
        if not pitching_result['success']:
            overall_success = False
        
        # Collect daily status for today
        status_result = collect_daily_player_status()
        results.append(status_result)
        
        if not status_result['success']:
            overall_success = False
        
    except Exception as e:
        log_error("Player Stats Collection", f"Collection failed: {str(e)}")
        overall_success = False
    
    # Calculate totals
    total_inserted = sum(r.get('inserted', 0) for r in results)
    total_updated = sum(r.get('updated', 0) for r in results)
    
    logger.info(f"🏆 Player stats collection complete: {total_inserted + total_updated} total changes")
    
    return {
        'overall_success': overall_success,
        'source': 'all_player_stats',
        'total_inserted': total_inserted,
        'total_updated': total_updated,
        'results': results
    }

# Command line interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == 'batting':
            result = collect_player_batting_stats()
        elif mode == 'pitching':
            result = collect_player_pitching_stats()
        elif mode == 'status':
            result = collect_daily_player_status()
        elif mode == 'all':
            result = collect_all_player_stats()
        else:
            print("Usage: python player_stats.py [batting|pitching|status|all]")
            sys.exit(1)
    else:
        result = collect_all_player_stats()
    
    print(f"✅ Success: {result['overall_success']}")
    if 'total_inserted' in result:
        print(f"📊 Inserted: {result['total_inserted']}")
        print(f"📊 Updated: {result['total_updated']}")
    
    sys.exit(0 if result['overall_success'] else 1)